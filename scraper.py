#!/usr/bin/env python3
"""Manual scraper: SEC EDGAR Form 4 filings + Tiingo daily prices -> SQLite.

Usage
-----
    python scraper.py                          # last default window, 200 filings
    python scraper.py --start 2025-01-01 --limit 500
    python scraper.py --max-tickers 25         # bound Tiingo usage this run

Safe to run repeatedly: every write is an upsert (filings keyed on accession
number, prices on ticker+date), so re-running the same window updates rows in
place rather than duplicating them.

The fetch/parse logic mirrors app.py, but is reimplemented standalone because
importing app.py would execute the whole Streamlit app. Deliberately uses only
requests + sqlite3 (no pandas/streamlit) so it starts instantly.

Tiingo key is read from the TIINGO_API_KEY env var, falling back to
.streamlit/secrets.toml (the same file the app uses).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

import database as db

# ── Constants (mirrored from app.py) ──────────────────────────────────────────
HEADERS      = {"User-Agent": "Jayal insider-monitor jayal@email.com"}
EDGAR_URL    = "https://efts.sec.gov/LATEST/search-index"
YAHOO_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"
TIINGO_URL   = "https://api.tiingo.com/tiingo/daily"
PRICE_START  = "2023-01-01"          # wide window -> one pull per ticker
EDGAR_PAGE   = 100                   # EDGAR full-text search returns 100 hits/page

# SEC's official CIK -> ticker mapping (authoritative, free). Cached to disk and
# refreshed weekly. This is the primary way we resolve tickers now; Yahoo name
# search (imprecise: returns Frankfurt ".F" listings and warrant classes) is only
# a fallback for the rare issuer whose CIK isn't in this file.
CIK_MAP_URL   = "https://www.sec.gov/files/company_tickers.json"
CIK_MAP_CACHE = Path(__file__).parent / ".cache" / "company_tickers.json"
CIK_MAP_TTL   = 7 * 86400            # refresh weekly

TXN_LABELS = {"P": "Buy", "S": "Sell", "A": "Award"}

_CIK_RE    = re.compile(r"\s*\(CIK\s+\d+\)\s*$", re.I)
_CODE_RE   = re.compile(r"<transactionCode>([^<]+)</transactionCode>", re.I)
_TITLE_RE  = re.compile(r"<officerTitle>([^<]*)</officerTitle>", re.I)
_SHARES_RE = re.compile(r"<transactionShares>\s*<value>([^<]+)</value>", re.I | re.S)
_PRICE_RE  = re.compile(r"<transactionPricePerShare>\s*<value>([^<]+)</value>", re.I | re.S)
_TDATE_RE  = re.compile(r"<transactionDate>\s*<value>([^<]+)</value>", re.I | re.S)
_SEE_RMKS  = re.compile(r"see\s+remarks", re.I)

session = requests.Session()
session.headers.update(HEADERS)
session.mount("https://", HTTPAdapter(pool_connections=20, pool_maxsize=20))


# ── Helpers ───────────────────────────────────────────────────────────────────
def tiingo_token() -> str:
    """Env var first, then .streamlit/secrets.toml (no streamlit import needed)."""
    tok = os.environ.get("TIINGO_API_KEY", "").strip()
    if tok:
        return tok
    secrets = Path(__file__).parent / ".streamlit" / "secrets.toml"
    if secrets.exists():
        try:
            import tomllib
            with open(secrets, "rb") as fh:
                return str(tomllib.load(fh).get("TIINGO_API_KEY", "")).strip()
        except Exception:
            pass
    return ""


def load_sec_ticker_map() -> dict[int, str]:
    """SEC's official CIK->ticker map as {int_cik: TICKER}. Cached weekly on disk.

    The file looks like {"0": {"cik_str": 320193, "ticker": "AAPL", ...}, ...}.
    Keyed by integer CIK (leading zeros dropped) so it matches the CIKs on filings.
    """
    raw = None
    try:
        if (CIK_MAP_CACHE.exists()
                and time.time() - CIK_MAP_CACHE.stat().st_mtime < CIK_MAP_TTL):
            raw = json.loads(CIK_MAP_CACHE.read_text())
    except Exception:
        raw = None
    if raw is None:
        try:
            resp = session.get(CIK_MAP_URL, timeout=30)
            resp.raise_for_status()
            raw = resp.json()
            CIK_MAP_CACHE.parent.mkdir(exist_ok=True)
            CIK_MAP_CACHE.write_text(json.dumps(raw))
        except Exception as exc:
            print(f"  ! could not load SEC CIK->ticker map: {exc}")
            return {}
    # A CIK can list several tickers (common + warrants/preferreds/units). SEC
    # orders them with the primary common stock FIRST, so keep the first one seen
    # per CIK — otherwise we'd grab e.g. the "KDKRW" warrant instead of "KDK".
    out: dict[int, str] = {}
    for entry in raw.values():
        try:
            cik = int(entry["cik_str"])
        except (KeyError, ValueError, TypeError):
            continue
        if cik not in out:
            out[cik] = str(entry["ticker"]).upper()
    return out


def _norm_cik(cik) -> int | None:
    try:
        return int(str(cik).strip())      # int() handles zero-padded CIKs
    except (ValueError, TypeError):
        return None


def resolve_cik_ticker(all_ciks, cik_map: dict[int, str]) -> str:
    """First of a filing's CIKs that maps to a ticker (issuer CIK, order-agnostic)."""
    for cik in all_ciks or []:
        ticker = cik_map.get(_norm_cik(cik))
        if ticker:
            return ticker
    return ""


