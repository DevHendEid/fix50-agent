"""Tests for the mock AI provider and the analyzer service."""
from __future__ import annotations

import pytest

from app.models import (
    Analysis,
    Difficulty,
    Opportunity,
    OpportunityInput,
    Status,
)

from app.services.ai_provider import MockAIProvider, build_provider
from tests.conftest import GOOD_OPPORTUNITY


class TestProviderFactory:
    def test_build_mock_provider(self):
        assert isinstance(build_provider("mock"), MockAIProvider)

    def test_build_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            build_provider("gpt-9000")


class TestMockProvider:
    def setup_method(self) -> None:
        self.provider = MockAIProvider()

    def _analyze(self, **overrides) -> object:
        payload = {**GOOD_OPPORTUNITY, **overrides}
        return self.provider.analyze(OpportunityInput(**payload))

    def test_extracts_problem_from_description(self):
        analysis = self._analyze()
        assert "checkout" in analysis.problem.lower()

    def test_detects_skills(self):
        analysis = self._analyze()
        assert "shopify" in analysis.required_skills

    def test_confidence_reflects_available_context(self):
        rich = self._analyze()
        poor = self._analyze(
            source=None, url=None, client_name=None, description=None
        )
        assert rich.confidence > poor.confidence
        assert poor.confidence >= 0.0 and rich.confidence <= 0.95

    def test_difficulty_scales_with_scope(self):
        easy = self._analyze(
            title="Small CSS fix",
            description="Fix one button color on our site.",
        )
        hard = self._analyze(
            description=(
                "We need a full integration between our ERP and the storefront, "
                "including order sync, inventory sync, customer sync, and "
                "webhook handling for payments, refunds, and cancellations. "
                + "There are many edge cases to handle carefully. " * 20
            )
        )
        assert easy.difficulty is Difficulty.EASY
        assert hard.difficulty is Difficulty.HARD

    def test_price_range_is_positive(self):
        analysis = self._analyze()
        assert 0 < analysis.price_min <= analysis.price_max

    def test_backward_compatible_analysis_shape(self):
        """The mock provider still returns the V1 Analysis shape (Day-2
        fields optional and None), so nothing downstream breaks."""
        analysis = self._analyze()
        assert analysis.business_value_explanation is None
        assert analysis.missing_information is None
        assert analysis.problem
        assert analysis.required_skills
        assert analysis.difficulty in (
            Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD
        )

    def test_mock_output_round_trips_through_database(self, tmp_path):
        """Mock analysis -> repository -> domain keeps all V1 fields."""
        from app.db.repository import OpportunityRepository

        repository = OpportunityRepository(str(tmp_path / "mock.db"))
        analysis = self._analyze()
        created = repository.create(
            Opportunity(
                id=None,
                input=OpportunityInput(**GOOD_OPPORTUNITY),
                status=Status.CANDIDATE,
                analysis=analysis,
            )
        )
        fetched = repository.get(created.id)
        assert fetched.analysis.problem == analysis.problem
        assert fetched.analysis.required_skills == analysis.required_skills
        assert fetched.analysis.difficulty is analysis.difficulty
        assert fetched.analysis.business_value_explanation is None
        assert fetched.analysis.missing_information is None
