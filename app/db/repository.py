"""Repository for Opportunity persistence."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.db.database import connect, init_db
from app.models import (
    Analysis,
    Classification,
    Difficulty,
    Opportunity,
    OpportunityInput,
    Proposal,
    ScoreBreakdown,
    ScoreResult,
    Status,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _analysis_to_row(analysis: Analysis | None) -> dict[str, object]:
    if analysis is None:
        return {}
    return {
        "problem": analysis.problem,
        "required_skills": json.dumps(analysis.required_skills),
        "difficulty": analysis.difficulty.value,
        "estimated_time": analysis.estimated_time,
        "estimated_hours": analysis.estimated_hours,
        "price_min": analysis.price_min,
        "price_max": analysis.price_max,
        "confidence": analysis.confidence,
        "business_value_explanation": analysis.business_value_explanation,
        "missing_information": (
            json.dumps(analysis.missing_information)
            if analysis.missing_information is not None
            else None
        ),
    }


def _row_to_analysis(row: sqlite3.Row) -> Analysis | None:
    if row["problem"] is None:
        return None
    return Analysis(
        problem=row["problem"],
        required_skills=json.loads(row["required_skills"] or "[]"),
        difficulty=Difficulty(row["difficulty"]),
        estimated_time=row["estimated_time"],
        estimated_hours=row["estimated_hours"],
        price_min=row["price_min"],
        price_max=row["price_max"],
        confidence=row["confidence"],
        business_value_explanation=row["business_value_explanation"],
        missing_information=(
            json.loads(row["missing_information"])
            if row["missing_information"] is not None
            else None
        ),
    )


def _score_to_row(score: ScoreResult | None) -> dict[str, object]:
    if score is None:
        return {}
    return {
        "score": score.total,
        "score_breakdown": json.dumps(score.breakdown.__dict__),
        "classification": score.classification.value,
    }


def _row_to_score(row: sqlite3.Row) -> ScoreResult | None:
    if row["score"] is None:
        return None
    breakdown_raw = json.loads(row["score_breakdown"] or "{}")
    return ScoreResult(
        total=row["score"],
        breakdown=ScoreBreakdown(**breakdown_raw),
        classification=Classification(row["classification"]),
    )


def _row_to_proposal(row: sqlite3.Row) -> Proposal | None:
    if row["proposal"] is None:
        return None
    return Proposal(**json.loads(row["proposal"]))


def _proposal_to_row(proposal: Proposal | None) -> dict[str, object]:
    if proposal is None:
        return {}
    return {"proposal": json.dumps(proposal.__dict__)}


class OpportunityRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        init_db(db_path)

    def create(self, opportunity: Opportunity) -> Opportunity:
        now = _utc_now()
        row: dict[str, object] = {
            "source": opportunity.input.source,
            "title": opportunity.input.title,
            "description": opportunity.input.description,
            "url": opportunity.input.url,
            "client_name": opportunity.input.client_name,
            "market": opportunity.input.market,
            "status": opportunity.status.value,
            "created_at": now,
            "updated_at": now,
        }
        row.update(_analysis_to_row(opportunity.analysis))
        row.update(_score_to_row(opportunity.score))
        row.update(_proposal_to_row(opportunity.proposal))

        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        with connect(self._db_path) as conn:
            cursor = conn.execute(
                f"INSERT INTO opportunities ({columns}) VALUES ({placeholders})",
                tuple(row.values()),
            )
            opportunity.id = int(cursor.lastrowid)
            opportunity.created_at = now
            opportunity.updated_at = now
        return opportunity

    def get(self, opportunity_id: int) -> Opportunity | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
            ).fetchone()
        return self._to_domain(row) if row else None

    def list(self, status: Status | None = None, limit: int = 100) -> list[Opportunity]:
        query = "SELECT * FROM opportunities"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY id DESC LIMIT ?"
        params += (limit,)
        with connect(self._db_path) as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._to_domain(row) for row in rows]

    def update_status(self, opportunity_id: int, status: Status) -> Opportunity | None:
        with connect(self._db_path) as conn:
            cursor = conn.execute(
                "UPDATE opportunities SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, _utc_now(), opportunity_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get(opportunity_id)

    @staticmethod
    def _to_domain(row: sqlite3.Row) -> Opportunity:
        return Opportunity(
            id=row["id"],
            input=OpportunityInput(
                title=row["title"],
                source=row["source"],
                description=row["description"],
                url=row["url"],
                client_name=row["client_name"],
                market=row["market"],
            ),
            status=Status(row["status"]),
            analysis=_row_to_analysis(row),
            score=_row_to_score(row),
            proposal=_row_to_proposal(row),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
