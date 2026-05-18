import html as _html
import json
import re as _re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global font ── */
*, *::before, *::after {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Animated gradient top border ── */
@keyframes gradBorder {
    0%   { background-position: 0% 0%; }
    100% { background-position: 200% 0%; }
}
body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 25%, #ec4899 50%, #f59e0b 75%, #3b82f6 100%);
    background-size: 200% 100%;
    animation: gradBorder 5s linear infinite;
    z-index: 99999;
    pointer-events: none;
}

/* ── Background with subtle dot grid ── */
.stApp {
    background-color: #0e1117;
    color: #fafafa;
    background-image: radial-gradient(rgba(255,255,255,0.025) 1px, transparent 1px);
    background-size: 28px 28px;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #111827;
    border-right: 1px solid #1f2937;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] label {
    text-transform: uppercase !important;
    font-size: 10px !important;
    letter-spacing: 0.1em !important;
    color: #6b7280 !important;
    font-weight: 600 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #1e3a5f 0%, #1e4a76 100%) !important;
    border: 1px solid #2d5a8e !important;
    color: #bae6fd !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1e4a76 0%, #1d5fa0 100%) !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 0 16px rgba(56,189,248,0.3) !important;
    color: #e0f2fe !important;
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #1e3a5f 0%, #1e4a76 100%) !important;
    border: 1px solid #2d5a8e !important;
    color: #bae6fd !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #1e4a76 0%, #1d5fa0 100%) !important;
    border-color: #38bdf8 !important;
    box-shadow: 0 0 16px rgba(56,189,248,0.3) !important;
}

