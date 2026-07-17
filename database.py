"""SQLite storage layer for the SEC insider-trading monitor.

Phase 2: the Streamlit app currently fetches everything live on each load. This
module is the durable store that a scraper populates ahead of time, so the app
can eventually read from disk instead of hammering SEC/Tiingo on every request.

Tables
------
filings : one row per SEC Form 4 filing, keyed by accession number.
prices  : daily closing prices, unique per (ticker, date).

Every write is an UPSERT, so the scraper is safe to run repeatedly — re-running
over the same window updates rows in place instead of duplicating them.

Dependency-light on purpose: stdlib sqlite3 only (no pandas / streamlit), so it
imports instantly and can be driven from a plain script or a scheduler.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "insider.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS filings (
    accession_no     TEXT PRIMARY KEY,   -- SEC accession number (unique per filing)
    filed_date       TEXT,               -- YYYY-MM-DD, when the Form 4 was filed
    transaction_date TEXT,               -- YYYY-MM-DD, when the trade happened
    executive        TEXT,               -- reporting person
    exec_title       TEXT,               -- e.g. "CEO", "Director"
    company          TEXT,               -- issuer name
    ticker           TEXT,
    cik              TEXT,
    transaction_type TEXT,               -- Buy | Sell | Award | Other
    shares           REAL,
    price_per_share  REAL,
    est_value        REAL,               -- shares * price_per_share
    location         TEXT,
    sector           TEXT,
    filing_url       TEXT,               -- link to the filing on sec.gov
    updated_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_filings_ticker     ON filings(ticker);
CREATE INDEX IF NOT EXISTS idx_filings_filed_date ON filings(filed_date);

CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,               -- YYYY-MM-DD
    close  REAL,
    UNIQUE(ticker, date)                -- never store the same day twice
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);
"""

# Column order used by upsert_filings; accession_no must stay first (conflict key).
FILING_COLUMNS = (
    "accession_no", "filed_date", "transaction_date", "executive", "exec_title",
    "company", "ticker", "cik", "transaction_type", "shares", "price_per_share",
    "est_value", "location", "sector", "filing_url",
)


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a connection with sane defaults (row access by name, WAL journaling)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Create the tables/indexes if they don't exist. Returns an open connection."""
    conn = connect(db_path)
    with conn:
        conn.executescript(_SCHEMA)
    return conn


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def upsert_filings(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int]:
    """Insert filings, updating in place on accession-number conflict.

    Returns (inserted, updated). Row count deltas tell us new vs updated, since
    an upsert never deletes.
    """
    if not rows:
        return (0, 0)
    before  = _count(conn, "filings")
    cols    = ", ".join(FILING_COLUMNS)
    holders = ", ".join("?" for _ in FILING_COLUMNS)
    updates = ", ".join(f"{c}=excluded.{c}" for c in FILING_COLUMNS if c != "accession_no")
    sql = (
        f"INSERT INTO filings ({cols}, updated_at) VALUES ({holders}, datetime('now')) "
        f"ON CONFLICT(accession_no) DO UPDATE SET {updates}, updated_at=datetime('now')"
    )
    payload = [tuple(r.get(c) for c in FILING_COLUMNS) for r in rows]
    with conn:
        conn.executemany(sql, payload)
    inserted = _count(conn, "filings") - before
    return inserted, len(payload) - inserted


def upsert_prices(conn: sqlite3.Connection, rows: list) -> tuple[int, int]:
    """Insert daily closes, updating the close on (ticker, date) conflict.

    Accepts dicts with ticker/date/close, or (ticker, date, close) tuples.
    Returns (inserted, updated).
    """
    if not rows:
        return (0, 0)
    before = _count(conn, "prices")
    sql = (
        "INSERT INTO prices (ticker, date, close) VALUES (?, ?, ?) "
        "ON CONFLICT(ticker, date) DO UPDATE SET close=excluded.close"
    )
    payload = [
        (r["ticker"], r["date"], r["close"]) if isinstance(r, dict) else tuple(r)
        for r in rows
    ]
    with conn:
        conn.executemany(sql, payload)
    inserted = _count(conn, "prices") - before
    return inserted, len(payload) - inserted


def tickers_with_prices(conn: sqlite3.Connection) -> set[str]:
    """Tickers that already have at least one stored price (used to prioritise
    which tickers a scrape run should spend its API budget on)."""
    return {row[0] for row in conn.execute("SELECT DISTINCT ticker FROM prices")}


def counts(conn: sqlite3.Connection) -> dict:
    """Row counts per table, for progress reporting."""
    return {
        "filings": _count(conn, "filings"),
        "prices":  _count(conn, "prices"),
        "tickers": conn.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0],
    }
