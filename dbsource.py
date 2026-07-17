"""Read the SQLite store into the exact shape the Streamlit app expects.

Phase 2 wiring: `app.py` reads filings + prices from `insider.db` (populated by
`scraper.py`) instead of live-fetching from SEC/Tiingo on every page load. This
module is the read layer. It's deliberately free of any `streamlit` import so it
can be unit-tested on its own (and imported cheaply by the app).

The DataFrames returned here match the columns the app's downstream code already
uses, so nothing after the load step needs to change:

  Filed (datetime), Executive / Filer, Company, Location, Accession No, CIK,
  Filing URL, Transaction Type (emoji-prefixed), Exec Title, Shares,
  Price Per Share, Transaction Date, Ticker, Sector

Return columns (7d/30d/90d) are computed by the app from the price history via
its existing returns math — not here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import database as db

# App uses emoji-prefixed transaction types everywhere (filters, pills, ==
# comparisons); the DB stores the plain word. Map back on the way out.
_TXN_TO_EMOJI = {"Buy": "🟢 Buy", "Sell": "🔴 Sell", "Award": "🔵 Award", "Other": "⚪ Other"}


def open_db(db_path: Path | str = db.DB_PATH):
    """Return (conn, has_filings). (None, False) if the DB is missing/empty/broken
    — the caller uses that to fall back to live fetching."""
    try:
        if not Path(db_path).exists():
            return None, False
        conn = db.connect(db_path)
        n = conn.execute("SELECT COUNT(*) FROM filings").fetchone()[0]
        return conn, (n > 0)
    except Exception:
        return None, False


def load_filings(conn, start: str, end: str, limit: int) -> pd.DataFrame:
    """Filings filed within [start, end] (inclusive), newest first, capped at
    `limit`, as a DataFrame with the app's column names. No return columns."""
    q = """
        SELECT accession_no, filed_date, transaction_date, executive, exec_title,
               company, ticker, cik, transaction_type, shares, price_per_share,
               location, sector, filing_url
        FROM filings
        WHERE filed_date BETWEEN ? AND ?
        ORDER BY filed_date DESC, accession_no DESC
        LIMIT ?
    """
    rows = conn.execute(q, (start, end, int(limit))).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame({
        "Filed":             pd.to_datetime([r["filed_date"] for r in rows], errors="coerce"),
        "Executive / Filer": [r["executive"] or "—" for r in rows],
        "Company":           [r["company"] or "—" for r in rows],
        "Location":          [r["location"] or "—" for r in rows],
        "Accession No":      [r["accession_no"] for r in rows],
        "CIK":               [r["cik"] or "" for r in rows],
        "Filing URL":        [r["filing_url"] or "" for r in rows],
        "Transaction Type":  [_TXN_TO_EMOJI.get(r["transaction_type"], "⚪ Other") for r in rows],
        "Exec Title":        [r["exec_title"] or "Director" for r in rows],
        "Shares":            [r["shares"] for r in rows],
        "Price Per Share":   [r["price_per_share"] for r in rows],
        "Transaction Date":  [r["transaction_date"] for r in rows],
        "Ticker":            [r["ticker"] or "" for r in rows],
        "Sector":            [r["sector"] or "Unknown" for r in rows],
    })
    return df


def history_from_db(conn, ticker: str) -> pd.DataFrame:
    """A ticker's stored daily closes as a tz-aware Date-indexed DataFrame with a
    "Close" column — the same shape the app's live Tiingo fetch produces, so the
    existing returns / chart / sparkline code works unchanged. Empty if no rows."""
    if not ticker:
        return pd.DataFrame()
    rows = conn.execute(
        "SELECT date, close FROM prices WHERE ticker = ? ORDER BY date", (ticker,)
    ).fetchall()
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(
        {"Close": [r["close"] for r in rows]},
        index=pd.to_datetime([r["date"] for r in rows], utc=True),
    )
    out.index.name = "Date"
    return out


def unique_tickers(df: pd.DataFrame) -> list[str]:
    return sorted({t for t in df["Ticker"] if t})
