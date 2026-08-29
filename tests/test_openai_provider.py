"""Tests for the OpenAI-compatible provider using mocked API calls."""
from __future__ import annotations

import json
import httpx
import pytest

from app.models import Difficulty, OpportunityInput
from app.schemas import LLMAnalysis
from app.services.ai_provider import build_provider
from app.services.exceptions import ConfigurationError, LLMResponseError
from app.services.openai_provider import OpenAICompatibleProvider, _parse_estimated_hours
from app.services.scorer import OpportunityScorer
from tests.conftest import GOOD_OPPORTUNITY

VALID_LLM_JSON = {
    "problem": "The Shopify checkout fails and the client loses orders daily.",
    "required_skills": ["shopify", "javascript", "debugging"],
    "difficulty": "medium",
    "estimated_execution_time": "1-2 days",
    "estimated_price_min": 120.0,
    "estimated_price_max": 250.0,
    "confidence": 0.85,
    "business_value_explanation": "Every broken checkout day costs roughly 30% of daily revenue.",
    "missing_information": ["Shopify plan tier", "error message samples"],
}


def _opportunity(): return OpportunityInput(**GOOD_OPPORTUNITY)
def _chat_response(content): return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})
def _make_provider(handler):
    return OpenAICompatibleProvider(api_key="test-key", client=httpx.Client(base_url="https://api.test/v1", transport=httpx.MockTransport(handler)))
def _valid_provider(): return _make_provider(lambda request: _chat_response(json.dumps(VALID_LLM_JSON)))


class TestValidStructuredResponse:
    def test_maps_valid_response_to_analysis(self):
        analysis = _valid_provider().analyze(_opportunity())
        assert analysis.problem == VALID_LLM_JSON["problem"]
        assert analysis.required_skills == VALID_LLM_JSON["required_skills"]
        assert analysis.difficulty is Difficulty.MEDIUM
        assert analysis.estimated_time == "1-2 days"
        assert analysis.estimated_hours == 16.0
        assert analysis.price_min == 120.0
        assert analysis.price_max == 250.0
        assert analysis.confidence == 0.85

    @pytest.mark.parametrize("label,hours", [("2 hours",2.0),("2-4 hours",4.0),("1 day",8.0),("1-2 days",16.0),("1 week",40.0),("30 minutes",0.5)])
    def test_parses_execution_time(self, label, hours):
        assert _parse_estimated_hours(label) == hours

    def test_accepts_markdown_fenced_json(self):
        provider = _make_provider(lambda request: _chat_response("```json\n" + json.dumps(VALID_LLM_JSON) + "\n```"))
        assert provider.analyze(_opportunity()).confidence == 0.85

    def test_valid_response_feeds_scoring_pipeline(self):
        score = OpportunityScorer().score(_opportunity(), _valid_provider().analyze(_opportunity()))
        assert 0 <= score.total <= 100

    def test_llm_schema_ignores_score_in_output(self):
        validated = LLMAnalysis.model_validate({**VALID_LLM_JSON, "score": 99, "classification": "strong"})
        assert not hasattr(validated, "score")


class TestMalformedResponses:
    def test_empty_content_fails_clearly(self):
        provider = _make_provider(lambda request: _chat_response("   "))
        with pytest.raises(LLMResponseError, match="empty content"):
            provider.analyze(_opportunity())

    def test_malformed_json_fails_safely(self):
        provider = _make_provider(lambda request: _chat_response("{not json"))
        with pytest.raises(LLMResponseError, match="malformed JSON"):
            provider.analyze(_opportunity())

    def test_missing_field_fails_safely(self):
        payload = {k: v for k, v in VALID_LLM_JSON.items() if k != "confidence"}
        with pytest.raises(LLMResponseError, match="invalid or missing data"):
            _make_provider(lambda request: _chat_response(json.dumps(payload))).analyze(_opportunity())

    def test_invalid_difficulty_fails_safely(self):
        with pytest.raises(LLMResponseError):
            _make_provider(lambda request: _chat_response(json.dumps({**VALID_LLM_JSON, "difficulty": "impossible"}))).analyze(_opportunity())

    def test_price_min_above_max_fails_safely(self):
        with pytest.raises(LLMResponseError, match="estimated_price_min"):
            _make_provider(lambda request: _chat_response(json.dumps({**VALID_LLM_JSON, "estimated_price_min": 500.0}))).analyze(_opportunity())

    def test_out_of_range_confidence_fails_safely(self):
        with pytest.raises(LLMResponseError):
            _make_provider(lambda request: _chat_response(json.dumps({**VALID_LLM_JSON, "confidence": 1.5}))).analyze(_opportunity())

    def test_non_object_output_fails_safely(self):
        with pytest.raises(LLMResponseError, match="not a JSON object"):
            _make_provider(lambda request: _chat_response('["a", "list"]')).analyze(_opportunity())

    def test_http_error_fails_safely(self):
        with pytest.raises(LLMResponseError, match="HTTP 500"):
            _make_provider(lambda request: httpx.Response(500, text="server exploded")).analyze(_opportunity())

    def test_unexpected_api_shape_fails_safely(self):
        with pytest.raises(LLMResponseError, match="unexpected structure"):
            _make_provider(lambda request: httpx.Response(200, json={})).analyze(_opportunity())


class TestConfiguration:
    def test_missing_api_key_fails_at_build(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False); monkeypatch.setenv("AI_PROVIDER", "openai")
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"): build_provider("openai")

    def test_missing_api_key_fails_at_construction(self):
        with pytest.raises(ConfigurationError): OpenAICompatibleProvider(api_key="")

    def test_build_openai_provider_with_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        assert isinstance(build_provider("openai"), OpenAICompatibleProvider)

    def test_unknown_provider_still_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown AI provider"): build_provider("gpt-9000")

    def test_api_key_not_leaked_in_request_body(self):
        captured = {}
        def handler(request):
            captured["headers"] = dict(request.headers); captured["body"] = request.content.decode()
            return _chat_response(json.dumps(VALID_LLM_JSON))
        _make_provider(handler).analyze(_opportunity())
        assert captured["headers"].get("authorization") == "Bearer test-key"
        assert "test-key" not in captured["body"]
