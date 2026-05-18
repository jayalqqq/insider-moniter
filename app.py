import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SEC Insider Trading Monitor",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #0e1117; color: #fafafa; }

section[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #21262d;
}

div[data-testid="metric-container"] {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px 20px;
}

/* ── Table ── */
.filing-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
    table-layout: fixed;
}
.filing-table th {
    background-color: #1f2937;
    color: #60a5fa;
    padding: 10px 10px;
    text-align: left;
    border-bottom: 2px solid #374151;
    font-weight: 600;
    letter-spacing: 0.03em;
    white-space: nowrap;
    overflow: hidden;
}
.filing-table td {
    padding: 8px 10px;
    border-bottom: 1px solid #1f2937;
    vertical-align: middle;
    overflow: hidden;
    text-overflow: ellipsis;
}
/* per-column widths tuned for 1440px with sidebar */
.filing-table .col-date   { width: 90px;  white-space: nowrap; }
.filing-table .col-txn    { width: 78px;  white-space: nowrap; }
.filing-table .col-exec   { width: 150px; }
.filing-table .col-title  { width: 130px; }
.filing-table .col-co     { width: 185px; }
.filing-table .col-sector { width: 110px; }
.filing-table .col-shares { width: 80px;  white-space: nowrap; text-align: right; }
.filing-table .col-value  { width: 82px;  white-space: nowrap; text-align: right; }
.filing-table .col-ret    { width: 155px; white-space: nowrap; }
.filing-table .col-link   { width: 60px;  white-space: nowrap; }

