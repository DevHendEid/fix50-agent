"""SQLite connection helpers and schema."""
from __future__ import annotations

import os
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT,
    title            TEXT NOT NULL,
    description      TEXT,
    url              TEXT,
    client_name      TEXT,
    market           TEXT,
    problem          TEXT,
    required_skills  TEXT,          -- JSON array
    difficulty       TEXT,
    estimated_time   TEXT,
    estimated_hours  REAL,
    price_min        REAL,
    price_max        REAL,
    confidence       REAL,
    business_value_explanation TEXT,
    missing_information TEXT,      -- JSON array
    score            INTEGER,
    score_breakdown  TEXT,          -- JSON object
    classification   TEXT,
    proposal         TEXT,          -- JSON object
    status           TEXT NOT NULL DEFAULT 'new',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """Open a new connection (one per operation -> thread-safe by design)."""
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after V1; older databases are migrated in init_db().
_MIGRATION_COLUMNS: dict[str, str] = {
    "business_value_explanation": "TEXT",
    "missing_information": "TEXT",
}


def init_db(db_path: str) -> None:
    """Create the schema if it does not exist yet, and migrate old databases."""
    with connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(opportunities)")}
        for column, column_type in _MIGRATION_COLUMNS.items():
            if column not in existing:
                conn.execute(
                    f"ALTER TABLE opportunities ADD COLUMN {column} {column_type}"
                )
