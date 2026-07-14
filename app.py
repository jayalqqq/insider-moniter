import html as _html
import json
import pathlib
import re as _re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from requests.adapters import HTTPAdapter
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Global ── */
*, *::before, *::after {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Hide all Streamlit chrome ── */
#MainMenu,
header[data-testid="stHeader"],
footer,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
    visibility: hidden !important;
}

/* ── App background — deep navy with radial glow ── */
.stApp {
    background-color: #080d1a;
    color: #e2e8f0;
    background-image:
        radial-gradient(ellipse 70% 40% at 50% -10%, rgba(37,99,235,0.08) 0%, transparent 70%);
}

/* ── Push content below fixed navbar ── */
.main .block-container {
    padding-top: 88px !important;
    padding-bottom: 64px !important;
    max-width: 1400px;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background-color: #0b1120;
    border-right: 1px solid #151f35;
}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
section[data-testid="stSidebar"] label {
    text-transform: uppercase !important;
    font-size: 10px !important;
    letter-spacing: 0.12em !important;
    color: #3b5280 !important;
    font-weight: 700 !important;
}
/* sidebar inputs */
section[data-testid="stSidebar"] input {
    background-color: #0e1829 !important;
    border-color: #1a2d47 !important;
    color: #8ca3c0 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: transparent !important;
    border: 1px solid #1a3050 !important;
    color: #4d7caf !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding: 9px 16px !important;
    border-radius: 6px !important;
    transition: all 0.2s ease !important;
    width: 100%;
}
.stButton > button:hover {
    background: rgba(37,99,235,0.08) !important;
    border-color: #2563eb !important;
    color: #60a5fa !important;
}
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid #1a3050 !important;
    color: #4d7caf !important;
    font-weight: 700 !important;
    font-size: 11px !important;
    border-radius: 6px !important;
    transition: all 0.2s ease !important;
}
.stDownloadButton > button:hover {
    background: rgba(37,99,235,0.08) !important;
    border-color: #2563eb !important;
    color: #60a5fa !important;
}

/* ── KPI Grid ── */
.kpi-grid {
    display: flex; gap: 16px; margin-bottom: 40px; flex-wrap: wrap;
}
.kpi-card {
    flex: 1; min-width: 140px;
    background-color: #0c1628;
    border: 1px solid #172038;
    border-top: none;
    border-radius: 12px;
    padding: 28px 28px 24px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.kpi-card:hover {
    border-color: #1e3055;
    box-shadow: 0 12px 40px rgba(0,0,0,0.4);
    transform: translateY(-2px);
}
/* default blue top accent */
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: #2563eb;
    border-radius: 12px 12px 0 0;
}
.kpi-card.kpi-accent-green::before  { background: #16a34a; }
.kpi-card.kpi-accent-amber::before  { background: #d97706; }
.kpi-card.kpi-accent-purple::before { background: #7c3aed; }

.kpi-label {
    color: #3b5280;
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.14em;
    margin-bottom: 14px;
}
.kpi-value {
    color: #f1f5f9;
    font-size: 2.25rem; font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1; letter-spacing: -0.03em;
}
.kpi-desc {
    color: #2e4268;
    font-size: 11px; margin-top: 10px; line-height: 1.5;
}

/* ── Live pulse ── */
@keyframes livePulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
    50%       { opacity: 0.7; box-shadow: 0 0 0 6px rgba(34,197,94,0); }
}
.live-dot {
    display: inline-block; width: 8px; height: 8px;
    background: #22c55e; border-radius: 50%;
    margin-right: 6px; vertical-align: middle;
    animation: livePulse 2s ease-in-out infinite;
}

/* ── Skeleton shimmer ── */
@keyframes shimmer {
    0%   { background-position: -800px 0; }
    100% { background-position:  800px 0; }
}
.shimmer {
    background: linear-gradient(90deg, #0b1526 25%, #111e38 50%, #0b1526 75%);
    background-size: 1600px 100%;
    animation: shimmer 1.8s ease-in-out infinite;
    border-radius: 12px;
}
.skel-kpi-grid { display: flex; gap: 16px; margin-bottom: 40px; }
.skel-kpi      { flex: 1; height: 108px; border-radius: 12px; }
.skel-charts   { display: flex; gap: 16px; margin: 0 0 24px; }
.skel-chart    { flex: 1; height: 280px; }
.skel-table    { width: 100%; height: 420px; }

/* ── Chart fade-in ── */
@keyframes chartFadeIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}
.stPlotlyChart { animation: chartFadeIn 0.5s ease-out both; }

/* ── Cursor glow ── */
#cursor-glow {
    position: fixed; width: 500px; height: 500px; border-radius: 50%;
    background: radial-gradient(circle,
        rgba(37,99,235,0.045) 0%, rgba(56,189,248,0.02) 45%, transparent 70%);
    pointer-events: none;
    transform: translate(-50%, -50%);
    z-index: 0; will-change: left, top;
    transition: left 0.07s linear, top 0.07s linear;
}

/* ── Navbar (injected into parent frame) ── */
#top-navbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 999999;
    height: 56px;
    background: rgba(8,13,26,0.94);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid #151f35;
    display: flex; align-items: center;
    padding: 0 32px;
    justify-content: space-between;
    box-shadow: 0 1px 0 rgba(37,99,235,0.1);
}
#top-navbar .nav-brand {
    display: flex; align-items: center; gap: 9px;
    text-decoration: none; cursor: default;
}
#top-navbar .nav-icon { font-size: 17px; line-height: 1; }
#top-navbar .nav-wordmark {
    font-size: 14px; font-weight: 800; letter-spacing: 0.12em;
    color: #f1f5f9;
}
#top-navbar .nav-wordmark em {
    font-style: normal; color: #2563eb;
}
#top-navbar .nav-right {
    display: flex; align-items: center; gap: 8px;
}
#top-navbar .nav-pill-live {
    display: flex; align-items: center; gap: 6px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #16a34a;
    background: rgba(22,163,74,0.08);
    border: 1px solid rgba(22,163,74,0.18);
    padding: 5px 12px; border-radius: 999px;
    margin-right: 8px;
}
#top-navbar .nav-right a {
    font-size: 11px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #3b5280; text-decoration: none;
    padding: 6px 14px; border-radius: 6px;
    border: 1px solid transparent;
    transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}