def _strip_cik(name: str) -> str:
    return _CIK_RE.sub("", name or "").strip()


def _filing_url(adsh: str, cik: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}-index.htm"


def _resolve_title(raw: str) -> str:
    raw = (raw or "").strip()
    return "Director" if not raw or _SEE_RMKS.search(raw) else raw


# ── SEC EDGAR ─────────────────────────────────────────────────────────────────
def fetch_filings(start: str, end: str, limit: int) -> list[dict]:
    """Paginate EDGAR full-text search, de-duplicating by accession number."""
    hits, seen = [], set()
    for page in range(100):                       # EDGAR caps `from` at 10,000
        if len(hits) >= limit:
            break
        params = {
            "q": '"form 4"', "forms": "4", "dateRange": "custom",
            "startdt": start, "enddt": end, "from": page * EDGAR_PAGE,
        }
        try:
            resp = session.get(EDGAR_URL, params=params, timeout=20)
            resp.raise_for_status()
            batch = resp.json().get("hits", {}).get("hits", [])
        except Exception as exc:
            print(f"  ! EDGAR error on page {page}: {exc}")
            break
        if not batch:
            break
        for hit in batch:
            adsh = hit.get("_source", {}).get("adsh", "")
            if adsh and adsh not in seen:
                seen.add(adsh)
                hits.append(hit)
        print(f"  page {page + 1}: {len(hits)} unique filings so far", flush=True)
        if len(batch) < EDGAR_PAGE:
            break
    return hits[:limit]


def parse_hit(hit: dict) -> dict:
    """EDGAR search hit -> partial filing row (before the per-filing detail fetch)."""
    src   = hit.get("_source", {})
    names = src.get("display_names", [])
    ciks  = src.get("ciks", [])
    cik   = ciks[-1] if ciks else ""
    adsh  = src.get("adsh", "")
    locs  = [l for l in src.get("biz_locations", []) if l]
    return {
        "accession_no": adsh,
        "filed_date":   src.get("file_date"),
        "executive":    _strip_cik(names[0]) if len(names) > 0 else None,
        "company":      _strip_cik(names[1]) if len(names) > 1 else None,
        "cik":          cik,
        "_all_ciks":    ciks,   # transient (not stored) — used for CIK->ticker lookup
        "location":     locs[0] if locs else (", ".join(src.get("biz_states", [])) or None),
        "filing_url":   _filing_url(adsh, cik) if adsh and cik else None,
    }


