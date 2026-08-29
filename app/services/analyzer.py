"""OpportunityAnalyzer: the pipeline entry point for analysis.

Wraps the AIProvider behind a stable interface, so swapping the LLM in V2
only means registering a new provider in ai_provider.build_provider().
"""
from __future__ import annotations

from app.models import Analysis, OpportunityInput
from app.services.ai_provider import AIProvider


class OpportunityAnalyzer:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def analyze(self, opportunity: OpportunityInput) -> Analysis:
        return self._provider.analyze(opportunity)