#top-navbar .nav-right a:hover {
    color: #93c5fd; border-color: #1a3050;
    background: rgba(37,99,235,0.06);
}

/* ── Hero section ── */
.hero-section {
    padding: 52px 0 44px;
    border-bottom: 1px solid #151f35;
    margin-bottom: 44px;
}
.hero-eyebrow {
    font-size: 10px; font-weight: 700; letter-spacing: 0.2em;
    text-transform: uppercase; color: #2563eb;
    margin-bottom: 18px;
}
.hero-headline {
    font-size: 52px; font-weight: 800;
    color: #f1f5f9; line-height: 1.04;
    letter-spacing: -0.03em;
    margin: 0 0 18px 0;
}
.hero-headline .hl {
    background: linear-gradient(92deg, #e2e8f0 0%, #93c5fd 55%, #60a5fa 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.hero-sub {
    font-size: 16px; color: #3b5280; line-height: 1.65;
    max-width: 520px; margin: 0 0 28px 0; font-weight: 400;
}
.hero-meta {
    display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
}
.hero-live {
    display: flex; align-items: center; gap: 7px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #22c55e;
}
.hero-meta-item { font-size: 12px; color: #2e4268; }
.hero-meta-sep  { font-size: 12px; color: #1a2743; }

/* ── Section label (above charts, table) ── */
.section-label {
    font-size: 10px; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: #2e4268;
    margin-bottom: 16px; padding-bottom: 10px;
    border-bottom: 1px solid #111e38;
}

/* ── Sidebar chrome ── */
.sidebar-brand {
    padding: 24px 0 6px;
    border-bottom: 1px solid #151f35;
    margin-bottom: 8px;
}
.sidebar-brand-label {
    font-size: 9px; font-weight: 700; letter-spacing: 0.18em;
    text-transform: uppercase; color: #1e3050; margin-bottom: 4px;
}
.sidebar-brand-title {
    font-size: 15px; font-weight: 700; color: #4d7caf;
    letter-spacing: -0.01em;
}
.sidebar-div {
    height: 1px; background: #111e38; margin: 14px 0;
}
.sidebar-footer {
    font-size: 10px; color: #1e3050; line-height: 1.7; padding-top: 4px;
}

/* ── Table ── */
.filing-table {
    width: 100%; border-collapse: collapse;
    font-size: 12.5px; table-layout: fixed;
}
.filing-table th {
    background-color: #090e1c;
    color: #2e4268;
    padding: 12px 12px;
    text-align: left;
    border-bottom: 1px solid #151f35;
    font-size: 10px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.12em;
    white-space: nowrap; overflow: hidden;
    position: sticky; top: 0; z-index: 1;
}
.filing-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #0c1424;
    vertical-align: middle; overflow: hidden; text-overflow: ellipsis;
    transition: background-color 0.12s ease;
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

.filing-table tbody tr:nth-child(even) td { background-color: #080d1a; }
.filing-table tbody tr:nth-child(odd)  td { background-color: #090e1e; }
.filing-table tr:hover td                 { background-color: #0d1a30 !important; }
.filing-table tr:hover td:first-child     { border-left: 2px solid #2563eb; }
.filing-table tr.notable td              { background-color: #060f0a !important; }
.filing-table tr.notable td:first-child  { border-left: 2px solid #16a34a; }
.filing-table tr.notable:hover td:first-child { border-left: 2px solid #2563eb; }
.filing-table a { color: #2563eb; text-decoration: none; font-weight: 500; }
.filing-table a:hover { color: #60a5fa; }
.exec-name { font-weight: 700; color: #dde6f0; }
.co-name   { color: #2e4268; font-size: 12px; }

/* ── Transaction pills ── */
.txn-pill {
    display: inline-flex; align-items: center; justify-content: center;
    padding: 3px 10px; border-radius: 999px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; white-space: nowrap;
}
.txn-buy   { background: rgba(22,163,74,0.1);  color: #4ade80; border: 1px solid rgba(22,163,74,0.2); }
.txn-sell  { background: rgba(220,38,38,0.1);  color: #f87171; border: 1px solid rgba(220,38,38,0.2); }
.txn-award { background: rgba(37,99,235,0.1);  color: #60a5fa; border: 1px solid rgba(37,99,235,0.2); }
.txn-other { background: rgba(71,85,105,0.08); color: #64748b; border: 1px solid rgba(71,85,105,0.15); }

/* ── Ticker pill ── */
.ticker-pill {
    display: inline-block;
    background-color: rgba(37,99,235,0.1); color: #60a5fa;
    border: 1px solid rgba(37,99,235,0.18);
    border-radius: 4px; padding: 1px 6px; font-size: 10px;
    font-weight: 700; letter-spacing: 0.06em;
    margin-left: 4px; vertical-align: middle;
}

/* ── Badges ── */
.badge {
    display: inline-block;
    background-color: rgba(37,99,235,0.1); color: #60a5fa;
    border: 1px solid rgba(37,99,235,0.18);
    border-radius: 6px; padding: 2px 10px;
    font-size: 11px; font-weight: 600;
}
.badge-alert {
    background-color: rgba(217,119,6,0.1); color: #fbbf24;
    border-color: rgba(217,119,6,0.2);
}

/* ── SEC link button ── */
.filing-link-btn {
    display: inline-block;
    padding: 3px 10px;
    border: 1px solid rgba(37,99,235,0.25);
    border-radius: 4px;
    color: #2563eb !important;
    font-size: 10px; font-weight: 700; letter-spacing: 0.05em;
    text-decoration: none !important;
    transition: all 0.15s ease;
    white-space: nowrap;
}
.filing-link-btn:hover {
    border-color: #3b82f6;
    background: rgba(37,99,235,0.08);
    color: #60a5fa !important;
    text-decoration: none !important;
}
.filing-link-btn:active { transform: scale(0.94); }

/* ── Toast ── */
#toast-container {
    position: fixed; bottom: 28px; right: 28px;
    z-index: 99999; display: flex; flex-direction: column;
    gap: 8px; pointer-events: none;
}
.st-toast {
    background: #0c1628; border: 1px solid #172038;
    border-left: 3px solid #2563eb; border-radius: 8px;
    padding: 14px 20px; font-size: 13px; color: #dde6f0;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6); min-width: 240px;
    opacity: 0; transform: translateX(16px);
    transition: opacity 0.3s ease, transform 0.3s ease;
}
.st-toast.toast-show { opacity: 1; transform: translateX(0); }

@media (prefers-reduced-motion: reduce) {
    .stPlotlyChart    { animation: none !important; }
    .shimmer          { animation: none !important; }
    #cursor-glow      { display: none !important; }
    .st-toast         { transition: none !important; }
    .live-dot         { animation: none !important; }
}

hr { border: none; border-top: 1px solid #151f35; margin: 28px 0; }
h2 { color: #dde6f0 !important; font-size: 13px !important; font-weight: 700 !important;
     letter-spacing: 0.08em !important; text-transform: uppercase !important; }
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

# ── Persistent filing cache ────────────────────────────────────────────────────
_CACHE_FILE = pathlib.Path("filing_cache.json")
_cache_lock = threading.Lock()


def _load_filing_cache() -> dict:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_filing_cache(cache: dict) -> None:
    with _cache_lock:
        try:
            _CACHE_FILE.write_text(
                json.dumps(cache, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass


_filing_cache: dict = _load_filing_cache()

# ── Shared HTTP session (connection-pool reuse across 50 threads) ─────────────
_session = requests.Session()
_session.headers.update(HEADERS)
_session.mount("https://", HTTPAdapter(pool_connections=50, pool_maxsize=50))
_session.mount("http://",  HTTPAdapter(pool_connections=10, pool_maxsize=10))

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
        resp = _session.get(_build_txt_url(adsh, cik), timeout=5)
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
def _get_yf_sector(symbol: str) -> str:
    """Get sector from yfinance .info with a hard 10-second timeout."""
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            info = ex.submit(lambda: yf.Ticker(symbol).info).result(timeout=10)
        return info.get("sector", "") or "Unknown"
    except Exception:
        return "Unknown"


@st.cache_data(ttl=3600, show_spinner=False)
def _lookup_ticker_and_sector(company_name: str) -> tuple[str, str]:
    try:
        url = (
            "https://query2.finance.yahoo.com/v1/finance/search"
            f"?q={requests.utils.quote(company_name)}&quotesCount=1&newsCount=0"
        )
        resp   = _session.get(url, timeout=8)
        quotes = resp.json().get("quotes", [])
        if quotes and quotes[0].get("quoteType") == "EQUITY":
            q      = quotes[0]
            symbol = q.get("symbol", "")
            sector = q.get("sectorDisp", q.get("sector", "")) or ""
            if not sector and symbol:
                sector = _get_yf_sector(symbol)
            return symbol, sector or "Unknown"
    except Exception:
        pass
    return "", "Unknown"


# ── yfinance helpers ──────────────────────────────────────────────────────────
def _history_with_fallback(ticker: str, start: str, end: str):
    try:
        hist = yf.Ticker(ticker).history(start=start, end=end, timeout=10)
        if hist.empty and "." in ticker:
            hist = yf.Ticker(ticker.split(".")[0]).history(start=start, end=end, timeout=10)
        return hist
    except Exception:
        return pd.DataFrame()


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
            resp = _session.get(BASE_URL, params=params, timeout=15)
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


# ── Phase 1: SEC .txt enrichment (parallel, file-cached) ─────────────────────
def enrich_with_filing_data(
    df: pd.DataFrame, progress_bar=None
) -> tuple[pd.DataFrame, int]:
    """Enrich df with SEC .txt data. Returns (enriched_df, cache_hits)."""
    results: dict[str, dict] = {}
    pairs = [(r["Accession No"], r["CIK"]) for _, r in df.iterrows()
             if r["Accession No"] and r["CIK"]]

    # Serve hits from persistent file cache without any HTTP requests
    need_fetch = []
    for adsh, cik in pairs:
        if adsh in _filing_cache:
            results[adsh] = _filing_cache[adsh]
        else:
            need_fetch.append((adsh, cik))

    cache_hits = len(pairs) - len(need_fetch)
    total      = len(pairs)

    if need_fetch:
        new_data: dict[str, dict] = {}
        done = cache_hits

        if progress_bar:
            progress_bar.progress(
                done / total if total else 1.0,
                text=f"⚡ {cache_hits} cached · Fetching {len(need_fetch)} from SEC…",
            )

        with ThreadPoolExecutor(max_workers=50) as ex:
            fmap = {ex.submit(_fetch_filing_data, adsh, cik): adsh
                    for adsh, cik in need_fetch}
            for fut in as_completed(fmap):
                adsh   = fmap[fut]
                result = fut.result()
                results[adsh]  = result
                new_data[adsh] = result
                done += 1
                if progress_bar:
                    pct  = done / total if total else 1.0
                    fetched = done - cache_hits
                    progress_bar.progress(
                        pct,
                        text=f"Fetching from SEC… {fetched}/{len(need_fetch)}",
                    )

        # Persist new entries to the JSON file cache
        _filing_cache.update(new_data)
        _save_filing_cache(_filing_cache)

    elif progress_bar:
        progress_bar.progress(1.0, text=f"⚡ All {cache_hits} filings loaded from cache")

    df = df.copy()
    get = lambda a, k, d: results.get(a, {}).get(k, d)
    df["Transaction Type"] = df["Accession No"].map(
        lambda a: get(a, "transaction_type", "⚪ Other"))
    df["Exec Title"]       = df["Accession No"].map(
        lambda a: get(a, "exec_title",       "Director"))
    df["Shares"]           = df["Accession No"].map(
        lambda a: get(a, "shares",           None))
    df["Price Per Share"]  = df["Accession No"].map(
        lambda a: get(a, "price_per_share",  None))
    df["Transaction Date"] = df["Accession No"].map(
        lambda a: get(a, "transaction_date", None))
    return df, cache_hits


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


# ── Navbar + cursor glow (injected once per page session) ─────────────────────
components.html("""
<script>
(function() {
  var p = window.parent;
  if (!p || p === window) return;
  var pd = p.document;

  // ── Navbar ──
  if (!pd.getElementById('top-navbar')) {
    var nav = pd.createElement('div');
    nav.id = 'top-navbar';
    nav.innerHTML =
      '<div class="nav-brand">'
      + '<span class="nav-icon">📊</span>'
      + '<span class="nav-wordmark">INSIDER<em>.IO</em></span>'
      + '</div>'
      + '<div class="nav-right">'
      + '<div class="nav-pill-live"><span class="live-dot"></span>Live</div>'
      + '<a href="https://github.com" target="_blank">GitHub</a>'
      + '<a href="#">About</a>'
      + '</div>';
    pd.body.prepend(nav);
  }

  // ── Cursor glow ──
  if (!pd.getElementById('cursor-glow')) {
    var g = pd.createElement('div');
    g.id = 'cursor-glow';
    pd.body.appendChild(g);
    if (!(p.matchMedia && p.matchMedia('(prefers-reduced-motion: reduce)').matches)) {
      pd.addEventListener('mousemove', function(e) {
        g.style.left = e.clientX + 'px';
        g.style.top  = e.clientY + 'px';
      });
    }
  }
})();
</script>
""", height=0)

# ── Sidebar divider helper ─────────────────────────────────────────────────────
_GRAD_DIV = '<div class="sidebar-div"></div>'

# ══════════════════════════════════════════════════════════════════════════════
# ── Sidebar part 1 ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(
        "<div class='sidebar-brand'>"
        "<div class='sidebar-brand-label'>Control Panel</div>"
        "<div class='sidebar-brand-title'>Filters</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    col_s, col_e = st.columns(2)
    with col_s:
        start_date = st.date_input(
            "📅 Start",
            value=date(2025, 1, 1),
            max_value=date.today(),
            key="start_date",
            on_change=fetch_filings.clear,
        )
    with col_e:
        end_date = st.date_input(
            "📅 End",
            value=date.today(),
            max_value=date.today(),
            key="end_date",
            on_change=fetch_filings.clear,
        )
    st.markdown(_GRAD_DIV, unsafe_allow_html=True)
    refresh = st.button("🔄 Refresh Data", use_container_width=True)
    if refresh:
        st.cache_data.clear()
        st.session_state["_refreshed"] = True

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
<div class="hero-section">
  <div class="hero-eyebrow">SEC Form 4 Intelligence</div>
  <h1 class="hero-headline">Track What<br><span class="hl">Insiders Know</span></h1>
  <p class="hero-sub">Real-time SEC Form 4 filings — see exactly when executives buy and sell their own stock.</p>
  <div class="hero-meta">
    <div class="hero-live"><span class="live-dot"></span>Live</div>
    <span class="hero-meta-sep">·</span>
    <span class="hero-meta-item">Form 4 filings via SEC EDGAR</span>
    <span class="hero-meta-sep">·</span>
    <span class="hero-meta-item">{start_date.strftime('%b %d, %Y')} – {end_date.strftime('%b %d, %Y')}</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

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

_enrich_prog = st.progress(0, text="Checking filing cache…")
df, _cache_hits = enrich_with_filing_data(df, progress_bar=_enrich_prog)
_enrich_prog.empty()

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
        "<div class='sidebar-footer'>"
        "Data: SEC EDGAR &amp; Yahoo Finance<br>"
        "Filings · 5 min cache<br>"
        "Filing detail · 10 min cache<br>"
        "Market data · 1 hr cache"
        "</div>",
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
sectors_n    = filtered[
    filtered["Sector"].notna() &
    (filtered["Sector"] != "") &
    (filtered["Sector"] != "Unknown")
]["Sector"].nunique()

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
  <div class="kpi-card kpi-accent-amber">
    <div class="kpi-label">Buy / Sell Ratio</div>
    <div class="kpi-value" data-target="{_ratio_num or 0}" data-final="{_html.escape(_ratio_display)}" data-type="ratio">{"0" if _ratio_num else _ratio_display}</div>
    <div class="kpi-desc">{buys} buys · {sells} sells</div>
  </div>
  <div class="kpi-card kpi-accent-green">
    <div class="kpi-label">Notable Buys</div>
    <div class="kpi-value" data-target="{notable_buys}" data-type="int">0</div>
    <div class="kpi-desc">CEO / CFO / President purchasing</div>
  </div>
  <div class="kpi-card kpi-accent-purple">
    <div class="kpi-label">Latest Filing</div>
    <div class="kpi-value" data-type="date" style="font-size:1.4rem;opacity:0;">{latest_str}</div>
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
_CHART_FONT   = dict(family="Inter, -apple-system, sans-serif", color="#94a3b8")
_GRID_COLOR   = "#1e2a3a"
_TICK_COLOR   = "#94a3b8"
_TRANSPARENT  = "rgba(0,0,0,0)"
_AXIS_BASE    = dict(
    color=_TICK_COLOR, tickfont=dict(color=_TICK_COLOR, size=11),
    linecolor=_GRID_COLOR, showline=False, zeroline=False,
    gridcolor=_GRID_COLOR, gridwidth=1,
)
_BASE_LAYOUT  = dict(
    margin=dict(l=0, r=0, t=14, b=0),
    plot_bgcolor=_TRANSPARENT, paper_bgcolor=_TRANSPARENT,
    height=268,
    font=_CHART_FONT,
    hoverlabel=dict(bgcolor="#0c1628", bordercolor="#1e2a3a", font=dict(color="#e2e8f0", size=12)),
    modebar=dict(remove=["toImage", "zoom2d", "pan2d", "select2d", "lasso2d",
                         "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"]),
)

_CHART_CONFIG = dict(displayModeBar=False, responsive=True)

# label mapping without emoji for chart legends
_TXN_LABEL_CLEAN = {
    "🟢 Buy":   "Buy",
    "🔴 Sell":  "Sell",
    "🔵 Award": "Award",
    "⚪ Other": "Other",
}
_SECTOR_COLORS = {
    "Buy":  "#22c55e",
    "Sell": "#ef4444",
}

with charts_placeholder.container():
    col_area, col_pie, col_bar = st.columns(3)

    # ── Filings Over Time — filled area chart ─────────────────────────────────
    with col_area:
        st.markdown("<div class='section-label'>Filings Over Time</div>", unsafe_allow_html=True)
        daily = (
            filtered.set_index("Filed").resample("D")["Accession No"]
            .count().reset_index()
            .rename(columns={"Filed": "Date", "Accession No": "Filings"})
        )
        avg_filings = daily["Filings"].mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["Date"], y=daily["Filings"],
            mode="lines",
            line=dict(color="#3b82f6", width=2),
            fill="tozeroy",
            fillgradient=dict(colorscale=[[0, "rgba(37,99,235,0.25)"], [1, "rgba(37,99,235,0)"]],
                              type="vertical"),
            hovertemplate="%{x|%b %d}<br><b>%{y} filings</b><extra></extra>",
            name="Filings",
        ))
        fig.add_hline(
            y=avg_filings, line_dash="dot", line_color="#1e3a5f", line_width=1,
            annotation_text=f"avg {avg_filings:.0f}",
            annotation_font=dict(color="#3b5280", size=10),
            annotation_position="bottom right",
        )
        fig.update_layout(
            **_BASE_LAYOUT,
            xaxis=dict(**_AXIS_BASE, showgrid=False,
                       tickformat="%b %d", nticks=6, tickangle=0),
            yaxis=dict(**_AXIS_BASE, showgrid=True),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    # ── Transaction Breakdown — donut chart ───────────────────────────────────
    with col_pie:
        st.markdown("<div class='section-label'>Transaction Breakdown</div>", unsafe_allow_html=True)
        txn_counts = (
            filtered["Transaction Type"].value_counts()
            .reindex(TRANSACTION_ORDER, fill_value=0).reset_index()
        )
        txn_counts.columns = ["Type", "Count"]
        txn_counts = txn_counts[txn_counts["Count"] > 0]
        txn_counts["Label"] = txn_counts["Type"].map(_TXN_LABEL_CLEAN).fillna(txn_counts["Type"])
        _donut_colors = {
            "🟢 Buy":   "#22c55e",
            "🔴 Sell":  "#ef4444",
            "🔵 Award": "#3b82f6",
            "⚪ Other": "#64748b",
        }
        _total_txn = int(txn_counts["Count"].sum())
        fig = go.Figure(go.Pie(
            labels=txn_counts["Label"],
            values=txn_counts["Count"],
            marker_colors=[_donut_colors.get(t, "#64748b") for t in txn_counts["Type"]],
            hole=0.65,
            textinfo="none",
            hovertemplate="<b>%{label}</b><br>%{value} transactions<br>%{percent}<extra></extra>",
        ))
        fig.add_annotation(
            text=f"<b>{_total_txn:,}</b><br><span style='font-size:10px'>total</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color="#e2e8f0", size=20, family="Inter"),
            align="center",
        )
        fig.update_layout(
            **_BASE_LAYOUT,
            showlegend=True,
            legend=dict(
                orientation="v", x=1.02, y=0.5,
                xanchor="left", yanchor="middle",
                bgcolor=_TRANSPARENT,
                font=dict(color="#94a3b8", size=11),
                itemsizing="constant",
                traceorder="normal",
            ),
            margin=dict(l=0, r=80, t=14, b=0),
        )
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    # ── Top 10 Locations — horizontal bar chart ───────────────────────────────
    with col_bar:
        st.markdown("<div class='section-label'>Top 10 Locations</div>", unsafe_allow_html=True)
        top_locs = filtered["Location"].value_counts().head(10).reset_index()
        top_locs.columns = ["Location", "Filings"]
        top_locs = top_locs.sort_values("Filings", ascending=True)
        _n = len(top_locs)
        _bar_colors = [
            f"rgba({int(37 + (6-37)*i/max(_n-1,1))},{int(99 + (182-99)*i/max(_n-1,1))},{int(235 + (212-235)*i/max(_n-1,1))},0.85)"
            for i in range(_n)
        ]
        fig = go.Figure(go.Bar(
            x=top_locs["Filings"],
            y=top_locs["Location"],
            orientation="h",
            marker=dict(color=_bar_colors, line=dict(width=0)),
            text=top_locs["Filings"],
            textposition="outside",
            textfont=dict(color="#4b6080", size=11),
            hovertemplate="<b>%{y}</b><br>%{x} filings<extra></extra>",
            cliponaxis=False,
        ))
        fig.update_layout(
            **_BASE_LAYOUT,
            yaxis=dict(**_AXIS_BASE, showgrid=False, showline=False, tickfont=dict(color="#94a3b8", size=11)),
            xaxis=dict(**_AXIS_BASE, showgrid=True, showticklabels=False),
            bargap=0.35,
        )
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    # ── Insider Activity by Sector — grouped bar chart ────────────────────────
    sector_df = filtered[
        filtered["Sector"].notna() &
        (filtered["Sector"] != "Unknown") &
        filtered["Transaction Type"].isin(["🟢 Buy", "🔴 Sell"])
    ]
    if not sector_df.empty:
        st.markdown("<div class='section-label'>Insider Activity by Sector</div>", unsafe_allow_html=True)
        sc = sector_df.copy()
        sc["TxnLabel"] = sc["Transaction Type"].map(_TXN_LABEL_CLEAN)
        sc = sc.groupby(["Sector", "TxnLabel"]).size().reset_index(name="Count")
        fig = go.Figure()
        for txn_label, color in [("Buy", "#22c55e"), ("Sell", "#ef4444")]:
            sub = sc[sc["TxnLabel"] == txn_label]
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub["Sector"], y=sub["Count"],
                name=txn_label,
                marker=dict(color=color, opacity=0.85, line=dict(width=0)),
                hovertemplate="<b>%{x}</b><br>" + txn_label + ": %{y}<extra></extra>",
            ))
        fig.update_layout(
            **_BASE_LAYOUT,
            height=280,
            barmode="group",
            bargap=0.28,
            bargroupgap=0.08,
            xaxis=dict(**_AXIS_BASE, showgrid=False, tickangle=-30, tickfont=dict(color="#94a3b8", size=11)),
            yaxis=dict(**_AXIS_BASE, showgrid=True),
            legend=dict(
                orientation="h", x=1, y=1,
                xanchor="right", yanchor="bottom",
                bgcolor=_TRANSPARENT,
                font=dict(color="#94a3b8", size=11),
                itemsizing="constant",
            ),
        )
        st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

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
            border:1px solid #151f35; border-radius:12px; width:100%;">
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
    _cache_note = (
        f" &nbsp;·&nbsp; <span style='color:#854d0e;'>⚡ {_cache_hits}/{len(df)} from cache</span>"
        if _cache_hits > 0 else ""
    )
    st.markdown(
        f"<small style='color:#4b5563'>Returns from transaction date · "
        f"Last fetched: {datetime.now().strftime('%H:%M:%S')}{_cache_note}</small>",
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
            end_price  = chart_data["Close"].iloc[-1]
            line_color = "#22c55e" if end_price >= base_price else "#ef4444"
            fig_chart  = go.Figure()
            fig_chart.add_trace(go.Scatter(
                x=chart_data["Date"], y=chart_data["Close"],
                mode="lines",
                line=dict(color=line_color, width=2),
                fill="tozeroy",
                fillgradient=dict(
                    colorscale=[[0, line_color.replace(")", ",0.15)").replace("rgb", "rgba")],
                                  [1, "rgba(0,0,0,0)"]],
                    type="vertical",
                ),
                hovertemplate="%{x|%b %d}<br><b>$%{y:.2f}</b><extra></extra>",
                name=sel_ticker,
            ))
            fig_chart.add_vline(
                x=int(pd.to_datetime(sel_date).timestamp() * 1000),
                line_dash="dash", line_color="#d97706", line_width=1,
                annotation_text="Transaction", annotation_font=dict(color="#d97706", size=11),
                annotation_position="top right",
            )
            fig_chart.add_hline(
                y=base_price, line_dash="dot", line_color="#1e3a5f", line_width=1,
                annotation_text=f"Entry ${base_price:.2f}",
                annotation_font=dict(color="#3b5280", size=10),
                annotation_position="bottom right",
            )
            fig_chart.update_layout(
                **_BASE_LAYOUT,
                height=320,
                margin=dict(l=0, r=0, t=36, b=0),
                title=dict(
                    text=f"{sel_ticker} — 30 days post-transaction",
                    font=dict(size=13, color="#94a3b8", family="Inter"),
                    x=0, pad=dict(l=0),
                ),
                xaxis=dict(**_AXIS_BASE, showgrid=False, tickformat="%b %d", nticks=8),
                yaxis=dict(**_AXIS_BASE, showgrid=True, tickprefix="$"),
                showlegend=False,
            )
            st.plotly_chart(fig_chart, use_container_width=True, config=_CHART_CONFIG)

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
