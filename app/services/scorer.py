"""Deterministic Fix50 opportunity scoring.

The six original rubric dimensions remain unchanged (100 points total).
Day 4 calibration makes them language-agnostic where possible and adds a
minimum-economics guardrail: work priced entirely below $50 cannot be a
candidate, because it cannot achieve the experiment's minimum paid outcome.
"""
from __future__ import annotations

import re

from app.models import Analysis, Classification, Difficulty, OpportunityInput, ScoreBreakdown, ScoreResult

_MAX_SCORES = {
    "problem_clarity": 25,
    "business_value": 25,
    "speed": 20,
    "explainability": 10,
    "contactability": 10,
    "credibility": 10,
}

_VALUE_KEYWORDS = (
    "revenue", "sales", "customer", "client", "orders", "conversion", "leads",
    "growth", "profit", "invoice", "payment", "checkout", "automate", "automation",
    "cost", "efficiency", "seo", "traffic", "retention", "churn", "signups",
    "subscribers", "مبيعات", "عملاء", "عميل", "طلبات", "دفع", "شراء", "متجر",
    "ارباح", "أرباح", "ايرادات", "إيرادات", "تحويل", "أتمتة", "اتمتة", "توفير",
)


def classify(total: int) -> Classification:
    if total < 70:
        return Classification.REJECTED
    if total < 85:
        return Classification.CANDIDATE
    return Classification.STRONG


class OpportunityScorer:
    def score(self, opportunity: OpportunityInput, analysis: Analysis) -> ScoreResult:
        breakdown = ScoreBreakdown(
            problem_clarity=self._problem_clarity(opportunity, analysis),
            business_value=self._business_value(opportunity, analysis),
            speed=self._speed(analysis),
            explainability=self._explainability(analysis),
            contactability=self._contactability(opportunity),
            credibility=self._credibility(opportunity, analysis),
        )
        total = sum(min(getattr(breakdown, criterion), max_score) for criterion, max_score in _MAX_SCORES.items())
        classification = classify(total)

        # Fix50 is explicitly an experiment to earn at least $50 from a real
        # client. An opportunity whose entire realistic range is below $50 is
        # therefore not economically eligible, regardless of how easy it is.
        if analysis.price_max < 50:
            classification = Classification.REJECTED

        return ScoreResult(total=total, breakdown=breakdown, classification=classification)

    def _problem_clarity(self, opportunity: OpportunityInput, analysis: Analysis) -> int:
        score = 0
        if analysis.problem.strip():
            score += 12
        if len(analysis.problem.strip()) >= 40:
            score += 8
        if (opportunity.description or "").strip():
            score += 5
        return min(score, 25)

    def _business_value(self, opportunity: OpportunityInput, analysis: Analysis) -> int:
        # The provider already supplies an explicit business-value assessment.
        # Use it as evidence instead of throwing it away and relying solely on
        # English keyword coincidences in the listing.
        explanation = (analysis.business_value_explanation or "").strip()
        score = 15 if explanation else 0
        text = " ".join(filter(None, (opportunity.title, opportunity.description or "", analysis.problem, explanation))).lower()
        hits = sum(1 for keyword in _VALUE_KEYWORDS if keyword in text)
        score += min(hits * 2, 10)
        return min(score, 25)

    def _speed(self, analysis: Analysis) -> int:
        hours = analysis.estimated_hours
        if hours is None:
            return 8
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
        return {Difficulty.EASY: 10, Difficulty.MEDIUM: 7, Difficulty.HARD: 3, Difficulty.UNKNOWN: 5}[analysis.difficulty]

    def _contactability(self, opportunity: OpportunityInput) -> int:
        # A named marketplace listing is contactable through the marketplace;
        # a direct client name is additional evidence, not a requirement.
        if opportunity.url:
            return 10
        if opportunity.client_name and opportunity.source:
            return 8
        if opportunity.client_name or opportunity.source:
            return 6
        return 2

    def _credibility(self, opportunity: OpportunityInput, analysis: Analysis) -> int:
        score = 0
        if opportunity.source:
            score += 4
        if opportunity.url:
            score += 3
        if opportunity.client_name:
            score += 1
        if analysis.confidence >= 0.7:
            score += 2
        return min(score, 10)
