from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    price_usd REAL NOT NULL,
    market_cap_usd REAL,
    volume_24h_usd REAL,
    change_24h_percent REAL,
    captured_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_coin_time
    ON market_snapshots (coin_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    change_24h_percent REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS news_articles (
    url_hash TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    published_at TEXT,
    summary TEXT,
    coins TEXT NOT NULL,
    image TEXT,
    fetched_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_published
    ON news_articles (published_at DESC);
"""


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db_path: Path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize_database() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)
        # Idempotent migration for databases created before the image column.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(news_articles)")}
        if "image" not in columns:
            conn.execute("ALTER TABLE news_articles ADD COLUMN image TEXT")


def save_snapshots(rows: list[dict]) -> int:
    if not rows:
        return 0
    captured_at = datetime.now(timezone.utc).isoformat()
    values = [
        (
            row["id"], row["symbol"], row["name"], row["current_price"],
            row.get("market_cap"), row.get("total_volume"),
            row.get("price_change_percentage_24h"), captured_at,
        )
        for row in rows
    ]
    with connection() as conn:
        conn.executemany(
            """INSERT INTO market_snapshots
            (coin_id, symbol, name, price_usd, market_cap_usd, volume_24h_usd,
             change_24h_percent, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
    return len(values)


def recent_snapshots(coin_id: str | None = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM market_snapshots"
    params: list[object] = []
    if coin_id:
        query += " WHERE coin_id = ?"
        params.append(coin_id)
    query += " ORDER BY captured_at DESC LIMIT ?"
    params.append(limit)
    with connection() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def save_alert(coin_id: str, severity: str, message: str, change: float) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO alerts (coin_id, severity, message, change_24h_percent, created_at) VALUES (?, ?, ?, ?, ?)",
            (coin_id, severity, message, change, datetime.now(timezone.utc).isoformat()),
        )


def recent_alerts(limit: int = 20) -> list[dict]:
    with connection() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()]
