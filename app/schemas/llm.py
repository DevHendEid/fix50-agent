"""Validation contract for structured LLM output.

Every field returned by a real LLM provider must pass this model before it
enters the scoring pipeline. Invalid or missing data raises ValidationError,
which the provider converts into a controlled LLMResponseError.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class LLMAnalysis(BaseModel):
    """Strict schema for the JSON an LLM must return. No score here — scoring
    is deterministic and happens in app/services/scorer.py, never in the LLM."""

    model_config = {"extra": "ignore"}

    problem: str = Field(..., min_length=1)
    required_skills: list[str] = Field(..., min_length=1)
    difficulty: Literal["easy", "medium", "hard"]
    estimated_execution_time: str = Field(..., min_length=1)
    estimated_price_min: float = Field(..., gt=0)
    estimated_price_max: float = Field(..., gt=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    business_value_explanation: str = Field(..., min_length=1)
    missing_information: list[str] = Field(default_factory=list)

    @field_validator("required_skills", "missing_information", mode="before")
    @classmethod
    def _coerce_list(cls, value: object) -> object:
        """Tolerate a common LLM quirk: skills given as a single comma string."""
        if isinstance(value, str):
            return [part.strip() for part in value.split(",")]
        return value

    @field_validator("required_skills", "missing_information")
    @classmethod
    def _clean_strings(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @field_validator("required_skills")
    @classmethod
    def _skills_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("required_skills must contain at least one skill")
        return value

    @model_validator(mode="after")
    def _price_range_valid(self) -> "LLMAnalysis":
        if self.estimated_price_min > self.estimated_price_max:
            raise ValueError("estimated_price_min must be <= estimated_price_max")
        return self
