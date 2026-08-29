"""Tests for the V1 scoring rubric."""
from __future__ import annotations

import pytest

from app.models import Analysis, Difficulty, OpportunityInput
from app.services.scorer import OpportunityScorer, classify


def _analysis(
    problem: str = "The checkout fails and the client loses orders.",
    skills: list[str] | None = None,
    difficulty: Difficulty = Difficulty.MEDIUM,
    estimated_hours: float | None = 8.0,
    confidence: float = 0.7,
) -> Analysis:
    return Analysis(
        problem=problem,
        required_skills=skills or ["shopify"],
        difficulty=difficulty,
        estimated_time="1-2 days",
        estimated_hours=estimated_hours,
        price_min=100.0,
        price_max=300.0,
        confidence=confidence,
    )


class TestClassify:
    @pytest.mark.parametrize(
        "total,expected",
        [
            (0, "rejected"),
            (69, "rejected"),
            (70, "candidate"),
            (84, "candidate"),
            (85, "strong"),
            (100, "strong"),
        ],
    )
    def test_classification_boundaries(self, total: int, expected: str):
        assert classify(total).value == expected


class TestScorer:
    def setup_method(self) -> None:
        self.scorer = OpportunityScorer()

    def _score(self, **kwargs):
        opportunity = OpportunityInput(
            title=kwargs.get("title", "Fix checkout bug"),
            source=kwargs.get("source", "upwork"),
            description=kwargs.get("description", "x" * 50),
            url=kwargs.get("url", "https://example.com/job"),
            client_name=kwargs.get("client_name", "Acme"),
        )
        return self.scorer.score(opportunity, kwargs.get("analysis", _analysis()))

    def test_breakdown_within_rubric_limits(self):
        result = self._score()
        b = result.breakdown
        assert b.problem_clarity <= 25
        assert b.business_value <= 25
        assert b.speed <= 20
        assert b.explainability <= 10
        assert b.contactability <= 10
        assert b.credibility <= 10
        assert result.total == (
            b.problem_clarity + b.business_value + b.speed
            + b.explainability + b.contactability + b.credibility
        )

    def test_strong_opportunity_scores_high(self):
        result = self._score(
            description=(
                "Customers cannot pay, we lose revenue and orders every day. "
                "We need this fixed to recover sales."
            ),
            analysis=_analysis(difficulty=Difficulty.EASY, estimated_hours=4.0),
        )
        assert result.total >= 85
        assert result.classification.value == "strong"

    def test_vague_opportunity_is_rejected(self):
        result = self.scorer.score(
            OpportunityInput(title="Looking for developer"),
            _analysis(problem="", confidence=0.3),
        )
        assert result.total < 70
        assert result.classification.value == "rejected"

    def test_missing_context_lowers_contactability(self):
        with_context = self._score()
        without_context = self._score(url=None, client_name=None, source=None)
        assert without_context.breakdown.contactability < with_context.breakdown.contactability
        assert without_context.total < with_context.total

    def test_slow_work_scores_lower_speed(self):
        fast = self._score(analysis=_analysis(estimated_hours=4.0))
        slow = self._score(analysis=_analysis(estimated_hours=60.0))
        assert slow.breakdown.speed < fast.breakdown.speed
