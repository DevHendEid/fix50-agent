"""Pydantic request/response models for the Fix50 Agent API."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models import Classification, Difficulty, Status


class OpportunityCreate(BaseModel):
    """POST /opportunities/analyze request body."""

    title: str = Field(..., min_length=3, description="Short title of the opportunity")
    source: str | None = Field(None, description="Where it came from, e.g. upwork")
    description: str | None = Field(None, description="Full text of the post/job")
    url: str | None = Field(None, description="Link to the original post")
    client_name: str | None = Field(None, description="Client or company name")
    market: str | None = Field(None, description="Market/language, e.g. 'US / English'")


class AnalysisOut(BaseModel):
    problem: str
    required_skills: list[str]
    difficulty: Difficulty
    estimated_time: str
    estimated_hours: float | None
    price_min: float
    price_max: float
    confidence: float
    business_value_explanation: str | None = None
    missing_information: list[str] | None = None


class ScoreBreakdownOut(BaseModel):
    problem_clarity: int = Field(..., le=25)
    business_value: int = Field(..., le=25)
    speed: int = Field(..., le=20)
    explainability: int = Field(..., le=10)
    contactability: int = Field(..., le=10)
    credibility: int = Field(..., le=10)


class ScoreOut(BaseModel):
    total: int
    breakdown: ScoreBreakdownOut
    classification: Classification


class ProposalOut(BaseModel):
    problem_summary: str
    proposed_solution: str
    delivery_estimate: str
    suggested_price: float
    message: str


class OpportunityOut(BaseModel):
    """GET /opportunities and GET /opportunities/{id} response body."""

    id: int
    title: str
    source: str | None
    description: str | None
    url: str | None
    client_name: str | None
    market: str | None
    analysis: AnalysisOut | None
    score: ScoreOut | None
    proposal: ProposalOut | None
    status: Status
    created_at: str | None
    updated_at: str | None


class StatusUpdate(BaseModel):
    """PATCH /opportunities/{id}/status request body."""

    status: Status
