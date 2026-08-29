"""Application configuration, loaded from environment variables.

Kept intentionally simple (no pydantic-settings dependency in V1).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ai_provider: str = "mock"
    database_path: str = "data/fix50.db"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    # OpenAI-compatible provider settings (any compatible endpoint works,
    # e.g. OpenAI, OpenRouter, Groq, a local vLLM server).
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            ai_provider=os.getenv("AI_PROVIDER", "mock"),
            database_path=os.getenv("DATABASE_PATH", "data/fix50.db"),
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "info"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_timeout_seconds=float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30")),
        )
