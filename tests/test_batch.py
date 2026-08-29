from __future__ import annotations

import json

from app.batch import run_batch
from app.config import Settings
from app.db.repository import OpportunityRepository


def _settings(tmp_path):
    return Settings(ai_provider="mock", database_path=str(tmp_path / "batch.db"))


def test_batch_stores_valid_rows(tmp_path, capsys):
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([
        {"title": "Fix checkout bug", "source": "upwork", "url": "https://example.com/1", "client_name": "Acme", "description": "Customers cannot complete checkout and orders and revenue are being lost every day. Fix the payment flow quickly."},
        {"title": "Fix responsive WordPress page", "source": "upwork", "url": "https://example.com/2", "description": "Existing WordPress page overlaps on mobile and needs responsive CSS fixes."}
    ]), encoding="utf-8")
    settings = _settings(tmp_path)
    assert run_batch(str(path), settings) == 0
    assert len(OpportunityRepository(settings.database_path).list()) == 2
    assert "SUMMARY input=2 stored=2" in capsys.readouterr().out


def test_batch_skips_duplicates(tmp_path, capsys):
    path = tmp_path / "batch.json"
    row = {"title": "Fix API", "source": "upwork", "url": "https://example.com/api", "description": "Fix one failing API endpoint in an existing application."}
    path.write_text(json.dumps([row]), encoding="utf-8")
    settings = _settings(tmp_path)
    assert run_batch(str(path), settings) == 0
    assert run_batch(str(path), settings) == 0
    assert len(OpportunityRepository(settings.database_path).list()) == 1
    assert "skipped=1" in capsys.readouterr().out


def test_batch_continues_after_invalid_row(tmp_path, capsys):
    path = tmp_path / "batch.json"
    path.write_text(json.dumps([{"source": "upwork"}, {"title": "Valid job", "description": "A clear small technical fix."}]), encoding="utf-8")
    settings = _settings(tmp_path)
    assert run_batch(str(path), settings) == 2
    assert len(OpportunityRepository(settings.database_path).list()) == 1
    captured = capsys.readouterr()
    assert "invalid input" in captured.err
    assert "stored=1" in captured.out
