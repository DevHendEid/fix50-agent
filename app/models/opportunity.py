"""Core domain entities for the Fix50 Agent."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"


class Classification(str, Enum):
    REJECTED = "rejected"       # score < 70
    CANDIDATE = "candidate"     # 70 <= score < 85
    STRONG = "strong"           # score >= 85


class Status(str, Enum):
    NEW = "new"
    REJECTED = "rejected"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    CONTACTED = "contacted"
    REPLIED = "replied"
    PAID = "paid"


@dataclass(frozen=True)
class Analysis:
    """Structured analysis of an opportunity, produced by an AIProvider.

    The last two fields are optional richer outputs (Day 2): the mock provider
    leaves them as None, real LLM providers fill them in.
    """

    problem: str
    required_skills: list[str]
    difficulty: Difficulty
    estimated_time: str          # human label, e.g. "4 hours", "1-2 days"
    estimated_hours: float | None
    price_min: float
    price_max: float
    confidence: float            # 0.0 - 1.0
    business_value_explanation: str | None = None
    missing_information: list[str] | None = None


@dataclass(frozen=True)
class ScoreBreakdown:
    """Per-criterion scores following the V1 rubric (total = 100)."""

    problem_clarity: int    # /25 - is the problem clear?
    business_value: int     # /25 - does solving it provide real business value?
    speed: int              # /20 - can it be completed quickly?
    explainability: int     # /10 - is the solution easy to explain?
    contactability: int     # /10 - can the client be contacted?
    credibility: int        # /10 - is the opportunity/client credible?


@dataclass(frozen=True)
class ScoreResult:
    total: int
    breakdown: ScoreBreakdown
    classification: Classification


@dataclass(frozen=True)
class Proposal:
    """Short personalized proposal, generated when score >= 70."""

    problem_summary: str
    proposed_solution: str
    delivery_estimate: str
    suggested_price: float
    message: str


@dataclass
class OpportunityInput:
    """Raw opportunity as received from the outside world."""

    title: str
    source: str | None = None
    description: str | None = None
    url: str | None = None
    client_name: str | None = None
    market: str | None = None


@dataclass
class Opportunity:
    """A stored opportunity: original input + analysis + score + proposal."""

    id: int | None
    input: OpportunityInput
    status: Status = Status.NEW
    analysis: Analysis | None = None
    score: ScoreResult | None = None
    proposal: Proposal | None = None
    created_at: str | None = None
    updated_at: str | None = None
