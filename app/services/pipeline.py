"""Shared analyze -> score -> proposal -> store pipeline.

Used by both the HTTP API and the CLI so there is exactly one place where
an opportunity flows through the V1/V2 workflow. Scoring stays deterministic
here — the LLM never decides the final score.
"""
from __future__ import annotations

from app.models import (
    Classification,
    Opportunity,
    OpportunityInput,
    Status,
)
from app.db.repository import OpportunityRepository
from app.services.analyzer import OpportunityAnalyzer
from app.services.proposal_generator import ProposalGenerator
from app.services.scorer import OpportunityScorer

_PROPOSAL_MIN_SCORE = 70  # generate a proposal for candidates and strong fits


def analyze_and_store(
    analyzer: OpportunityAnalyzer,
    scorer: OpportunityScorer,
    proposal_generator: ProposalGenerator,
    repository: OpportunityRepository,
    opportunity_input: OpportunityInput,
) -> Opportunity:
    """Run the full pipeline and persist the result.

    May raise AIProviderError subclasses (ConfigurationError,
    LLMResponseError) from the provider — callers convert them into
    controlled API/CLI errors.
    """
    analysis = analyzer.analyze(opportunity_input)
    score_result = scorer.score(opportunity_input, analysis)

    proposal = None
    if score_result.total >= _PROPOSAL_MIN_SCORE:
        proposal = proposal_generator.generate(
            opportunity_input, analysis, score_result
        )

    stored_status = (
        Status.REJECTED
        if score_result.classification is Classification.REJECTED
        else Status.CANDIDATE
    )

    opportunity = Opportunity(
        id=None,
        input=opportunity_input,
        status=stored_status,
        analysis=analysis,
        score=score_result,
        proposal=proposal,
    )
    return repository.create(opportunity)
