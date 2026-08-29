"""Tests for the schema migration of pre-Day-2 databases."""
from __future__ import annotations

import json
import sqlite3

from app.db.database import init_db
from app.db.repository import OpportunityRepository
from app.models import (
    Analysis,
    Difficulty,
    Opportunity,
    OpportunityInput,
    Status,
)

_OLD_SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT,
    title            TEXT NOT NULL,
    description      TEXT,
    url              TEXT,
    client_name      TEXT,
    market           TEXT,
    problem          TEXT,
    required_skills  TEXT,
    difficulty       TEXT,
    estimated_time   TEXT,
    estimated_hours  REAL,
    price_min        REAL,
    price_max        REAL,
    confidence       REAL,
    score            INTEGER,
    score_breakdown  TEXT,
    classification   TEXT,
    proposal         TEXT,
    status           TEXT NOT NULL DEFAULT 'new',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
"""


def test_old_database_is_migrated_and_old_rows_still_load(tmp_path):
    db_path = str(tmp_path / "old.db")

    # Simulate a V1 database with a legacy row (no Day-2 columns).
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        conn.execute(
            "INSERT INTO opportunities (title, problem, required_skills, difficulty,"
            " estimated_time, price_min, price_max, confidence, score,"
            " score_breakdown, classification, status, created_at, updated_at)"
            " VALUES ('Legacy fix', 'Old problem', '[\"sql\"]', 'medium',"
            " '1-2 days', 100, 200, 0.8, 75, '{\"problem_clarity\": 20,"
            " \"business_value\": 15, \"speed\": 16, \"explainability\": 7,"
            " \"contactability\": 10, \"credibility\": 7}', 'candidate',"
            " 'candidate', '2026-01-01T00:00:00+00:00',"
            " '2026-01-01T00:00:00+00:00')"
        )

    init_db(db_path)  # must ALTER TABLE, not fail

    repository = OpportunityRepository(db_path)

    # Legacy row loads with the new fields defaulting to None/[].
    legacy = repository.get(1)
    assert legacy is not None
    assert legacy.analysis.business_value_explanation is None
    assert legacy.analysis.missing_information is None

    # New rows persist and round-trip the Day-2 fields.
    created = repository.create(
        Opportunity(
            id=None,
            input=OpportunityInput(title="New fix"),
            status=Status.CANDIDATE,
            analysis=Analysis(
                problem="New problem",
                required_skills=["python"],
                difficulty=Difficulty.EASY,
                estimated_time="4 hours",
                estimated_hours=4.0,
                price_min=50.0,
                price_max=120.0,
                confidence=0.9,
                business_value_explanation="Saves hours weekly.",
                missing_information=["access details"],
            ),
        )
    )
    fetched = repository.get(created.id)
    assert fetched.analysis.business_value_explanation == "Saves hours weekly."
    assert fetched.analysis.missing_information == ["access details"]
    # legacy row untouched
    with sqlite3.connect(db_path) as conn:
        missing_values = conn.execute(
            "SELECT business_value_explanation, missing_information"
            " FROM opportunities WHERE id = 1"
        ).fetchone()
    assert missing_values[0] is None
    assert missing_values[1] is None
