"""Tests for the manual ingestion CLI (python -m app.cli)."""
from __future__ import annotations

import csv
import io
import json
import sys

import pytest

from app.cli import main
from tests.conftest import GOOD_OPPORTUNITY


@pytest.fixture()
def cli_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "cli.db"))
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


class TestAddCommand:
    def test_add_via_description_flag(self, cli_env, capsys):
        code = main(
            [
                "add",
                "--title", GOOD_OPPORTUNITY["title"],
                "--source", GOOD_OPPORTUNITY["source"],
                "--description", GOOD_OPPORTUNITY["description"],
                "--url", GOOD_OPPORTUNITY["url"],
                "--client", GOOD_OPPORTUNITY["client_name"],
                "--market", GOOD_OPPORTUNITY["market"],
            ]
        )
        assert code == 0
        out = capsys.readouterr().out
        assert "id: 1" in out
        assert "score:" in out
        assert "candidate" in out
        assert "suggested price:" in out

    def test_add_reads_description_from_stdin(self, cli_env, monkeypatch, capsys):
        monkeypatch.setattr(
            sys, "stdin", io.StringIO(GOOD_OPPORTUNITY["description"] + "\n")
        )
        code = main(["add", "--title", GOOD_OPPORTUNITY["title"]])
        assert code == 0
        assert "score:" in capsys.readouterr().out

    def test_add_via_description_file(self, cli_env, capsys):
        description_file = cli_env / "opportunity.txt"
        description_file.write_text(GOOD_OPPORTUNITY["description"])
        code = main(
            [
                "add",
                "--title", GOOD_OPPORTUNITY["title"],
                "--description-file", str(description_file),
            ]
        )
        assert code == 0
        assert "id: 1" in capsys.readouterr().out

    def test_add_provider_error_fails_cleanly(self, cli_env, monkeypatch, capsys):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        code = main(["add", "--title", "Anything", "--description", "Some text"])
        assert code == 1
        assert "OPENAI_API_KEY" in capsys.readouterr().err


class TestListShowExport:
    def _seed(self, capsys=None):
        main(
            [
                "add",
                "--title", GOOD_OPPORTUNITY["title"],
                "--source", GOOD_OPPORTUNITY["source"],
                "--description", GOOD_OPPORTUNITY["description"],
                "--client", GOOD_OPPORTUNITY["client_name"],
            ]
        )
        if capsys is not None:
            capsys.readouterr()

    def test_list_shows_stored_opportunities(self, cli_env, capsys):
        self._seed()
        code = main(["list"])
        assert code == 0
        out = capsys.readouterr().out
        assert GOOD_OPPORTUNITY["title"] in out
        assert "candidate" in out

    def test_show_prints_full_evaluation_record(self, cli_env, capsys):
        self._seed(capsys)
        code = main(["show", "1"])
        assert code == 0
        record = json.loads(capsys.readouterr().out)
        assert record["id"] == 1
        assert record["source"] == GOOD_OPPORTUNITY["source"]
        assert record["analysis_summary"]
        assert record["classification"] == "candidate"
        assert record["suggested_price"] >= 50
        assert "proposal" in record and record["proposal"]
        assert record["status"] == "candidate"

    def test_show_missing_id_fails_cleanly(self, cli_env, capsys):
        assert main(["show", "999"]) == 1
        assert "not found" in capsys.readouterr().err

    def test_export_csv_contains_evaluation_columns(self, cli_env, capsys):
        self._seed(capsys)
        out_file = cli_env / "evaluation.csv"
        code = main(["export", "--format", "csv", "--out", str(out_file)])
        assert code == 0
        with open(out_file, encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "1"
        assert row["source"] == GOOD_OPPORTUNITY["source"]
        assert row["title"] == GOOD_OPPORTUNITY["title"]
        assert "skills:" in row["analysis_summary"]
        assert int(row["score"]) >= 70
        assert row["classification"] == "candidate"
        assert float(row["suggested_price"]) >= 50
        assert "Hi" in row["proposal"]
        assert row["status"] == "candidate"

    def test_export_json(self, cli_env, capsys):
        self._seed(capsys)
        code = main(["export", "--format", "json"])
        assert code == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 1
        assert rows[0]["classification"] == "candidate"

    def test_export_with_status_filter(self, cli_env, capsys):
        main(["add", "--title", "Tiny task", "--description", "short"])
        capsys.readouterr()
        self._seed(capsys)
        code = main(["export", "--format", "json", "--status", "rejected"])
        assert code == 0
        rows = json.loads(capsys.readouterr().out)
        assert len(rows) == 1
        assert rows[0]["classification"] == "rejected"
        assert rows[0]["proposal"] is None


class TestEvalCommand:
    def _seed(self, capsys=None):
        main(
            [
                "add",
                "--title", GOOD_OPPORTUNITY["title"],
                "--source", GOOD_OPPORTUNITY["source"],
                "--description", GOOD_OPPORTUNITY["description"],
                "--client", GOOD_OPPORTUNITY["client_name"],
            ]
        )
        if capsys is not None:
            capsys.readouterr()

    def test_eval_prints_all_comparison_fields(self, cli_env, capsys):
        self._seed(capsys)
        code = main(["eval"])
        assert code == 0
        out = capsys.readouterr().out
        assert "opportunity_id: 1" in out
        assert "source: upwork" in out
        assert GOOD_OPPORTUNITY["title"] in out
        assert "AGENT ANALYSIS:" in out
        assert "problem: " in out
        assert "required_skills:" in out
        assert "difficulty:" in out
        assert "estimated_execution_time:" in out
        assert "estimated_price_range:" in out
        assert "confidence:" in out
        assert "business_value_explanation:" in out
        assert "missing_information:" in out
        assert "deterministic_score:" in out
        assert "classification: candidate" in out
        assert "suggested_fixed_price:" in out
        assert "proposed_solution:" in out
        assert "Hi" in out
        assert "INPUT DESCRIPTION:" in out

    def test_eval_by_id(self, cli_env, capsys):
        self._seed(capsys)
        assert main(["eval", "--id", "1"]) == 0
        assert "opportunity_id: 1" in capsys.readouterr().out

    def test_eval_missing_id_fails_cleanly(self, cli_env, capsys):
        assert main(["eval", "--id", "999"]) == 1
        assert "not found" in capsys.readouterr().err

    def test_eval_empty_db_fails_cleanly(self, cli_env, capsys):
        assert main(["eval"]) == 1
        assert "no opportunities" in capsys.readouterr().err

    def test_eval_status_filter(self, cli_env, capsys):
        main(["add", "--title", "Tiny task", "--description", "short"])
        capsys.readouterr()
        self._seed(capsys)
        code = main(["eval", "--status", "rejected"])
        assert code == 0
        out = capsys.readouterr().out
        assert "Tiny task" in out
        assert "Fix broken checkout" not in out
