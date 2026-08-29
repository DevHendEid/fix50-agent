"""AI provider interface.

The whole application only talks to this abstraction, so the LLM behind it
can be swapped later (OpenAI, Anthropic, local models, ...) without touching
the analyzer, scorer or API code. V1 ships a deterministic mock provider so
the app runs with zero budget and zero API keys; Day 2 adds an
OpenAI-compatible provider selected via environment variables.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.config import Settings
from app.models import Analysis, Difficulty, OpportunityInput
from app.services.exceptions import ConfigurationError


class AIProvider(ABC):
    """Interface for turning a raw opportunity into a structured analysis."""

    @abstractmethod
    def analyze(self, opportunity: OpportunityInput) -> Analysis:
        """Analyze an opportunity and return a structured Analysis."""


def build_provider(name: str, settings: Settings | None = None) -> AIProvider:
    """Factory: create the provider configured via settings/env.

    Raises ConfigurationError (a controlled, clearly-worded error) when the
    chosen provider is missing required configuration, e.g. an API key.
    """
    name = name.lower()
    if name == "mock":
        return MockAIProvider()
    if name == "openai":
        settings = settings or Settings.from_env()
        if not settings.openai_api_key:
            raise ConfigurationError(
                "AI_PROVIDER is set to 'openai' but OPENAI_API_KEY is not set. "
                "Set it in your .env file or environment."
            )
        # Imported lazily to keep the mock-only path free of HTTP client wiring.
        from app.services.openai_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    raise ValueError(
        f"Unknown AI provider '{name}'. Available: mock, openai"
    )


class MockAIProvider(AIProvider):
    """Deterministic, rule-based provider.

    Produces a sensible analysis from keywords and text statistics so the
    whole pipeline (analysis -> scoring -> proposal -> persistence) can be
    exercised and tested without any paid API access.
    """

    _SKILL_KEYWORDS: dict[str, list[str]] = {
        "python": ["python", "django", "flask", "fastapi", "pandas", "script"],
        "javascript": ["javascript", "typescript", "node", "react", "vue"],
        "web_scraping": ["scrape", "scraping", "crawler", "parser", "harvest"],
        "api_development": ["api", "endpoint", "rest", "webhook", "integration"],
        "database": ["database", "sql", "sqlite", "postgres", "mysql"],
        "automation": ["automate", "automation", "bot", "workflow", "zapier"],
        "wordpress": ["wordpress", "woocommerce"],
        "shopify": ["shopify", "ecommerce", "e-commerce", "checkout"],
        "seo": ["seo", "ranking", "keywords", "backlinks"],
        "data_entry": ["data entry", "excel", "spreadsheet", "csv"],
        "design": ["design", "figma", "logo", "ui", "ux"],
        "frontend": ["html", "css", "landing page", "website", "responsive"],
    }

    _TIME_LABELS = {
        Difficulty.EASY: "4 hours",
        Difficulty.MEDIUM: "1-2 days",
        Difficulty.HARD: "3-5 days",
        Difficulty.UNKNOWN: "unknown",
    }

    _HOURS = {
        Difficulty.EASY: 4.0,
        Difficulty.MEDIUM: 8.0,
        Difficulty.HARD: 24.0,
        Difficulty.UNKNOWN: None,
    }

    _PRICE_RANGES = {
        Difficulty.EASY: (50.0, 120.0),
        Difficulty.MEDIUM: (100.0, 300.0),
        Difficulty.HARD: (250.0, 700.0),
        Difficulty.UNKNOWN: (50.0, 150.0),
    }

    def analyze(self, opportunity: OpportunityInput) -> Analysis:
        text = " ".join(
            part
            for part in (opportunity.title, opportunity.description or "")
            if part
        ).lower()

        skills = self._detect_skills(text)
        difficulty = self._estimate_difficulty(opportunity, skills)
        return Analysis(
            problem=self._extract_problem(opportunity),
            required_skills=skills,
            difficulty=difficulty,
            estimated_time=self._TIME_LABELS[difficulty],
            estimated_hours=self._HOURS[difficulty],
            price_min=self._PRICE_RANGES[difficulty][0],
            price_max=self._PRICE_RANGES[difficulty][1],
            confidence=self._estimate_confidence(opportunity),
        )

    def _detect_skills(self, text: str) -> list[str]:
        detected = [
            skill
            for skill, keywords in self._SKILL_KEYWORDS.items()
            if any(
                re.search(rf"\b{re.escape(keyword)}\b", text) is not None
                for keyword in keywords
            )
        ]
        return detected or ["general_programming"]

    def _estimate_difficulty(
        self, opportunity: OpportunityInput, skills: list[str]
    ) -> Difficulty:
        word_count = len((opportunity.description or "").split())
        if word_count > 150 or len(skills) >= 4:
            return Difficulty.HARD
        if word_count < 40 and len(skills) <= 1:
            return Difficulty.EASY
        return Difficulty.MEDIUM

    def _extract_problem(self, opportunity: OpportunityInput) -> str:
        description = (opportunity.description or "").strip()
        if description:
            # First sentence(s) are the best available signal of the problem.
            match = re.match(r"^(.+?[.!?])(\s|$)", description, flags=re.DOTALL)
            return (match.group(1) if match else description).strip()
        return f"Client needs help with: {opportunity.title.strip()}"

    def _estimate_confidence(self, opportunity: OpportunityInput) -> float:
        confidence = 0.4
        if opportunity.description and len(opportunity.description) >= 50:
            confidence += 0.15
        if opportunity.url:
            confidence += 0.15
        if opportunity.client_name:
            confidence += 0.15
        if opportunity.source:
            confidence += 0.10
        return min(confidence, 0.95)
