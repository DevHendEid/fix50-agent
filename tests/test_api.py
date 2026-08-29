"""Tests for the Fix50 Agent API endpoints."""
from __future__ import annotations

from tests.conftest import BAD_OPPORTUNITY, GOOD_OPPORTUNITY


class TestAnalyzeEndpoint:
    def test_analyze_good_opportunity(self, client):
        response = client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY)
        assert response.status_code == 201
        body = response.json()
        assert body["id"] > 0
        assert body["status"] == "candidate"
        assert body["score"]["total"] >= 70
        assert body["analysis"]["problem"]
        assert body["analysis"]["required_skills"]
        assert 0.0 <= body["analysis"]["confidence"] <= 1.0
        # Proposal is generated because score >= 70
        proposal = body["proposal"]
        assert proposal is not None
        assert "Acme Store" in proposal["message"]
        assert proposal["suggested_price"] >= 50

    def test_analyze_weak_opportunity_is_rejected(self, client):
        response = client.post("/opportunities/analyze", json=BAD_OPPORTUNITY)
        assert response.status_code == 201
        body = response.json()
        assert body["score"]["total"] < 70
        assert body["status"] == "rejected"
        assert body["proposal"] is None

    def test_analyze_requires_title(self, client):
        response = client.post("/opportunities/analyze", json={"source": "upwork"})
        assert response.status_code == 422

    def test_full_analysis_is_persisted(self, client):
        created = client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY).json()
        fetched = client.get(f"/opportunities/{created['id']}").json()
        assert fetched["analysis"] == created["analysis"]
        assert fetched["score"] == created["score"]
        assert fetched["proposal"] == created["proposal"]


class TestReadEndpoints:
    def test_list_opportunities(self, client):
        client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY)
        client.post("/opportunities/analyze", json=BAD_OPPORTUNITY)
        response = client.get("/opportunities")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2
        # newest first
        assert items[0]["title"] == BAD_OPPORTUNITY["title"]

    def test_list_filter_by_status(self, client):
        client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY)
        client.post("/opportunities/analyze", json=BAD_OPPORTUNITY)
        rejected = client.get("/opportunities", params={"status": "rejected"}).json()
        assert len(rejected) == 1
        assert rejected[0]["score"]["total"] < 70

    def test_get_opportunity_not_found(self, client):
        response = client.get("/opportunities/999")
        assert response.status_code == 404


class TestStatusEndpoint:
    def test_update_status(self, client):
        created = client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY).json()
        response = client.patch(
            f"/opportunities/{created['id']}/status", json={"status": "contacted"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "contacted"

    def test_full_pipeline_lifecycle(self, client):
        created = client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY).json()
        opportunity_id = created["id"]
        for next_status in ("approved", "contacted", "replied", "paid"):
            updated = client.patch(
                f"/opportunities/{opportunity_id}/status", json={"status": next_status}
            ).json()
            assert updated["status"] == next_status

    def test_update_status_invalid_value(self, client):
        created = client.post("/opportunities/analyze", json=GOOD_OPPORTUNITY).json()
        response = client.patch(
            f"/opportunities/{created['id']}/status", json={"status": "won_the_lottery"}
        )
        assert response.status_code == 422

    def test_update_status_not_found(self, client):
        response = client.patch("/opportunities/999/status", json={"status": "paid"})
        assert response.status_code == 404


class TestMeta:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "ai_provider": "mock"}