.filing-table tr:hover td  { background-color: #1a2332; }
.filing-table tr.notable td { background-color: #162616; }
.filing-table tr.notable td:first-child { border-left: 3px solid #22c55e; }

.filing-table a { color: #38bdf8; text-decoration: none; font-weight: 500; }
.filing-table a:hover { text-decoration: underline; }

.ticker-pill {
    display: inline-block;
    background-color: #1e1b4b;
    color: #a78bfa;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    margin-left: 4px;
    vertical-align: middle;
}

.badge {
    display: inline-block;
    background-color: #1e3a5f;
    color: #60a5fa;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
}
.badge-alert { background-color: #422006; color: #fb923c; }

hr { border-color: #21262d; }
h2 { color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS     = {"User-Agent": "Jayal insider-monitor jayal@email.com"}
BASE_URL    = "https://efts.sec.gov/LATEST/search-index"
MAX_RESULTS = 200

TRANSACTION_LABELS = {"P": "🟢 Buy", "S": "🔴 Sell", "A": "🔵 Award"}
TRANSACTION_ORDER  = ["🟢 Buy", "🔴 Sell", "🔵 Award", "⚪ Other"]
PIE_COLORS = {
    "🟢 Buy": "#22c55e", "🔴 Sell": "#ef4444",
    "🔵 Award": "#3b82f6", "⚪ Other": "#6b7280",
}
NOTABLE_RE   = _re.compile(r"\b(Chief|CEO|CFO|President)\b", _re.IGNORECASE)
SEE_RMKS_RE  = _re.compile(r"see\s+remarks", _re.IGNORECASE)

# ── Regex for SEC .txt parsing ────────────────────────────────────────────────
_CIK_RE    = _re.compile(r"\s*\(CIK\s+\d+\)\s*$", _re.IGNORECASE)
_CODE_RE   = _re.compile(r"<transactionCode>([^<]+)</transactionCode>", _re.I)
_TITLE_RE  = _re.compile(r"<officerTitle>([^<]*)</officerTitle>", _re.I)
_SHARES_RE = _re.compile(r"<transactionShares>\s*<value>([^<]+)</value>", _re.I | _re.S)
_PRICE_RE  = _re.compile(r"<transactionPricePerShare>\s*<value>([^<]+)</value>", _re.I | _re.S)
_TDATE_RE  = _re.compile(r"<transactionDate>\s*<value>([^<]+)</value>", _re.I | _re.S)


# ── Formatters ────────────────────────────────────────────────────────────────
def _fmt_ret_single(r) -> str:
    if r is None:
        return "<span style='color:#4b5563'>—</span>"
    color = "#22c55e" if r >= 0 else "#ef4444"
    sign  = "+" if r >= 0 else ""
    return f"<span style='color:{color};font-weight:600'>{sign}{r:.1f}%</span>"


def _fmt_returns(r7, r30, r90) -> str:
    return " / ".join([_fmt_ret_single(r7), _fmt_ret_single(r30), _fmt_ret_single(r90)])


def _fmt_value(shares, price) -> str:
    try:
        v = float(shares) * float(price)
        return "—" if v == 0 else f"${v:,.0f}"
    except Exception:
        return "—"


def _fmt_shares(s) -> str:
    try:
        return f"{float(s):,.0f}"
    except Exception:
        return "—"


def _strip_cik(s: str) -> str:
    return _CIK_RE.sub("", s).strip()


def _build_filing_url(adsh: str, cik: str) -> str:
    clean = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean}/{adsh}-index.htm"


def _build_txt_url(adsh: str, cik: str) -> str:
    clean = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean}/{adsh}.txt"


def _resolve_title(raw: str) -> str:
    """Return 'Director' if title is blank, 'See Remarks', or similar."""
    raw = raw.strip()
    if not raw or SEE_RMKS_RE.search(raw):
        return "Director"
    return raw


# ── SEC .txt fetch — all fields in one request (TTL 10 min) ───────────────────
@st.cache_data(ttl=600, show_spinner=False)
def _fetch_filing_data(adsh: str, cik: str) -> dict:
    default = {
        "transaction_type": "⚪ Other",
        "exec_title":       "Director",
        "shares":           None,
        "price_per_share":  None,
        "transaction_date": None,
    }
    try:
        resp = requests.get(_build_txt_url(adsh, cik), headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return default
        text = resp.text

        # ── Transaction code: scan ALL codes, prioritise P > S > A > others ──
        raw_codes = [c.strip() for c in _CODE_RE.findall(text)]
        for priority in ("P", "S", "A"):
            if priority in raw_codes:
                default["transaction_type"] = TRANSACTION_LABELS[priority]
                break

        # ── Officer title with "See Remarks" fallback ─────────────────────────
        m = _TITLE_RE.search(text)
        default["exec_title"] = _resolve_title(m.group(1) if m else "")

        # ── Shares & price ────────────────────────────────────────────────────
        m = _SHARES_RE.search(text)
        if m:
            try:
                default["shares"] = float(m.group(1).strip())
            except ValueError:
                pass

        m = _PRICE_RE.search(text)
        if m:
            try:
                default["price_per_share"] = float(m.group(1).strip())
            except ValueError:
                pass

        # ── Transaction date ──────────────────────────────────────────────────
        m = _TDATE_RE.search(text)
        if m:
            default["transaction_date"] = m.group(1).strip()

        return default
    except Exception:
        return default


# ── Ticker + sector via Yahoo Finance search (TTL 1 hr) ───────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _lookup_ticker_and_sector(company_name: str) -> tuple[str, str]:
    try:
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={requests.utils.quote(company_name)}&quotesCount=1&newsCount=0"
        )
        resp   = requests.get(url, headers=HEADERS, timeout=8)
        quotes = resp.json().get("quotes", [])
        if quotes and quotes[0].get("quoteType") == "EQUITY":
            q = quotes[0]
            return q.get("symbol", ""), q.get("sectorDisp", q.get("sector", "Unknown"))
    except Exception:
        pass
    return "", "Unknown"


# ── Stock return calculation (TTL 1 hr) ───────────────────────────────────────
def _history_with_fallback(ticker: str, start: str, end: str):
    """Fetch yfinance history; if empty and ticker has an exchange suffix, retry without it."""
    hist = yf.Ticker(ticker).history(start=start, end=end)
    if hist.empty and "." in ticker:
        base_ticker = ticker.split(".")[0]
        hist = yf.Ticker(base_ticker).history(start=start, end=end)
    return hist


@st.cache_data(ttl=3600, show_spinner=False)
def _get_returns(ticker: str, base_date_str: str) -> tuple:
    try:
        base = pd.to_datetime(base_date_str).date()
        end  = min(base + timedelta(days=100), date.today())
        hist = _history_with_fallback(ticker, str(base), str(end))
        if hist.empty:
            return None, None, None
        base_price = hist["Close"].iloc[0]

        def _ret(days: int):
            target = base + timedelta(days=days)
            if target >= date.today():
                return None
            future = hist[hist.index.date >= target]
            if future.empty:
                return None
            return round((future["Close"].iloc[0] / base_price - 1) * 100, 2)

        return _ret(7), _ret(30), _ret(90)
    except Exception:
        return None, None, None


# ── Stock chart data (TTL 1 hr) ───────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _get_stock_chart_data(ticker: str, base_date_str: str) -> pd.DataFrame:
    try:
        base = pd.to_datetime(base_date_str).date()
        end  = min(base + timedelta(days=35), date.today())
        hist = _history_with_fallback(ticker, str(base), str(end))
        if hist.empty:
            return pd.DataFrame()
        hist = hist.reset_index()[["Date", "Close"]]
        hist["Date"] = pd.to_datetime(hist["Date"]).dt.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


# ── EDGAR filing fetch (TTL 5 min) ────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def fetch_filings(start_dt: str, end_dt: str) -> pd.DataFrame:
    hits, page, per_page = [], 0, 10
    while len(hits) < MAX_RESULTS:
        params = {
            "q": '"form 4"', "forms": "4", "dateRange": "custom",
            "startdt": start_dt, "enddt": end_dt, "from": page * per_page,
        }
        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            st.error(f"EDGAR API error: {e}")
            break
        batch = data.get("hits", {}).get("hits", [])
        if not batch:
            break
        hits.extend(batch)
        page += 1
        if len(batch) < per_page:
            break
    return _parse_hits(hits)


def _parse_hits(hits: list) -> pd.DataFrame:
    rows = []
    for h in hits:
        s     = h.get("_source", {})
        adsh  = s.get("adsh", "")
        names = s.get("display_names", [])

        exec_name = _strip_cik(names[0]) if len(names) > 0 else "—"
        company   = _strip_cik(names[1]) if len(names) > 1 else "—"

        locs     = [l for l in s.get("biz_locations", []) if l]
        location = locs[0] if locs else (", ".join(s.get("biz_states", [])) or "—")

        cik_list = s.get("ciks", [])
        cik = str(int(cik_list[1])) if len(cik_list) > 1 else (
              str(int(cik_list[0])) if cik_list else "")

        rows.append({
            "Filed":             s.get("file_date", ""),
            "Executive / Filer": exec_name or "—",
            "Company":           company or "—",
            "Location":          location,
            "Accession No":      adsh,
            "CIK":               cik,
            "Filing URL":        _build_filing_url(adsh, cik) if adsh and cik else "",
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["Filed"] = pd.to_datetime(df["Filed"], errors="coerce")
    df.sort_values("Filed", ascending=False, inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ── Phase 1: SEC .txt enrichment (parallel) ───────────────────────────────────
def enrich_with_filing_data(df: pd.DataFrame) -> pd.DataFrame:
    results: dict[str, dict] = {}
    pairs = [(r["Accession No"], r["CIK"]) for _, r in df.iterrows()
             if r["Accession No"] and r["CIK"]]

    with ThreadPoolExecutor(max_workers=12) as ex:
        fmap = {ex.submit(_fetch_filing_data, adsh, cik): adsh for adsh, cik in pairs}
        for fut in as_completed(fmap):
            results[fmap[fut]] = fut.result()

    df = df.copy()
    get = lambda a, k, d: results.get(a, {}).get(k, d)
    df["Transaction Type"] = df["Accession No"].map(lambda a: get(a, "transaction_type", "⚪ Other"))
    df["Exec Title"]       = df["Accession No"].map(lambda a: get(a, "exec_title",       "Director"))
    df["Shares"]           = df["Accession No"].map(lambda a: get(a, "shares",           None))
    df["Price Per Share"]  = df["Accession No"].map(lambda a: get(a, "price_per_share",  None))
    df["Transaction Date"] = df["Accession No"].map(lambda a: get(a, "transaction_date", None))
    return df


# ── Phase 2: Market data enrichment (parallel) ────────────────────────────────
def enrich_with_market_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ticker + sector per unique company
    unique_cos  = df["Company"].dropna().unique().tolist()
    ticker_map: dict[str, str] = {}
    sector_map: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=10) as ex:
        fmap = {ex.submit(_lookup_ticker_and_sector, co): co for co in unique_cos}
        for fut in as_completed(fmap):
            co = fmap[fut]
            t, s = fut.result()
            ticker_map[co] = t
            sector_map[co] = s

    df["Ticker"] = df["Company"].map(ticker_map).fillna("")
    df["Sector"] = df["Company"].map(sector_map).fillna("Unknown")

    # Returns for Buy rows only
    df["7d Return"] = df["30d Return"] = df["90d Return"] = None

    buy_mask = (df["Transaction Type"] == "🟢 Buy") & df["Ticker"].astype(bool)
    buy_rows = df[buy_mask]

    if not buy_rows.empty:
        pairs = list(dict.fromkeys(
            (row["Ticker"], row["Transaction Date"] or str(row["Filed"].date()))
            for _, row in buy_rows.iterrows() if row["Ticker"]
        ))
        ret_results: dict[tuple, tuple] = {}
        with ThreadPoolExecutor(max_workers=10) as ex:
            fmap2 = {ex.submit(_get_returns, t, d): (t, d) for t, d in pairs}
            for fut in as_completed(fmap2):
                ret_results[fmap2[fut]] = fut.result()

        for idx, row in buy_rows.iterrows():
            key = (row["Ticker"], row["Transaction Date"] or str(row["Filed"].date()))
            r7, r30, r90 = ret_results.get(key, (None, None, None))
            df.at[idx, "7d Return"]  = r7
            df.at[idx, "30d Return"] = r30
            df.at[idx, "90d Return"] = r90

    return df


# ══════════════════════════════════════════════════════════════════════════════
# ── Sidebar part 1: Date range + refresh (before data fetch) ─────────────────
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Filters")
    st.markdown("---")
    col_s, col_e = st.columns(2)
    with col_s:
        start_date = st.date_input("Start date", value=date(2025, 1, 1))
    with col_e:
        end_date = st.date_input("End date", value=date.today())

    st.markdown("---")
    refresh = st.button("🔄 Refresh data", use_container_width=True)
    if refresh:
        st.cache_data.clear()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='font-size:2.2rem; font-weight:700; margin-bottom:4px;'>"
    "📈 SEC Insider Trading Monitor"
    "</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='color:#6b7280; margin-top:0;'>Real-time Form 4 filings · "
    f"{start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}</p>",
    unsafe_allow_html=True,
)
st.markdown("---")


# ── Fetch & enrich ────────────────────────────────────────────────────────────
with st.spinner("Fetching filings from SEC EDGAR…"):
    df = fetch_filings(str(start_date), str(end_date))

if df.empty:
    st.warning("No filings found for the selected date range.")
    st.stop()

with st.spinner(f"Parsing transaction details for {len(df)} filings…"):
    df = enrich_with_filing_data(df)

with st.spinner("Fetching market data (tickers, sectors, returns)…"):
    df = enrich_with_market_data(df)


# ── Sidebar part 2: Filter controls (populated from enriched data) ─────────────
with st.sidebar:
    txn_filter = st.multiselect(
        "Transaction type", options=TRANSACTION_ORDER,
        default=[], placeholder="All types",
    )

    # Ticker selectbox with autocomplete
    all_tickers = sorted(t for t in df["Ticker"].dropna().unique() if t)
    ticker_label_map = {
        t: f"{t} — {df[df['Ticker'] == t]['Company'].iloc[0][:28]}"
        for t in all_tickers
    }
    ticker_options = [""] + all_tickers
    ticker_sel = st.selectbox(
        "Filter by ticker",
        options=ticker_options,
        format_func=lambda x: "All tickers" if x == "" else ticker_label_map.get(x, x),
    )
    ticker_filter = ticker_sel or ""

    # Company selectbox with autocomplete
    all_companies = sorted(df["Company"].dropna().unique().tolist())
    company_options = [""] + all_companies
    company_sel = st.selectbox(
        "Filter by company",
        options=company_options,
        format_func=lambda x: "All companies" if x == "" else x,
    )
    company_filter = company_sel or ""

    # Location text filter (kept as free-text — many distinct values)
    location_filter = st.text_input("Filter by location", placeholder="e.g. CA, NY, TX")

    st.markdown("---")
    st.markdown(
        "<small style='color:#6b7280'>Data: SEC EDGAR & Yahoo Finance.<br>"
        "Filings: 5 min · Filing data: 10 min · Market: 1 hr.</small>",
        unsafe_allow_html=True,
    )


# ── Apply filters ─────────────────────────────────────────────────────────────
filtered = df.copy()
if txn_filter:
    filtered = filtered[filtered["Transaction Type"].isin(txn_filter)]
if ticker_filter:
    filtered = filtered[filtered["Ticker"] == ticker_filter]
if company_filter:
    filtered = filtered[filtered["Company"] == company_filter]
if location_filter.strip():
    filtered = filtered[
        filtered["Location"].str.contains(location_filter.strip(), case=False, na=False)
    ]

# Notable flag: Chief/CEO/CFO/President + Buy
filtered = filtered.copy()
filtered["Notable"] = (
    (filtered["Transaction Type"] == "🟢 Buy") &
    filtered["Exec Title"].apply(lambda t: bool(NOTABLE_RE.search(str(t))))
)


# ── KPI metrics ───────────────────────────────────────────────────────────────
total        = len(filtered)
companies    = filtered["Company"].nunique()
latest       = filtered["Filed"].max()
latest_str   = latest.strftime("%b %d, %Y") if pd.notna(latest) else "—"
buys         = (filtered["Transaction Type"] == "🟢 Buy").sum()
sells        = (filtered["Transaction Type"] == "🔴 Sell").sum()
notable_buys = filtered["Notable"].sum()
ratio_str    = f"{buys/sells:.1f}:1" if sells > 0 else ("∞" if buys > 0 else "—")
sectors_n    = filtered[filtered["Sector"] != "Unknown"]["Sector"].nunique()

m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Total Filings",    f"{total:,}")
m2.metric("Unique Companies", f"{companies:,}")
m3.metric("Buy / Sell Ratio", ratio_str, help=f"{buys} buys · {sells} sells")
m4.metric("🚨 Notable Buys",  f"{notable_buys:,}", help="CEO/CFO/Chief + Buy")
m5.metric("Latest Filing",    latest_str)
m6.metric("Sectors Covered",  str(sectors_n))

st.markdown("---")


# ── Charts row 1 ─────────────────────────────────────────────────────────────
_base_layout = dict(
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor="#161b22", paper_bgcolor="#161b22", height=260,
)

col_area, col_pie, col_bar = st.columns(3)

with col_area:
    st.markdown("**Filings Over Time**")
    daily = (
        filtered.set_index("Filed").resample("D")["Accession No"]
        .count().reset_index()
        .rename(columns={"Filed": "Date", "Accession No": "Filings"})
    )
    fig = px.area(daily, x="Date", y="Filings",
                  color_discrete_sequence=["#38bdf8"], template="plotly_dark")
    fig.update_layout(**_base_layout,
                      xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#1f2937"))
    st.plotly_chart(fig, use_container_width=True)

with col_pie:
    st.markdown("**Transaction Breakdown**")
    txn_counts = (
        filtered["Transaction Type"].value_counts()
        .reindex(TRANSACTION_ORDER, fill_value=0).reset_index()
    )
    txn_counts.columns = ["Type", "Count"]
    txn_counts = txn_counts[txn_counts["Count"] > 0]
    fig = px.pie(txn_counts, names="Type", values="Count", color="Type",
                 color_discrete_map=PIE_COLORS, template="plotly_dark", hole=0.45)
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(**_base_layout, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col_bar:
    st.markdown("**Top 10 Locations**")
    top_locs = filtered["Location"].value_counts().head(10).reset_index()
    top_locs.columns = ["Location", "Filings"]
    fig = px.bar(top_locs, x="Filings", y="Location", orientation="h",
                 color="Filings", color_continuous_scale="Blues", template="plotly_dark")
    fig.update_layout(**_base_layout,
                      yaxis=dict(autorange="reversed", showgrid=False),
                      xaxis=dict(gridcolor="#1f2937"), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

# ── Charts row 2: Sector breakdown ────────────────────────────────────────────
sector_df = filtered[
    filtered["Sector"].notna() &
    (filtered["Sector"] != "Unknown") &
    filtered["Transaction Type"].isin(["🟢 Buy", "🔴 Sell"])
]
if not sector_df.empty:
    st.markdown("**Insider Activity by Sector**")
    sc = sector_df.groupby(["Sector", "Transaction Type"]).size().reset_index(name="Count")
    fig = px.bar(sc, x="Sector", y="Count", color="Transaction Type",
                 barmode="group", color_discrete_map=PIE_COLORS, template="plotly_dark")
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="#161b22", paper_bgcolor="#161b22", height=280,
        xaxis=dict(gridcolor="#1f2937"), yaxis=dict(gridcolor="#1f2937"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ── Table controls ────────────────────────────────────────────────────────────
tbl_left, tbl_right = st.columns([3, 1])
with tbl_left:
    badge_html = f"<span class='badge'>{total} results</span>"
    if notable_buys:
        badge_html += f" &nbsp;<span class='badge badge-alert'>🚨 {notable_buys} notable</span>"
    st.markdown(f"**Recent Form 4 Filings** &nbsp; {badge_html}", unsafe_allow_html=True)

with tbl_right:
    export_cols = [
        "Filed", "Transaction Type", "Exec Title", "Executive / Filer",
        "Company", "Ticker", "Sector", "Shares", "Price Per Share",
        "7d Return", "30d Return", "90d Return", "Location", "Filing URL",
    ]
    export_df = filtered[export_cols].copy()
    export_df["Filed"] = export_df["Filed"].dt.strftime("%Y-%m-%d")
    st.download_button(
        "⬇ Download CSV", export_df.to_csv(index=False),
        file_name="insider_trades.csv", mime="text/csv",
        use_container_width=True,
    )

st.markdown("<br>", unsafe_allow_html=True)


# ── Filing table ──────────────────────────────────────────────────────────────
display = filtered.head(200).copy()
display["Filed_str"] = display["Filed"].dt.strftime("%Y-%m-%d").fillna("—")

rows_html = ""
for _, row in display.iterrows():
    notable  = row.get("Notable", False)
    tr_class = "notable" if notable else ""
    flag     = "🚨 " if notable else ""
    url      = row["Filing URL"]
    link     = f'<a href="{url}" target="_blank">🔗</a>' if url else "—"

    ticker   = row.get("Ticker", "") or ""
    ticker_html = f"<span class='ticker-pill'>{ticker}</span>" if ticker else ""

    sector   = row.get("Sector", "Unknown") or "Unknown"
    sector_lbl = sector if sector != "Unknown" else "—"

    # Company + ticker merged cell
    co_cell = f"{row['Company']}{ticker_html}"

    rows_html += (
        f'<tr class="{tr_class}">'
        f"<td class='col-date'>{row['Filed_str']}</td>"
        f"<td class='col-txn'>{row['Transaction Type']}</td>"
        f"<td class='col-exec'>{flag}<strong>{row['Executive / Filer']}</strong></td>"
        f"<td class='col-title'>{row['Exec Title']}</td>"
        f"<td class='col-co'>{co_cell}</td>"
        f"<td class='col-sector'>{sector_lbl}</td>"
        f"<td class='col-shares'>{_fmt_shares(row['Shares'])}</td>"
        f"<td class='col-value'>{_fmt_value(row['Shares'], row['Price Per Share'])}</td>"
        f"<td class='col-ret'>{_fmt_returns(row['7d Return'], row['30d Return'], row['90d Return'])}</td>"
        f"<td class='col-link'>{link}</td>"
        f"</tr>"
    )

table_html = f"""
<div style="overflow-x:hidden; max-height:560px; overflow-y:auto;
            border:1px solid #21262d; border-radius:10px; width:100%;">
  <table class="filing-table">
    <colgroup>
      <col class="col-date">  <col class="col-txn">   <col class="col-exec">
      <col class="col-title"> <col class="col-co">    <col class="col-sector">
      <col class="col-shares"><col class="col-value"> <col class="col-ret">
      <col class="col-link">
    </colgroup>
    <thead><tr>
      <th class="col-date">Date</th>
      <th class="col-txn">Type</th>
      <th class="col-exec">Executive</th>
      <th class="col-title">Title</th>
      <th class="col-co">Company</th>
      <th class="col-sector">Sector</th>
      <th class="col-shares">Shares</th>
      <th class="col-value">Est. Value</th>
      <th class="col-ret">7d / 30d / 90d Returns</th>
      <th class="col-link">Link</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
"""
st.markdown(table_html, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<small style='color:#6b7280'>Returns from transaction date · "
    f"Last fetched: {datetime.now().strftime('%H:%M:%S')}</small>",
    unsafe_allow_html=True,
)


# ── Returns summary ───────────────────────────────────────────────────────────
buy_rows    = filtered[filtered["Transaction Type"] == "🟢 Buy"]
has_returns = buy_rows[["7d Return", "30d Return", "90d Return"]].notna().any().any()

if has_returns:
    st.markdown("---")
    st.markdown("**📊 Historical Performance — Buy Transactions**")

    def _kpi_ret(label, val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return f"**{label}:** —"
        color = "#22c55e" if val >= 0 else "#ef4444"
        sign  = "+" if val >= 0 else ""
        return f"**{label}:** <span style='color:{color}'>{sign}{val:.2f}%</span>"

    ra, rb, rc = st.columns(3)
    ra.markdown(_kpi_ret("Avg 7-day",  buy_rows["7d Return"].mean()),  unsafe_allow_html=True)
    rb.markdown(_kpi_ret("Avg 30-day", buy_rows["30d Return"].mean()), unsafe_allow_html=True)
    rc.markdown(_kpi_ret("Avg 90-day", buy_rows["90d Return"].mean()), unsafe_allow_html=True)


# ── Stock Price Explorer ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("**📉 Stock Price Explorer** — 30 days post-transaction")

chart_df = filtered[filtered["Ticker"].astype(bool)][
    ["Company", "Ticker", "Transaction Date", "Filed"]
].copy()
chart_df["Label"] = (
    chart_df["Company"].str[:32] + " (" + chart_df["Ticker"] + ") — " +
    chart_df["Transaction Date"].fillna(chart_df["Filed"].dt.strftime("%Y-%m-%d"))
)

if chart_df.empty:
    st.info("No tickers resolved for the current filter — try a broader date range.")
else:
    selected = st.selectbox("Select a filing", options=chart_df["Label"].tolist(), index=0)
    sel      = chart_df[chart_df["Label"] == selected].iloc[0]
    sel_ticker = sel["Ticker"]
    sel_date   = sel["Transaction Date"] or str(sel["Filed"].date())

    with st.spinner(f"Loading {sel_ticker} chart…"):
        chart_data = _get_stock_chart_data(sel_ticker, sel_date)

    if chart_data.empty:
        st.warning(f"No price data for {sel_ticker} from {sel_date}.")
    else:
        base_price = chart_data["Close"].iloc[0]
        fig_chart  = go.Figure()
        fig_chart.add_trace(go.Scatter(
            x=chart_data["Date"], y=chart_data["Close"],
            mode="lines+markers", line=dict(color="#38bdf8", width=2),
            marker=dict(size=4), name=sel_ticker,
        ))
        fig_chart.add_vline(
            x=int(pd.to_datetime(sel_date).timestamp() * 1000),
            line_dash="dash", line_color="#f59e0b",
            annotation_text="Transaction date", annotation_font_color="#f59e0b",
        )
        fig_chart.add_hline(
            y=base_price, line_dash="dot", line_color="#6b7280",
            annotation_text=f"Entry ${base_price:.2f}", annotation_font_color="#6b7280",
        )
        fig_chart.update_layout(
            template="plotly_dark",
            plot_bgcolor="#161b22", paper_bgcolor="#161b22",
            margin=dict(l=0, r=0, t=30, b=0), height=320,
            title=dict(text=f"{sel_ticker} — 30 days post-transaction", font=dict(size=14)),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#1f2937", tickprefix="$"),
            showlegend=False,
        )
        st.plotly_chart(fig_chart, use_container_width=True)
