"""Run a JSON batch of real opportunities through the existing Fix50 pipeline.

Usage: python -m app.batch docs/day6_real_batch.json
This analyzes supplied snapshots only; it never scrapes or contacts clients.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import Settings
from app.db.repository import OpportunityRepository
from app.models import OpportunityInput
from app.services.ai_provider import build_provider
from app.services.analyzer import OpportunityAnalyzer
from app.services.exceptions import AIProviderError
from app.services.pipeline import analyze_and_store
from app.services.proposal_generator import ProposalGenerator
from app.services.scorer import OpportunityScorer

_ALLOWED_FIELDS = {"title", "source", "description", "url", "client_name", "market"}


def _key(item: OpportunityInput) -> tuple[str, str]:
    return ((item.url or "").strip().lower(), item.title.strip().lower())


def _parse_input(item: object) -> OpportunityInput:
    if not isinstance(item, dict):
        raise ValueError("opportunity must be a JSON object")
    unknown = set(item) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")
    title = item.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be a non-empty string")
    return OpportunityInput(**item)


def run_batch(path: str, settings: Settings) -> int:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("batch JSON must be a list of opportunity objects")

    repository = OpportunityRepository(settings.database_path)
    existing = {_key(row.input) for row in repository.list(limit=10000)}
    provider = build_provider(settings.ai_provider, settings)
    analyzer, scorer, proposals = OpportunityAnalyzer(provider), OpportunityScorer(), ProposalGenerator()
    stats = {"input": len(raw), "stored": 0, "skipped": 0, "failed": 0, "candidate": 0, "strong": 0, "rejected": 0}

    for index, item in enumerate(raw, start=1):
        try:
            opportunity_input = _parse_input(item)
        except (TypeError, ValueError) as exc:
            stats["failed"] += 1
            print(f"[{index}] invalid input: {exc}", file=sys.stderr)
            continue
        key = _key(opportunity_input)
        if key in existing:
            stats["skipped"] += 1
            print(f"[{index}] skip duplicate: {opportunity_input.title}")
            continue
        try:
            opportunity = analyze_and_store(analyzer, scorer, proposals, repository, opportunity_input)
        except AIProviderError as exc:
            stats["failed"] += 1
            print(f"[{index}] provider error: {opportunity_input.title}: {exc}", file=sys.stderr)
            continue
        existing.add(key)
        stats["stored"] += 1
        classification = opportunity.score.classification.value
        stats[classification] += 1
        price = f"${opportunity.proposal.suggested_price:.0f}" if opportunity.proposal else "-"
        print(f"[{index}] id={opportunity.id} score={opportunity.score.total} class={classification} price={price} | {opportunity.input.title}")

    print("SUMMARY " + " ".join(f"{key}={value}" for key, value in stats.items()))
    return 0 if stats["failed"] == 0 else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a supplied Fix50 opportunity batch")
    parser.add_argument("path", help="JSON file containing a list of opportunities")
    args = parser.parse_args(argv)
    try:
        return run_batch(args.path, Settings.from_env())
    except (OSError, ValueError, json.JSONDecodeError, AIProviderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