def fetch_filing_detail(adsh: str, cik: str):
    """Parse transaction code/title/shares/price/date from the raw filing .txt.

    Returns a detail dict on a SUCCESSFUL fetch — a genuinely holdings-only filing
    (no transaction) yields the empty defaults, which is accurate. Returns **None**
    if the fetch itself failed after retries (SEC throttling / timeout). The caller
    skips those so they retry on a later run instead of writing a bad NULL row or
    overwriting good data. This is the fix for the ~40% silent NULLs: firing 100
    requests at once exceeded SEC's ~10 req/s limit; failures were swallowed as
    the same default an empty filing produces, so we couldn't tell them apart.
    """
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{adsh}.txt"
    text = None
    for attempt in range(4):
        try:
            time.sleep(random.uniform(0.08, 0.2))      # pacing to stay under SEC's rate limit
            resp = session.get(url, timeout=20)
            if resp.status_code == 200:
                text = resp.text
                break
            if resp.status_code in (429, 403, 500, 502, 503, 504):
                time.sleep(1.0 * (attempt + 1) + random.random())   # backoff on throttle
                continue
            return None            # other non-200 -> treat as fetch failure, retry next run
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    if text is None:
        return None                # fetch failed after retries -> skip (don't store NULL)

    detail = {"transaction_type": "Other", "exec_title": "Director",
              "shares": None, "price_per_share": None, "transaction_date": None}

    codes = [c.strip() for c in _CODE_RE.findall(text)]
    for code in ("P", "S", "A"):                  # priority: Buy > Sell > Award
        if code in codes:
            detail["transaction_type"] = TXN_LABELS[code]
            break

    m = _TITLE_RE.search(text)
    detail["exec_title"] = _resolve_title(m.group(1) if m else "")

    m = _SHARES_RE.search(text)
    if m:
        try:
            detail["shares"] = float(m.group(1).strip())
        except ValueError:
            pass

    m = _PRICE_RE.search(text)
    if m:
        try:
            detail["price_per_share"] = float(m.group(1).strip())
        except ValueError:
            pass

    m = _TDATE_RE.search(text)
    if m:
        detail["transaction_date"] = m.group(1).strip()
    return detail


def lookup_ticker_sector(company: str) -> tuple[str, str]:
    """Company name -> (ticker, sector) via Yahoo's search endpoint."""
    try:
        resp = session.get(YAHOO_SEARCH,
                           params={"q": company, "quotesCount": 1, "newsCount": 0},
                           timeout=10)
        quotes = resp.json().get("quotes", [])
        if quotes and quotes[0].get("quoteType") == "EQUITY":
            q = quotes[0]
            return q.get("symbol", ""), (q.get("sectorDisp") or q.get("sector") or "Unknown")
    except Exception:
        pass
    return "", "Unknown"


