"""OpportunityScorer: deterministic 0-100 scoring based on the V1 rubric.

Rubric (total 100):
  - Is the problem clear?                    /25
  - Does solving it provide business value?  /25
  - Can it be completed quickly?             /20
  - Is the solution easy to explain?         /10
  - Can the client be contacted?             /10
  - Is the opportunity/client credible?      /10

Classification:
  score < 70  -> rejected
  70 <= < 85  -> candidate
  score >= 85 -> strong opportunity
"""
from __future__ import annotations

from app.models import (
    Analysis,
    Classification,
    Difficulty,
    OpportunityInput,
    ScoreBreakdown,
    ScoreResult,
)

_MAX_SCORES = {
    "problem_clarity": 25,
    "business_value": 25,
    "speed": 20,
    "explainability": 10,
    "contactability": 10,
    "credibility": 10,
}

# Words that hint the problem is tied to money/customers/growth.
_VALUE_KEYWORDS = (
    "revenue", "sales", "customer", "client", "orders", "conversion",
    "leads", "growth", "profit", "invoice", "payment", "checkout",
    "automate", "automation", "cost", "efficiency", "seo", "traffic",
    "retention", "churn", "signups", "subscribers",
)


def classify(total: int) -> Classification:
    if total < 70:
        return Classification.REJECTED
    if total < 85:
        return Classification.CANDIDATE
    return Classification.STRONG


class OpportunityScorer:
    """Scores (OpportunityInput, Analysis) pairs. Fully deterministic."""

    def score(self, opportunity: OpportunityInput, analysis: Analysis) -> ScoreResult:
        breakdown = ScoreBreakdown(
            problem_clarity=self._problem_clarity(opportunity, analysis),
            business_value=self._business_value(opportunity, analysis),
            speed=self._speed(analysis),
            explainability=self._explainability(analysis),
            contactability=self._contactability(opportunity),
            credibility=self._credibility(opportunity, analysis),
        )
        total = sum(
            min(getattr(breakdown, criterion), max_score)
            for criterion, max_score in _MAX_SCORES.items()
        )
        return ScoreResult(
            total=total, breakdown=breakdown, classification=classify(total)
        )

    # --- criteria -------------------------------------------------------

    def _problem_clarity(self, opportunity: OpportunityInput, analysis: Analysis) -> int:
        score = 0
        if analysis.problem:
            score += 12
        if len(analysis.problem) >= 40:
            score += 8
        if (opportunity.description or "").strip():
            score += 5
        return min(score, _MAX_SCORES["problem_clarity"])

    def _business_value(self, opportunity: OpportunityInput, analysis: Analysis) -> int:
        text = " ".join(
            part
            for part in (
                opportunity.title,
                opportunity.description or "",
                analysis.problem,
            )
            if part
        ).lower()
        hits = sum(1 for keyword in _VALUE_KEYWORDS if keyword in text)
        return min(5 * hits, _MAX_SCORES["business_value"])

    def _speed(self, analysis: Analysis) -> int:
        hours = analysis.estimated_hours
        if hours is None:
            return 10
        if hours <= 4:
            return 20
        if hours <= 8:
            return 16
        if hours <= 16:
            return 12
        if hours <= 40:
            return 7
        return 3

    def _explainability(self, analysis: Analysis) -> int:
        return {
            Difficulty.EASY: 10,
            Difficulty.MEDIUM: 7,
            Difficulty.HARD: 3,
            Difficulty.UNKNOWN: 5,
        }[analysis.difficulty]

    def _contactability(self, opportunity: OpportunityInput) -> int:
        if opportunity.url and opportunity.client_name:
            return 10
        if opportunity.url or opportunity.client_name:
            return 6
        return 2

    def _credibility(self, opportunity: OpportunityInput, analysis: Analysis) -> int:
        score = 0
        if opportunity.source:
            score += 5
        if opportunity.url:
            score += 3
        if analysis.confidence >= 0.7:
            score += 2
        return min(score, _MAX_SCORES["credibility"])
