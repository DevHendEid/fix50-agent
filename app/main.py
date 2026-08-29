"""Fix50 Agent - FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router as opportunities_router
from app.config import Settings
from app.db.repository import OpportunityRepository
from app.services.ai_provider import build_provider
from app.services.analyzer import OpportunityAnalyzer
from app.services.proposal_generator import ProposalGenerator
from app.services.scorer import OpportunityScorer


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    app = FastAPI(
        title="Fix50 Agent",
        description=(
            "AI agent for finding, scoring, and preparing small freelance "
            "opportunities in a 14-day $50 revenue experiment."
        ),
        version="1.0.0",
    )

    # Wiring: provider -> analyzer -> scorer -> proposal generator -> repository
    provider = build_provider(settings.ai_provider, settings)
    app.state.settings = settings
    app.state.provider = provider
    app.state.analyzer = OpportunityAnalyzer(provider)
    app.state.scorer = OpportunityScorer()
    app.state.proposal_generator = ProposalGenerator()
    app.state.repository = OpportunityRepository(settings.database_path)

    app.include_router(opportunities_router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "ai_provider": settings.ai_provider}

    return app


app = create_app()