/* ── KPI Cards ── */
.kpi-grid { display: flex; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.kpi-card {
    flex: 1; min-width: 120px;
    background-color: #161b22;
    border: 1px solid #21262d;
    border-top: none;
    border-radius: 10px;
    padding: 16px 20px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.25s ease, box-shadow 0.25s ease;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, #3b82f6, #8b5cf6);
    border-radius: 10px 10px 0 0;
}
.kpi-card:hover {
    border-color: #2d3748;
    box-shadow: 0 0 20px rgba(56,189,248,0.12), inset 0 0 20px rgba(56,189,248,0.03);
}
.kpi-label {
    color: #6b7280; font-size: 11px; font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.kpi-value {
    color: #f1f5f9; font-size: 1.75rem; font-weight: 800;
    font-variant-numeric: tabular-nums; line-height: 1.1;
    letter-spacing: -0.02em;
}
.kpi-desc { color: #4b5563; font-size: 10.5px; margin-top: 5px; line-height: 1.4; }
.kpi-subtext { color: #4b5563; font-size: 10px; margin-top: 4px; }

/* ── Live pulse dot ── */
@keyframes livePulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
    50%       { opacity: 0.85; box-shadow: 0 0 0 5px rgba(34,197,94,0); }
}
.live-dot {
    display: inline-block; width: 7px; height: 7px;
    background: #22c55e; border-radius: 50%;
    margin-right: 5px; vertical-align: middle;
    animation: livePulse 2s ease-in-out infinite;
}

/* ── Skeleton shimmer ── */
@keyframes shimmer {
    0%   { background-position: -600px 0; }
    100% { background-position:  600px 0; }
}
.shimmer {
    background: linear-gradient(90deg, #1c2230 25%, #2a3441 50%, #1c2230 75%);
    background-size: 1200px 100%;
    animation: shimmer 1.6s ease-in-out infinite;
    border-radius: 8px;
}
.skel-kpi-grid { display: flex; gap: 12px; margin-bottom: 8px; }
.skel-kpi      { flex: 1; height: 80px; border-radius: 10px; }
.skel-charts   { display: flex; gap: 12px; margin: 0 0 16px; }
.skel-chart    { flex: 1; height: 260px; }
.skel-table    { width: 100%; height: 380px; }

/* ── Chart entry animation ── */
@keyframes chartFadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
.stPlotlyChart { animation: chartFadeIn 0.55s ease-out both; }

/* ── Cursor glow ── */
#cursor-glow {
    position: fixed; width: 400px; height: 400px; border-radius: 50%;
    background: radial-gradient(circle,
        rgba(56,189,248,0.055) 0%, rgba(99,102,241,0.03) 45%, transparent 70%);
    pointer-events: none;
    transform: translate(-50%, -50%);
    z-index: 0; will-change: left, top;
    transition: left 0.07s linear, top 0.07s linear;
}

/* ── Table ── */
.filing-table {
    width: 100%; border-collapse: collapse;
    font-size: 12.5px; table-layout: fixed;
}
.filing-table th {
    background-color: #161b22; color: #60a5fa;
    padding: 11px 10px; text-align: left;
    border-bottom: 1px solid #2d3748;
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.1em;
    white-space: nowrap; overflow: hidden;
    position: sticky; top: 0; z-index: 1;
}
.filing-table td {
    padding: 8px 10px; border-bottom: 1px solid #1a2332;
    vertical-align: middle; overflow: hidden; text-overflow: ellipsis;
    transition: padding 0.15s ease, background-color 0.15s ease;
}
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

/* Alternating row shading */
.filing-table tbody tr:nth-child(even) td { background-color: #0b1018; }
.filing-table tbody tr:nth-child(odd)  td { background-color: #0e1117; }

.filing-table tr:hover td {
    background-color: #1a2332 !important;
    padding-top: 11px; padding-bottom: 11px;
}
.filing-table tr:hover td:first-child { border-left: 3px solid #38bdf8; }
.filing-table tr.notable td { background-color: #0d1f0f !important; }
.filing-table tr.notable td:first-child { border-left: 3px solid #22c55e; }
.filing-table tr.notable:hover td:first-child { border-left: 3px solid #38bdf8; }
.filing-table a { color: #38bdf8; text-decoration: none; font-weight: 500; }
.filing-table a:hover { text-decoration: underline; }
.exec-name { font-weight: 700; color: #f1f5f9; }
.co-name   { color: #64748b; font-size: 12px; }

/* ── Transaction type pills ── */
.txn-pill {
    display: inline-flex; align-items: center; justify-content: center;
    padding: 2px 9px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
    white-space: nowrap;
}
.txn-buy   { background: rgba(34,197,94,0.12);  color: #4ade80; border: 1px solid rgba(34,197,94,0.25); }
.txn-sell  { background: rgba(239,68,68,0.12);  color: #f87171; border: 1px solid rgba(239,68,68,0.25); }
.txn-award { background: rgba(59,130,246,0.12); color: #60a5fa; border: 1px solid rgba(59,130,246,0.25); }
.txn-other { background: rgba(107,114,128,0.12);color: #9ca3af; border: 1px solid rgba(107,114,128,0.25); }

/* ── Ticker pill ── */
.ticker-pill {
    display: inline-block; background-color: rgba(139,92,246,0.15); color: #a78bfa;
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: 4px; padding: 1px 5px; font-size: 10px;
    font-weight: 700; letter-spacing: 0.05em;
    margin-left: 4px; vertical-align: middle;
}

/* ── Badges ── */
.badge {
    display: inline-block; background-color: #1e3a5f; color: #60a5fa;
    border-radius: 12px; padding: 2px 10px; font-size: 11px; font-weight: 600;
}
.badge-alert { background-color: #422006; color: #fb923c; }

/* ── SEC filing link button ── */
.filing-link-btn {
    display: inline-block;
    padding: 2px 8px;
    border: 1px solid rgba(56,189,248,0.4);
    border-radius: 999px;
    color: #38bdf8 !important;
    font-size: 10px; font-weight: 700; letter-spacing: 0.05em;
    text-decoration: none !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
    white-space: nowrap;
}
.filing-link-btn:hover {
    border-color: #38bdf8;
    box-shadow: 0 0 8px rgba(56,189,248,0.35);
    text-decoration: none !important;
}
.filing-link-btn:active { transform: scale(0.92); }

/* ── Toast ── */
#toast-container {
    position: fixed; bottom: 28px; right: 28px;
    z-index: 99999; display: flex; flex-direction: column;
    gap: 8px; pointer-events: none;
}
.st-toast {
    background: #1e2530; border: 1px solid #374151;
    border-left: 3px solid #38bdf8; border-radius: 10px;
    padding: 12px 18px; font-size: 13px; color: #f1f5f9;
    box-shadow: 0 8px 24px rgba(0,0,0,0.5); min-width: 230px;
    opacity: 0; transform: translateX(20px);
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.st-toast.toast-show { opacity: 1; transform: translateX(0); }

@media (prefers-reduced-motion: reduce) {
    body::before      { animation: none !important; }
    .stPlotlyChart    { animation: none !important; }
    .shimmer          { animation: none !important; }
    #cursor-glow      { transition: none !important; display: none !important; }
    .st-toast         { transition: none !important; }
    .filing-table td  { transition: none !important; }
    .live-dot         { animation: none !important; }
}
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
TXN_PILL_HTML = {
    "🟢 Buy":   "<span class='txn-pill txn-buy'>Buy</span>",
    "🔴 Sell":  "<span class='txn-pill txn-sell'>Sell</span>",
    "🔵 Award": "<span class='txn-pill txn-award'>Award</span>",
    "⚪ Other": "<span class='txn-pill txn-other'>Other</span>",
}
NOTABLE_RE  = _re.compile(r"\b(Chief|CEO|CFO|President)\b", _re.IGNORECASE)
SEE_RMKS_RE = _re.compile(r"see\s+remarks", _re.IGNORECASE)

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
    raw = raw.strip()
    if not raw or SEE_RMKS_RE.search(raw):
        return "Director"
    return raw


# ── SEC .txt fetch (TTL 10 min) ───────────────────────────────────────────────
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

        raw_codes = [c.strip() for c in _CODE_RE.findall(text)]
        for priority in ("P", "S", "A"):
            if priority in raw_codes:
                default["transaction_type"] = TRANSACTION_LABELS[priority]
                break

        m = _TITLE_RE.search(text)
        default["exec_title"] = _resolve_title(m.group(1) if m else "")

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

        m = _TDATE_RE.search(text)
        if m:
            default["transaction_date"] = m.group(1).strip()

        return default
    except Exception:
        return default


# ── Ticker + sector via Yahoo Finance (TTL 1 hr) ──────────────────────────────
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


# ── yfinance helpers ──────────────────────────────────────────────────────────
def _history_with_fallback(ticker: str, start: str, end: str):
    hist = yf.Ticker(ticker).history(start=start, end=end)
    if hist.empty and "." in ticker:
        hist = yf.Ticker(ticker.split(".")[0]).history(start=start, end=end)
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


@st.cache_data(ttl=3600, show_spinner=False)
def _get_sparkline_prices(ticker: str, ref_date_str: str) -> list:
    """Last ≤30 closes ending at ref_date for the hover sparkline tooltip."""
    try:
        ref   = pd.to_datetime(ref_date_str).date()
        start = ref - timedelta(days=50)
        hist  = _history_with_fallback(ticker, str(start), str(ref + timedelta(days=1)))
        if hist.empty:
            return []
        return [round(float(c), 2) for c in hist["Close"].tail(30).tolist()]
    except Exception:
        return []


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


# ── Cursor glow (injected once per page session) ──────────────────────────────
components.html("""
<script>
(function() {
  var p = window.parent;
  if (!p || p === window) return;
  if (p.document.getElementById('cursor-glow')) return;
  var g = p.document.createElement('div');
  g.id = 'cursor-glow';
  p.document.body.appendChild(g);
  if (p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  p.document.addEventListener('mousemove', function(e) {
    g.style.left = e.clientX + 'px';
    g.style.top  = e.clientY + 'px';
  });
})();
</script>
""", height=0)

# ── Sidebar gradient divider helper ───────────────────────────────────────────
_GRAD_DIV = (
    '<div style="height:1px;background:linear-gradient(90deg,transparent,'
    '#3b82f6 30%,#8b5cf6 70%,transparent);margin:12px 0;"></div>'
)

# ══════════════════════════════════════════════════════════════════════════════
# ── Sidebar part 1 ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div style='font-size:13px;font-weight:700;letter-spacing:0.08em;"
        "color:#94a3b8;text-transform:uppercase;padding:4px 0 8px;'>⚙️ Filters</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    col_s, col_e = st.columns(2)
    with col_s:
        start_date = st.date_input("📅 Start", value=date(2025, 1, 1))
    with col_e:
        end_date = st.date_input("📅 End", value=date.today())
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    refresh = st.button("🔄 Refresh Data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.session_state["_refreshed"] = True

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='font-size:2.6rem;font-weight:800;margin-bottom:4px;line-height:1.15;'>"
    "📈 <span style='background:linear-gradient(90deg,#ffffff 0%,#93c5fd 60%,#60a5fa 100%);"
    "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
    "background-clip:text;'>SEC Insider Trading Monitor</span>"
    "</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='color:#6b7280;margin-top:0;font-size:13.5px;'>"
    f"<span class='live-dot'></span>"
    f"<span style='color:#4ade80;font-weight:600;'>Real-time</span> Form 4 filings &nbsp;·&nbsp; "
    f"{start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ── Skeleton placeholders ─────────────────────────────────────────────────────
_SKEL_KPI = """
<div class="skel-kpi-grid">
  <div class="skel-kpi shimmer"></div><div class="skel-kpi shimmer"></div>
  <div class="skel-kpi shimmer"></div><div class="skel-kpi shimmer"></div>
  <div class="skel-kpi shimmer"></div><div class="skel-kpi shimmer"></div>
</div>"""

_SKEL_CHARTS = """
<div class="skel-charts">
  <div class="skel-chart shimmer"></div>
  <div class="skel-chart shimmer"></div>
  <div class="skel-chart shimmer"></div>
</div>"""

_SKEL_TABLE = '<div style="margin-top:16px;"><div class="skel-table shimmer"></div></div>'

kpi_placeholder    = st.empty()
charts_placeholder = st.empty()
table_placeholder  = st.empty()

kpi_placeholder.markdown(_SKEL_KPI,      unsafe_allow_html=True)
charts_placeholder.markdown(_SKEL_CHARTS, unsafe_allow_html=True)
table_placeholder.markdown(_SKEL_TABLE,   unsafe_allow_html=True)

# ── Fetch & enrich ────────────────────────────────────────────────────────────
with st.spinner("Fetching filings from SEC EDGAR…"):
    df = fetch_filings(str(start_date), str(end_date))

if df.empty:
    kpi_placeholder.empty()
    charts_placeholder.empty()
    table_placeholder.empty()
    st.warning("No filings found for the selected date range.")
    st.stop()

with st.spinner(f"Parsing transaction details for {len(df)} filings…"):
    df = enrich_with_filing_data(df)

with st.spinner("Fetching market data (tickers, sectors, returns)…"):
    df = enrich_with_market_data(df)

# ── Sidebar part 2 ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    txn_filter = st.multiselect(
        "🔀 Transaction Type", options=TRANSACTION_ORDER,
        default=[], placeholder="All types",
    )

    all_tickers = sorted(t for t in df["Ticker"].dropna().unique() if t)
    ticker_label_map = {
        t: f"{t} — {df[df['Ticker'] == t]['Company'].iloc[0][:28]}"
        for t in all_tickers
    }
    ticker_sel = st.selectbox(
        "📈 Ticker",
        options=[""] + all_tickers,
        format_func=lambda x: "All tickers" if x == "" else ticker_label_map.get(x, x),
    )
    ticker_filter = ticker_sel or ""

    all_companies = sorted(df["Company"].dropna().unique().tolist())
    company_sel = st.selectbox(
        "🏢 Company",
        options=[""] + all_companies,
        format_func=lambda x: "All companies" if x == "" else x,
    )
    company_filter = company_sel or ""

    location_filter = st.text_input("📍 Location", placeholder="e.g. CA, NY, TX")

    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    st.markdown(
        "<small style='color:#4b5563'>Data: SEC EDGAR & Yahoo Finance.<br>"
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

filtered = filtered.copy()
filtered["Notable"] = (
    (filtered["Transaction Type"] == "🟢 Buy") &
    filtered["Exec Title"].apply(lambda t: bool(NOTABLE_RE.search(str(t))))
)

# ── KPI values ────────────────────────────────────────────────────────────────
total        = len(filtered)
companies    = filtered["Company"].nunique()
latest       = filtered["Filed"].max()
latest_str   = latest.strftime("%b %d, %Y") if pd.notna(latest) else "—"
buys         = (filtered["Transaction Type"] == "🟢 Buy").sum()
sells        = (filtered["Transaction Type"] == "🔴 Sell").sum()
notable_buys = filtered["Notable"].sum()
sectors_n    = filtered[filtered["Sector"] != "Unknown"]["Sector"].nunique()

_ratio_num     = round(buys / sells, 1) if sells > 0 else None
_ratio_display = (
    f"{_ratio_num}:1" if _ratio_num is not None else ("∞" if buys > 0 else "—")
)

# ── Sparkline pre-fetch for hover tooltips ────────────────────────────────────
display = filtered.head(200).copy()
display["Filed_str"] = display["Filed"].dt.strftime("%Y-%m-%d").fillna("—")

_spark_pairs = list(dict.fromkeys(
    (r["Ticker"], r["Transaction Date"] or str(r["Filed"].date()))
    for _, r in display.iterrows()
    if r.get("Ticker")
))[:60]

spark_map: dict = {}
if _spark_pairs:
    with ThreadPoolExecutor(max_workers=8) as _sex:
        _sfmap = {_sex.submit(_get_sparkline_prices, t, d): (t, d) for t, d in _spark_pairs}
        for _sfut in as_completed(_sfmap):
            spark_map[_sfmap[_sfut]] = _sfut.result()

# ── Replace KPI skeleton ──────────────────────────────────────────────────────
_kpi_html = f"""
<div class="kpi-grid">
  <div class="kpi-card">
    <div class="kpi-label">Total Filings</div>
    <div class="kpi-value" data-target="{total}" data-type="int">0</div>
    <div class="kpi-desc">Form 4 filings tracked</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Unique Companies</div>
    <div class="kpi-value" data-target="{companies}" data-type="int">0</div>
    <div class="kpi-desc">Distinct issuers</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Buy / Sell Ratio</div>
    <div class="kpi-value" data-target="{_ratio_num or 0}" data-final="{_html.escape(_ratio_display)}" data-type="ratio">{"0" if _ratio_num else _ratio_display}</div>
    <div class="kpi-desc">{buys} buys · {sells} sells</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">🚨 Notable Buys</div>
    <div class="kpi-value" data-target="{notable_buys}" data-type="int">0</div>
    <div class="kpi-desc">CEO / CFO / Chief purchasing</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Latest Filing</div>
    <div class="kpi-value" data-type="date" style="font-size:1.25rem;opacity:0;">{latest_str}</div>
    <div class="kpi-desc">Most recent submission</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Sectors Covered</div>
    <div class="kpi-value" data-target="{sectors_n}" data-type="int">0</div>
    <div class="kpi-desc">Industries represented</div>
  </div>
</div>
"""
kpi_placeholder.markdown(_kpi_html, unsafe_allow_html=True)

# ── Counter animation ─────────────────────────────────────────────────────────
components.html("""
<script>
(function() {
  var p  = window.parent ? window.parent : window;
  var pd = p.document;
  var reduced = p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) {
    pd.querySelectorAll('.kpi-value[data-type="date"]').forEach(function(el) {
      el.style.opacity = '1';
    });
    return;
  }
  var DUR = 1500;
  function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
  setTimeout(function() {
    pd.querySelectorAll('.kpi-value[data-type="int"]').forEach(function(el) {
      var target = parseInt(el.dataset.target, 10);
      if (isNaN(target)) return;
      var t0 = p.performance.now();
      (function tick(now) {
        var prog = Math.min((now - t0) / DUR, 1);
        el.textContent = Math.round(easeOut(prog) * target).toLocaleString();
        if (prog < 1) p.requestAnimationFrame(tick);
      })(p.performance.now());
    });
    pd.querySelectorAll('.kpi-value[data-type="ratio"]').forEach(function(el) {
      var target = parseFloat(el.dataset.target);
      var final  = el.dataset.final;
      if (!target || isNaN(target)) return;
      var t0 = p.performance.now();
      (function tick(now) {
        var prog = Math.min((now - t0) / DUR, 1);
        el.textContent = prog < 1 ? (easeOut(prog) * target).toFixed(1) + ':1' : final;
        if (prog < 1) p.requestAnimationFrame(tick);
      })(p.performance.now());
    });
    pd.querySelectorAll('.kpi-value[data-type="date"]').forEach(function(el) {
      el.style.transition = 'opacity 0.9s ease-out';
      el.style.opacity = '1';
    });
  }, 120);
})();
</script>
""", height=0)

# ── Replace charts skeleton ───────────────────────────────────────────────────
_base_layout = dict(
    margin=dict(l=0, r=0, t=10, b=0),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=260,
)

with charts_placeholder.container():
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
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", height=280,
            xaxis=dict(gridcolor="#1f2937"), yaxis=dict(gridcolor="#1f2937"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

# ── Build table HTML ──────────────────────────────────────────────────────────
rows_html = ""
for _, row in display.iterrows():
    notable    = row.get("Notable", False)
    tr_class   = "notable" if notable else ""
    flag       = "🚨 " if notable else ""
    url        = row["Filing URL"]
    link       = f'<a href="{url}" target="_blank" rel="noopener noreferrer" class="filing-link-btn">SEC</a>' if url else "—"
    ticker     = row.get("Ticker", "") or ""
    ticker_html = f"<span class='ticker-pill'>{_html.escape(ticker)}</span>" if ticker else ""
    sector     = row.get("Sector", "Unknown") or "Unknown"
    sector_lbl = sector if sector != "Unknown" else "—"

    txn_type   = row["Transaction Type"]
    txn_cell   = TXN_PILL_HTML.get(
        txn_type,
        f"<span class='txn-pill txn-other'>{_html.escape(txn_type)}</span>"
    )
    co_cell    = f"<span class='co-name'>{_html.escape(row['Company'])}</span>{ticker_html}"

    _spark_key  = (ticker, row.get("Transaction Date") or str(row["Filed"].date())) if ticker else None
    _spark_json = json.dumps(spark_map.get(_spark_key, []))
    _est_val    = _fmt_value(row["Shares"], row["Price Per Share"])

    rows_html += (
        f'<tr class="{tr_class}"'
        f' data-spark=\'{_spark_json}\''
        f' data-ticker="{_html.escape(ticker)}"'
        f' data-exec-title="{_html.escape(str(row["Exec Title"]))}"'
        f' data-est-value="{_html.escape(_est_val)}"'
        f' data-sec-url="{_html.escape(url)}">'
        f"<td class='col-date'>{row['Filed_str']}</td>"
        f"<td class='col-txn'>{txn_cell}</td>"
        f"<td class='col-exec'>{flag}<span class='exec-name'>{_html.escape(str(row['Executive / Filer']))}</span></td>"
        f"<td class='col-title'>{_html.escape(str(row['Exec Title']))}</td>"
        f"<td class='col-co'>{co_cell}</td>"
        f"<td class='col-sector'>{_html.escape(sector_lbl)}</td>"
        f"<td class='col-shares'>{_fmt_shares(row['Shares'])}</td>"
        f"<td class='col-value'>{_est_val}</td>"
        f"<td class='col-ret'>{_fmt_returns(row['7d Return'], row['30d Return'], row['90d Return'])}</td>"
        f"<td class='col-link'>{link}</td>"
        f"</tr>"
    )

table_html = f"""
<div style="overflow-x:hidden; max-height:560px; overflow-y:auto;
            border:1px solid #1f2937; border-radius:12px; width:100%;">
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

# ── Replace table skeleton ────────────────────────────────────────────────────
with table_placeholder.container():
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
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"<small style='color:#4b5563'>Returns from transaction date · "
        f"Last fetched: {datetime.now().strftime('%H:%M:%S')}</small>",
        unsafe_allow_html=True,
    )

    # ── Returns summary ───────────────────────────────────────────────────────
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

    # ── Stock Price Explorer ──────────────────────────────────────────────────
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
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=30, b=0), height=320,
                title=dict(text=f"{sel_ticker} — 30 days post-transaction", font=dict(size=14)),
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor="#1f2937", tickprefix="$"),
                showlegend=False,
            )
            st.plotly_chart(fig_chart, use_container_width=True)

# ── Hover sparkline tooltip JS (fixed: delayed hide + pointer-events + above row) ──
components.html("""
<script>
(function() {
  var p  = window.parent ? window.parent : window;
  var pd = p.document;
  var hideTimer = null;

  // Build or reuse tooltip
  var tt = pd.getElementById('spark-tooltip');
  if (!tt) {
    tt = pd.createElement('div');
    tt.id = 'spark-tooltip';
    Object.assign(tt.style, {
      position:     'fixed',
      background:   '#1a2235',
      border:       '1px solid #2d3748',
      borderLeft:   '3px solid #38bdf8',
      borderRadius: '10px',
      padding:      '10px 14px',
      fontSize:     '12px',
      color:        '#f1f5f9',
      zIndex:       '99998',
      pointerEvents:'auto',
      opacity:      '0',
      transition:   'opacity 0.15s ease',
      boxShadow:    '0 12px 32px rgba(0,0,0,0.6)',
      minWidth:     '190px',
      maxWidth:     '240px'
    });
    pd.body.appendChild(tt);
  }

  // Tooltip stays open when hovered — cancel pending hide
  tt.addEventListener('mouseenter', function() { clearTimeout(hideTimer); });
  tt.addEventListener('mouseleave', function() {
    hideTimer = setTimeout(function() { tt.style.opacity = '0'; }, 150);
  });

  function makeSpark(prices, w, h) {
    if (!prices || prices.length < 3) return '';
    var mn = Math.min.apply(null, prices), mx = Math.max.apply(null, prices);
    var rng = mx - mn || 1;
    var pts = prices.map(function(v, i) {
      var x = (i / (prices.length - 1)) * w;
      var y = h - 4 - ((v - mn) / rng) * (h - 8);
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    var clr = prices[prices.length - 1] >= prices[0] ? '#4ade80' : '#f87171';
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h +
           '" style="display:block;margin-bottom:8px;">' +
           '<polyline points="' + pts + '" fill="none" stroke="' + clr +
           '" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>';
  }

  function positionAboveRow(tr) {
    var rect  = tr.getBoundingClientRect();
    var vw    = p.innerWidth;
    var ttH   = tt.offsetHeight || 165;
    var top   = rect.top - ttH - 6;
    if (top < 6) top = rect.bottom + 6;   // fallback: below row
    var left  = rect.right - 220;
    if (left < 6) left = 6;
    if (left + 250 > vw) left = vw - 256;
    tt.style.left = left + 'px';
    tt.style.top  = top  + 'px';
  }

  setTimeout(function() {
    pd.querySelectorAll('.filing-table tr[data-spark]').forEach(function(tr) {
      tr.addEventListener('mouseenter', function() {
        clearTimeout(hideTimer);

        var prices;
        try { prices = JSON.parse(tr.getAttribute('data-spark')); } catch(e) { prices = []; }
        var ticker    = tr.getAttribute('data-ticker')     || '';
        var execTitle = tr.getAttribute('data-exec-title') || '—';
        var estValue  = tr.getAttribute('data-est-value')  || '—';

        var h = '';
        if (ticker) h += '<div style="font-weight:700;color:#a78bfa;margin-bottom:8px;font-size:13px;">' + ticker + ' — 30d</div>';
        h += makeSpark(prices, 180, 44);
        h += '<div style="color:#9ca3af;font-size:11px;line-height:1.9;">' +
             'Title:&nbsp;<span style="color:#e5e7eb;">' + execTitle + '</span><br>' +
             'Value:&nbsp;<span style="color:#e5e7eb;">' + estValue  + '</span></div>';

        tt.innerHTML = h;
        tt.style.opacity = '0';          // reset before measuring
        tt.style.display = 'block';
        positionAboveRow(tr);
        tt.style.opacity = '1';
      });

      tr.addEventListener('mouseleave', function() {
        hideTimer = setTimeout(function() { tt.style.opacity = '0'; }, 150);
      });
    });
  }, 350);
})();
</script>
""", height=0)

# ── Toast: data refreshed ─────────────────────────────────────────────────────
if st.session_state.get("_refreshed"):
    del st.session_state["_refreshed"]
    components.html("""
<script>
(function() {
  var p  = window.parent ? window.parent : window;
  var pd = p.document;
  if (p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  var container = pd.getElementById('toast-container');
  if (!container) {
    container = pd.createElement('div');
    container.id = 'toast-container';
    pd.body.appendChild(container);
  }

  var t = pd.createElement('div');
  t.className = 'st-toast';
  t.style.borderLeftColor = '#22c55e';
  t.textContent = '✅ Data refreshed!';
  container.appendChild(t);

  p.requestAnimationFrame(function() {
    p.requestAnimationFrame(function() { t.classList.add('toast-show'); });
  });

  setTimeout(function() {
    t.classList.remove('toast-show');
    setTimeout(function() {
      if (container.contains(t)) container.removeChild(t);
    }, 400);
  }, 3500);
})();
</script>
""", height=0)
