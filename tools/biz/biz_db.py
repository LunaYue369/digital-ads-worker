#!/usr/bin/env python3
"""
SQLite schema and shared DB utilities for biz tools.

DB location: data/pos/{industry}.db
"""
import sqlite3
from pathlib import Path

DB_DIR = Path(__file__).parent.parent.parent / "data" / "pos"


def get_db_path(industry: str) -> Path:
    return DB_DIR / f"{industry}.db"


def get_conn(industry: str) -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path(industry))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(industry: str):
    """Create tables if they don't exist."""
    conn = get_conn(industry)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS catalog (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,
            price       REAL NOT NULL,
            cost        REAL NOT NULL,
            active      INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              TEXT PRIMARY KEY,
            created_at      TEXT NOT NULL,
            date            TEXT NOT NULL,
            hour            INTEGER NOT NULL,
            day_of_week     INTEGER NOT NULL,
            table_no        TEXT,
            covers          INTEGER DEFAULT 1,
            employee_id     TEXT,
            order_type      TEXT DEFAULT 'dine_in',
            subtotal        REAL NOT NULL,
            discount        REAL DEFAULT 0,
            tax             REAL DEFAULT 0,
            tip             REAL DEFAULT 0,
            total           REAL NOT NULL,
            payment_method  TEXT DEFAULT 'credit',
            void            INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS line_items (
            id              TEXT PRIMARY KEY,
            transaction_id  TEXT NOT NULL,
            item_id         TEXT NOT NULL,
            item_name       TEXT NOT NULL,
            category        TEXT NOT NULL,
            qty             INTEGER NOT NULL,
            unit_price      REAL NOT NULL,
            unit_cost       REAL NOT NULL,
            total_price     REAL NOT NULL,
            total_cost      REAL NOT NULL,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id)
        );

        CREATE INDEX IF NOT EXISTS idx_txn_date        ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_txn_created_at  ON transactions(created_at);
        CREATE INDEX IF NOT EXISTS idx_li_txn_id       ON line_items(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_li_item_id      ON line_items(item_id);
        CREATE INDEX IF NOT EXISTS idx_li_date         ON line_items(transaction_id);
    """)
    conn.commit()
    conn.close()
