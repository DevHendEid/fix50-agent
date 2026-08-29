"""API routes for the Fix50 Agent (V1).

Note: this API only *prepares* work. It never sends messages or processes
payments — contacting clients is a manual step outside the app.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_analyzer,
    get_proposal_generator,
    get_repository,
    get_scorer,
)
from app.models import (
    Opportunity,
    OpportunityInput,
    Status,
)
from app.schemas import (
    AnalysisOut,
    OpportunityCreate,
    OpportunityOut,
    ProposalOut,
    ScoreBreakdownOut,
    ScoreOut,
    StatusUpdate,
)
from app.db.repository import OpportunityRepository
from app.services.analyzer import OpportunityAnalyzer
from app.services.exceptions import ConfigurationError, LLMResponseError
from app.services.pipeline import analyze_and_store
from app.services.proposal_generator import ProposalGenerator
from app.services.scorer import OpportunityScorer

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _to_out(opportunity: Opportunity) -> OpportunityOut:
    analysis = None
    if opportunity.analysis is not None:
        analysis = AnalysisOut(**opportunity.analysis.__dict__)
    score = None
    if opportunity.score is not None:
        score = ScoreOut(
            total=opportunity.score.total,
            breakdown=ScoreBreakdownOut(**opportunity.score.breakdown.__dict__),
            classification=opportunity.score.classification,
        )
    proposal = (
        ProposalOut(**opportunity.proposal.__dict__)
        if opportunity.proposal is not None
        else None
    )
    return OpportunityOut(
        id=opportunity.id,  # type: ignore[arg-type]
        title=opportunity.input.title,
        source=opportunity.input.source,
        description=opportunity.input.description,
        url=opportunity.input.url,
        client_name=opportunity.input.client_name,
        market=opportunity.input.market,
        analysis=analysis,
        score=score,
        proposal=proposal,
        status=opportunity.status,
        created_at=opportunity.created_at,
        updated_at=opportunity.updated_at,
    )


@router.post(
    "/analyze",
    response_model=OpportunityOut,
    status_code=status.HTTP_201_CREATED,
)
def analyze_opportunity(
    payload: OpportunityCreate,
    analyzer: OpportunityAnalyzer = Depends(get_analyzer),
    scorer: OpportunityScorer = Depends(get_scorer),
    proposal_generator: ProposalGenerator = Depends(get_proposal_generator),
    repository: OpportunityRepository = Depends(get_repository),
) -> OpportunityOut:
    """Analyze, score, (maybe) draft a proposal, and store an opportunity."""
    opportunity_input = OpportunityInput(
        title=payload.title,
        source=payload.source,
        description=payload.description,
        url=payload.url,
        client_name=payload.client_name,
        market=payload.market,
    )

    try:
        opportunity = analyze_and_store(
            analyzer, scorer, proposal_generator, repository, opportunity_input
        )
    except ConfigurationError as exc:
        # Provider misconfigured (e.g. missing API key) -> fail safely.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except LLMResponseError as exc:
        # LLM unreachable or returned invalid/missing data -> fail safely.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM analysis failed: {exc}",
        )
    return _to_out(opportunity)


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(
    status_filter: Status | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    repository: OpportunityRepository = Depends(get_repository),
) -> list[OpportunityOut]:
    """List stored opportunities, newest first, optionally filtered by status."""
    return [
        _to_out(opportunity)
        for opportunity in repository.list(status=status_filter, limit=limit)
    ]


@router.get("/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(
    opportunity_id: int,
    repository: OpportunityRepository = Depends(get_repository),
) -> OpportunityOut:
    opportunity = repository.get(opportunity_id)
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity {opportunity_id} not found",
        )
    return _to_out(opportunity)


@router.patch("/{opportunity_id}/status", response_model=OpportunityOut)
def update_opportunity_status(
    opportunity_id: int,
    payload: StatusUpdate,
    repository: OpportunityRepository = Depends(get_repository),
) -> OpportunityOut:
    """Move an opportunity through the pipeline (manual, human-driven)."""
    opportunity = repository.update_status(opportunity_id, payload.status)
    if opportunity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity {opportunity_id} not found",
        )
    return _to_out(opportunity)
