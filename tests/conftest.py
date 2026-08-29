"""Shared pytest fixtures."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

GOOD_OPPORTUNITY = {
    "source": "upwork",
    "title": "Fix broken checkout on Shopify store - losing orders",
    "description": (
        "Our Shopify checkout has been failing for the last week. "
        "Customers report errors when paying, and we estimate we are losing "
        "about 30% of daily orders and revenue. We need someone to find the "
        "bug and fix it quickly."
    ),
    "url": "https://example.com/job/123",
    "client_name": "Acme Store",
    "market": "US / English",
}

BAD_OPPORTUNITY = {"title": "Looking for developer"}


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        ai_provider="mock",
        database_path=str(tmp_path / "test.db"),
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