# ── Tiingo ────────────────────────────────────────────────────────────────────
def fetch_price_history(ticker: str, token: str) -> list[tuple[str, str, float]]:
    """One pull per ticker -> [(ticker, YYYY-MM-DD, close), ...]. [] on failure."""
    symbol = ticker.split(".")[0].strip().upper()   # Tiingo uses plain US symbols
    params = {"startDate": PRICE_START, "endDate": str(date.today()), "token": token}
    for attempt in range(3):
        try:
            time.sleep(random.uniform(0.15, 0.4))   # gentle pacing
            resp = session.get(f"{TIINGO_URL}/{symbol}/prices", params=params,
                               headers={"Content-Type": "application/json"}, timeout=20)
            if resp.status_code == 429:
                wait = 2 ** attempt + random.random()
                print(f"    ! {ticker}: rate limited (429), backing off {wait:.1f}s")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"    ! {ticker}: HTTP {resp.status_code}")
                return []
            return [(ticker, row["date"][:10], row["close"])
                    for row in resp.json() if row.get("close") is not None]
        except Exception as exc:
            print(f"    ! {ticker}: {type(exc).__name__}")
            time.sleep(1.0 * (attempt + 1))
    return []


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="Scrape SEC Form 4 filings + prices into SQLite")
    ap.add_argument("--start", default="2025-01-01", help="filing start date (YYYY-MM-DD)")
    ap.add_argument("--end", default=str(date.today()), help="filing end date (YYYY-MM-DD)")
    ap.add_argument("--limit", type=int, default=200, help="max filings to fetch")
    ap.add_argument("--max-tickers", type=int, default=40,
                    help="max tickers to fetch prices for this run (Tiingo free tier: 50/hr)")
    ap.add_argument("--skip-prices", action="store_true", help="only scrape filings")
    args = ap.parse_args()

    print(f"Database: {db.DB_PATH}")
    conn = db.init_db()
    start_counts = db.counts(conn)
    print(f"Starting row counts: {start_counts}\n")

    # 1. Filings from EDGAR
    print(f"[1/4] Fetching Form 4 filings {args.start} -> {args.end} (limit {args.limit})")
    hits = fetch_filings(args.start, args.end, args.limit)
    print(f"      fetched {len(hits)} filings\n")
    if not hits:
        print("No filings returned; nothing to do.")
        return 0

    rows = [parse_hit(h) for h in hits]

    # 2. Per-filing detail (transaction type, shares, price, transaction date).
    #    Low concurrency + pacing + retries keep us under SEC's ~10 req/s limit so
    #    fetches don't get throttled and silently stored as NULL. A None result
    #    means the fetch FAILED (not a holdings-only filing) -> skip that filing so
    #    it retries next run rather than clobbering a row with NULLs.
    print(f"[2/4] Fetching filing details for {len(rows)} filings (throttled)")
    detailed, failed, done = [], 0, 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_filing_detail, r["accession_no"], r["cik"]): r
                   for r in rows if r["accession_no"] and r["cik"]}
        for fut in as_completed(futures):
            r = futures[fut]
            detail = fut.result()
            done += 1
            if detail is None:
                failed += 1                 # fetch failed -> skip; retry next run
            else:
                r.update(detail)
                detailed.append(r)
            if done % 25 == 0 or done == len(futures):
                print(f"      {done}/{len(futures)} details fetched", flush=True)
    if failed:
        print(f"      ! {failed} detail fetch(es) failed (throttled/timeout) — "
              f"skipped, will retry next run")
    rows = detailed                          # keep only filings we successfully detailed
    if not rows:
        print("No filings could be detailed; nothing to store.")
        return 0
    print()

    # 3. Ticker via SEC's authoritative CIK->ticker map (exact, no guessing).
    #    Yahoo name search is used only for the sector, and as a ticker fallback
    #    when an issuer's CIK isn't in the SEC file.
    cik_map = load_sec_ticker_map()
    companies = sorted({r["company"] for r in rows if r.get("company")})
    print(f"[3/4] Resolving tickers via SEC CIK map ({len(cik_map)} entries) "
          f"+ sector for {len(companies)} companies")
    name_results: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(lookup_ticker_sector, c): c for c in companies}
        for fut in as_completed(futures):
            name_results[futures[fut]] = fut.result()

    cik_hits = name_fallbacks = 0
    for r in rows:
        cik_ticker = resolve_cik_ticker(r.get("_all_ciks"), cik_map)
        name_ticker, sector = name_results.get(r.get("company"), ("", "Unknown"))
        if cik_ticker:
            r["ticker"] = cik_ticker
            cik_hits += 1
        else:
            r["ticker"] = name_ticker          # fallback: name search
            if name_ticker:
                name_fallbacks += 1
        r["sector"] = sector
        if r.get("shares") is not None and r.get("price_per_share") is not None:
            r["est_value"] = round(r["shares"] * r["price_per_share"], 2)
        else:
            r["est_value"] = None
    resolved = sum(1 for r in rows if r["ticker"])
    print(f"      resolved {resolved}/{len(rows)} filings to a ticker "
          f"({cik_hits} via SEC CIK map, {name_fallbacks} via name-search fallback)\n")

    inserted, updated = db.upsert_filings(conn, rows)
    print(f"      -> filings: {inserted} new, {updated} updated\n")

    # 4. Prices per unique ticker (tickers with no prices yet go first)
    if args.skip_prices:
        print("[4/4] --skip-prices set; skipping Tiingo.")
    else:
        token = tiingo_token()
        if not token:
            print("[4/4] No TIINGO_API_KEY found (env or .streamlit/secrets.toml); skipping prices.")
        else:
            have = db.tickers_with_prices(conn)
            uniq = sorted({r["ticker"] for r in rows if r["ticker"]})
            # SPY is the S&P-500 benchmark the app needs; always fetch it first so
            # it's never cut by the --max-tickers cap.
            todo = ["SPY"] if "SPY" not in have else []
            todo += [t for t in uniq if t not in have and t != "SPY"]
            todo += [t for t in uniq if t in have and t != "SPY"]
            todo = todo[:args.max_tickers]
            print(f"[4/4] Fetching prices for {len(todo)} of {len(uniq)} unique tickers "
                  f"(cap --max-tickers={args.max_tickers})")
            p_ins = p_upd = ok = 0
            for i, ticker in enumerate(todo, 1):
                bars = fetch_price_history(ticker, token)
                if bars:
                    ok += 1
                    a, b = db.upsert_prices(conn, bars)
                    p_ins += a
                    p_upd += b
                print(f"      {i}/{len(todo)} {ticker}: {len(bars)} bars", flush=True)
            print(f"      -> prices: {p_ins} new, {p_upd} updated "
                  f"({ok}/{len(todo)} tickers succeeded)\n")

    end_counts = db.counts(conn)
    print("Done.")
    print(f"  filings : {start_counts['filings']} -> {end_counts['filings']}")
    print(f"  prices  : {start_counts['prices']} -> {end_counts['prices']} "
          f"across {end_counts['tickers']} tickers")
    # Merge the WAL into the main file so the committed insider.db is complete
    # and standalone (the -wal/-shm sidecars are not committed).
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
