"""FastAPI dependencies pulling services from app.state."""
from __future__ import annotations

from fastapi import Request

from app.db.repository import OpportunityRepository
from app.services.analyzer import OpportunityAnalyzer
from app.services.proposal_generator import ProposalGenerator
from app.services.scorer import OpportunityScorer


def get_analyzer(request: Request) -> OpportunityAnalyzer:
    return request.app.state.analyzer


def get_scorer(request: Request) -> OpportunityScorer:
    return request.app.state.scorer


def get_proposal_generator(request: Request) -> ProposalGenerator:
    return request.app.state.proposal_generator


def get_repository(request: Request) -> OpportunityRepository:
    return request.app.state.repository
