"""Fix50 Agent CLI - manual ingestion and evaluation of opportunities.

No scraping, no platform integrations: you paste opportunities yourself.

Usage:
  python -m app.cli add --title "..." [--source ...] [--url ...]
                        [--client ...] [--market ...]
                        [--description "..." | --description-file FILE]
                        (description read from stdin if not given)
  python -m app.cli list [--status candidate] [--limit N]
  python -m app.cli show ID
  python -m app.cli eval [--id ID | --status STATUS] [--limit N]
  python -m app.cli export [--format csv|json] [--out FILE]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys

from app.config import Settings
from app.db.repository import OpportunityRepository
from app.models import Opportunity, OpportunityInput, Status
from app.services.ai_provider import build_provider
from app.services.analyzer import OpportunityAnalyzer
from app.services.exceptions import AIProviderError
from app.services.pipeline import analyze_and_store
from app.services.proposal_generator import ProposalGenerator
from app.services.scorer import OpportunityScorer

# CSV columns used for the manual evaluation of real opportunities.
EXPORT_COLUMNS = [
    "id", "source", "title", "analysis_summary", "score",
    "classification", "suggested_price", "proposal", "status",
]


def _analysis_summary(opportunity: Opportunity) -> str:
    analysis = opportunity.analysis
    if analysis is None:
        return ""
    skills = ", ".join(analysis.required_skills)
    return (
        f"{analysis.problem} | skills: {skills} | difficulty: "
        f"{analysis.difficulty.value} | time: {analysis.estimated_time}"
    )


def _export_row(opportunity: Opportunity) -> dict:
    return {
        "id": opportunity.id,
        "source": opportunity.input.source,
        "title": opportunity.input.title,
        "analysis_summary": _analysis_summary(opportunity),
        "score": opportunity.score.total if opportunity.score else None,
        "classification": (
            opportunity.score.classification.value if opportunity.score else None
        ),
        "suggested_price": (
            opportunity.proposal.suggested_price if opportunity.proposal else None
        ),
        "proposal": opportunity.proposal.message if opportunity.proposal else None,
        "status": opportunity.status.value,
    }


def _read_description(args: argparse.Namespace) -> str | None:
    if args.description:
        return args.description
    if args.description_file:
        with open(args.description_file, encoding="utf-8") as handle:
            return handle.read().strip()
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            return piped
    return input("Paste the opportunity description: ").strip() or None


def _eval_block(opportunity: Opportunity) -> str:
    """Human-reviewable block with every agent output needed for Day 3 evaluation.

    Mirrors the fields in docs/day3_evaluation.md so it can be copied over
    while filling in the human review columns. No product changes — this only
    prints what the agent already produced.
    """
    inp = opportunity.input
    analysis = opportunity.analysis
    score = opportunity.score
    proposal = opportunity.proposal
    lines = [
        f"opportunity_id: {opportunity.id}",
        f"source: {inp.source or '-'}",
        f"title: {inp.title}",
        f"url: {inp.url or '-'}",
        f"client: {inp.client_name or '-'}",
        f"market: {inp.market or '-'}",
        f"status: {opportunity.status.value}",
        "",
        "AGENT ANALYSIS:",
    ]
    if analysis is None:
        lines.append("  (no analysis stored)")
    else:
        lines += [
            f"  problem: {analysis.problem}",
            f"  required_skills: {', '.join(analysis.required_skills)}",
            f"  difficulty: {analysis.difficulty.value}",
            f"  estimated_execution_time: {analysis.estimated_time}",
            f"  estimated_price_range: "
            f"{analysis.price_min:.0f} - {analysis.price_max:.0f}",
            f"  confidence: {analysis.confidence}",
            "  business_value_explanation: "
            f"{analysis.business_value_explanation or '-'}",
            "  missing_information: "
            f"{', '.join(analysis.missing_information or []) or '-'}",
        ]
    lines += ["", "SCORE:"]
    if score is None:
        lines.append("  (no score stored)")
    else:
        lines += [
            f"  deterministic_score: {score.total}",
            f"  classification: {score.classification.value}",
        ]
    lines += ["", "PROPOSAL:"]
    if proposal is None:
        lines.append("  (no proposal - score < 70)")
    else:
        lines += [
            f"  suggested_fixed_price: {proposal.suggested_price:.0f}",
            f"  delivery_estimate: {proposal.delivery_estimate}",
            f"  problem_summary: {proposal.problem_summary}",
            f"  proposed_solution: {proposal.proposed_solution}",
            "",
            proposal.message,
        ]
    lines += ["", "INPUT DESCRIPTION:", inp.description or "-"]
    return "\n".join(lines)


def _cmd_add(args: argparse.Namespace, settings: Settings) -> int:
    opportunity_input = OpportunityInput(
        title=args.title,
        source=args.source,
        description=_read_description(args),
        url=args.url,
        client_name=args.client,
        market=args.market,
    )
    try:
        provider = build_provider(settings.ai_provider, settings)
        services = (
            OpportunityAnalyzer(provider),
            OpportunityScorer(),
            ProposalGenerator(),
            OpportunityRepository(settings.database_path),
        )
        opportunity = analyze_and_store(*services, opportunity_input)
    except AIProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"id: {opportunity.id}")
    print(f"title: {opportunity.input.title}")
    print(f"score: {opportunity.score.total} ({opportunity.score.classification.value})")
    print(f"status: {opportunity.status.value}")
    if opportunity.proposal is not None:
        print(f"suggested price: ${opportunity.proposal.suggested_price:.0f}")
        print("--- proposal draft ---")
        print(opportunity.proposal.message)
    else:
        print("suggested price: - (rejected, no proposal drafted)")
    return 0


def _cmd_list(args: argparse.Namespace, settings: Settings) -> int:
    repository = OpportunityRepository(settings.database_path)
    status = Status(args.status) if args.status else None
    for opportunity in repository.list(status=status, limit=args.limit):
        score = opportunity.score.total if opportunity.score else "-"
        classification = (
            opportunity.score.classification.value if opportunity.score else "-"
        )
        print(
            f"{opportunity.id:>4} | {score:>3} | {classification:<8} | "
            f"{opportunity.status.value:<9} | {opportunity.input.title}"
        )
    return 0


def _cmd_show(args: argparse.Namespace, settings: Settings) -> int:
    repository = OpportunityRepository(settings.database_path)
    opportunity = repository.get(args.id)
    if opportunity is None:
        print(f"error: opportunity {args.id} not found", file=sys.stderr)
        return 1
    print(json.dumps(_export_row(opportunity), indent=2, ensure_ascii=False))
    return 0


def _cmd_eval(args: argparse.Namespace, settings: Settings) -> int:
    """Print the full agent evaluation data for human review (Day 3)."""
    repository = OpportunityRepository(settings.database_path)
    if args.id is not None:
        opportunity = repository.get(args.id)
        if opportunity is None:
            print(f"error: opportunity {args.id} not found", file=sys.stderr)
            return 1
        opportunities = [opportunity]
    else:
        status = Status(args.status) if args.status else None
        opportunities = list(repository.list(status=status, limit=args.limit))
    if not opportunities:
        print("no opportunities matching the filter", file=sys.stderr)
        return 1
    print("\n\n====\n\n".join(_eval_block(opportunity) for opportunity in opportunities))
    return 0


def _cmd_export(args: argparse.Namespace, settings: Settings) -> int:
    repository = OpportunityRepository(settings.database_path)
    status = Status(args.status) if args.status else None
    rows = [
        _export_row(opportunity)
        for opportunity in repository.list(status=status, limit=args.limit)
    ]

    if args.format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        content = buffer.getvalue()
    else:
        content = json.dumps(rows, indent=2, ensure_ascii=False)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(content)
        print(f"exported {len(rows)} opportunities to {args.out}")
    else:
        print(content)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fix50", description="Fix50 Agent - manual opportunity ingestion"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="paste and analyze one opportunity")
    add.add_argument("--title", required=True, help="short opportunity title")
    add.add_argument("--source", help="where it came from, e.g. a forum or a friend")
    add.add_argument("--url", help="link to the original post")
    add.add_argument("--client", help="client or company name")
    add.add_argument("--market", help="market/language, e.g. 'DE / German'")
    add.add_argument("--description", help="full opportunity text")
    add.add_argument("--description-file", help="file containing the full text")
    add.set_defaults(func=_cmd_add)

    list_parser = sub.add_parser("list", help="list stored opportunities")
    list_parser.add_argument("--status", choices=[s.value for s in Status])
    list_parser.add_argument("--limit", type=int, default=100)
    list_parser.set_defaults(func=_cmd_list)

    show = sub.add_parser("show", help="show one opportunity as JSON")
    show.add_argument("id", type=int)
    show.set_defaults(func=_cmd_show)

    eval_parser = sub.add_parser(
        "eval",
        help="print full agent evaluation data for human review (Day 3)",
    )
    eval_parser.add_argument("--id", type=int, help="print one opportunity")
    eval_parser.add_argument("--status", choices=[s.value for s in Status])
    eval_parser.add_argument("--limit", type=int, default=100)
    eval_parser.set_defaults(func=_cmd_eval)

    export = sub.add_parser("export", help="export opportunities for evaluation")
    export.add_argument("--format", choices=["csv", "json"], default="csv")
    export.add_argument("--out", help="write to file instead of stdout")
    export.add_argument("--status", choices=[s.value for s in Status])
    export.add_argument("--limit", type=int, default=100)
    export.set_defaults(func=_cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args, Settings.from_env())


if __name__ == "__main__":
    raise SystemExit(main())
