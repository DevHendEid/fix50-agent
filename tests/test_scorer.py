"""Tests for deterministic Fix50 scoring."""
from __future__ import annotations

import pytest

from app.models import Analysis, Difficulty, OpportunityInput
from app.services.scorer import OpportunityScorer, classify


def _analysis(problem="The checkout fails and the client loses orders.", skills=None, difficulty=Difficulty.MEDIUM, estimated_hours=8.0, confidence=0.7, price_min=100.0, price_max=300.0, business_value="Fixing this restores a useful business function and prevents lost revenue."):
    return Analysis(problem=problem, required_skills=skills or ["shopify"], difficulty=difficulty, estimated_time="1-2 days", estimated_hours=estimated_hours, price_min=price_min, price_max=price_max, confidence=confidence, business_value_explanation=business_value)


class TestClassify:
    @pytest.mark.parametrize("total,expected", [(0,"rejected"),(69,"rejected"),(70,"candidate"),(84,"candidate"),(85,"strong"),(100,"strong")])
    def test_classification_boundaries(self, total, expected):
        assert classify(total).value == expected


class TestScorer:
    def setup_method(self):
        self.scorer = OpportunityScorer()

    def _score(self, **kwargs):
        opportunity = OpportunityInput(title=kwargs.get("title", "Fix checkout bug"), source=kwargs.get("source", "upwork"), description=kwargs.get("description", "x" * 50), url=kwargs.get("url", "https://example.com/job"), client_name=kwargs.get("client_name", "Acme"))
        return self.scorer.score(opportunity, kwargs.get("analysis", _analysis()))

    def test_breakdown_within_rubric_limits(self):
        b = self._score().breakdown
        assert b.problem_clarity <= 25
        assert b.business_value <= 25
        assert b.speed <= 20
        assert b.explainability <= 10
        assert b.contactability <= 10
        assert b.credibility <= 10

    def test_strong_opportunity_scores_high(self):
        result = self._score(description="Customers cannot pay, we lose revenue and orders every day. We need this fixed to recover sales.", analysis=_analysis(difficulty=Difficulty.EASY, estimated_hours=4.0))
        assert result.total >= 85
        assert result.classification.value == "strong"

    def test_vague_opportunity_is_rejected(self):
        result = self.scorer.score(OpportunityInput(title="Looking for developer"), _analysis(problem="", confidence=0.3, business_value=""))
        assert result.total < 70
        assert result.classification.value == "rejected"

    def test_missing_context_lowers_contactability(self):
        assert self._score(url=None, client_name=None, source=None).breakdown.contactability < self._score().breakdown.contactability

    def test_slow_work_scores_lower_speed(self):
        assert self._score(analysis=_analysis(estimated_hours=60.0)).breakdown.speed < self._score(analysis=_analysis(estimated_hours=4.0)).breakdown.speed

    def test_business_value_explanation_works_without_english_keywords(self):
        result = self._score(title="إصلاح مشكلة تقنية", description="الموقع يحتاج إلى إصلاح واضح", analysis=_analysis(problem="هناك عطل واضح في الموقع", business_value="إصلاح العطل يعيد الخدمة للمتجر ويمنع خسارة العملاء."))
        assert result.breakdown.business_value >= 15

    def test_marketplace_listing_is_contactable_without_client_name(self):
        result = self._score(client_name=None, url="https://example.com/job/42", source="upwork")
        assert result.breakdown.contactability == 10

    def test_below_50_opportunity_is_economically_rejected(self):
        result = self._score(analysis=_analysis(difficulty=Difficulty.EASY, estimated_hours=2.0, price_min=10.0, price_max=10.0))
        assert result.classification.value == "rejected"

    def test_50_dollar_quick_job_remains_eligible(self):
        result = self._score(analysis=_analysis(difficulty=Difficulty.EASY, estimated_hours=4.0, price_min=50.0, price_max=50.0))
        assert result.classification.value in {"candidate", "strong"}
