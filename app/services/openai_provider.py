"""OpenAI-compatible LLM provider."""
from __future__ import annotations

import json
import re

import httpx
from pydantic import ValidationError

from app.models import Analysis, Difficulty, OpportunityInput
from app.schemas import LLMAnalysis
from app.services.ai_provider import AIProvider
from app.services.exceptions import ConfigurationError, LLMResponseError

_SYSTEM_PROMPT = (
    "You are a freelance opportunity analyst for Fix50 Agent, a tool that "
    "helps find small freelance jobs worth at least $50.\n"
    "Analyze the given opportunity and respond ONLY with a JSON object with "
    "exactly these keys:\n"
    "{\n"
    '  "problem": string,\n'
    '  "required_skills": string[],\n'
    '  "difficulty": "easy" | "medium" | "hard",\n'
    '  "estimated_execution_time": string,\n'
    '  "estimated_price_min": number,\n'
    '  "estimated_price_max": number,\n'
    '  "confidence": number,\n'
    '  "business_value_explanation": string,\n'
    '  "missing_information": string[]\n'
    "}\n"
    "Do NOT return any score, ranking or classification — the application "
    "scores opportunities deterministically on its own."
)


def _strip_code_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _parse_estimated_hours(label: str) -> float | None:
    """Convert common LLM duration labels to an approximate hour count.

    For ranges we use the upper bound so the scorer stays conservative.
    Unknown/free-form labels remain None instead of guessing.
    """
    text = label.strip().lower()
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]
    if not numbers:
        return None
    amount = max(numbers)
    if "minute" in text or "min" in text:
        return amount / 60.0
    if "hour" in text or re.search(r"\bhrs?\b", text):
        return amount
    if "day" in text:
        return amount * 8.0
    if "week" in text:
        return amount * 40.0
    return None


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini", timeout_seconds: float = 30.0, client: httpx.Client | None = None) -> None:
        if not api_key:
            raise ConfigurationError("OpenAI-compatible provider requires an API key (set OPENAI_API_KEY).")
        self._model = model
        self._api_key = api_key
        self._client = client or httpx.Client(base_url=base_url, timeout=timeout_seconds, headers={"Content-Type": "application/json"})

    def analyze(self, opportunity: OpportunityInput) -> Analysis:
        return self._to_analysis(self._validate(self._call_llm(opportunity)))

    def _post_chat(self, payload: dict) -> httpx.Response:
        return self._client.post("/chat/completions", json=payload, headers={"Authorization": f"Bearer {self._api_key}"})

    def _call_llm(self, opportunity: OpportunityInput) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"source": opportunity.source, "title": opportunity.title, "description": opportunity.description, "url": opportunity.url, "client_name": opportunity.client_name, "market": opportunity.market})},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._post_chat(payload)
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"Could not reach the LLM API: {exc}") from exc
        if response.status_code != 200:
            raise LLMResponseError(f"LLM API returned HTTP {response.status_code}: {response.text[:300]}")
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(f"LLM API response has unexpected structure: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMResponseError("LLM returned empty content (HTTP 200)")
        try:
            return json.loads(_strip_code_fences(content))
        except ValueError as exc:
            raise LLMResponseError(f"LLM returned malformed JSON: {exc}") from exc

    @staticmethod
    def _validate(raw: dict) -> LLMAnalysis:
        if not isinstance(raw, dict):
            raise LLMResponseError("LLM output is not a JSON object")
        try:
            return LLMAnalysis.model_validate(raw)
        except ValidationError as exc:
            raise LLMResponseError(f"LLM returned invalid or missing data: {exc.error_count()} validation error(s), first: {exc.errors()[0]['msg']}") from exc

    @staticmethod
    def _to_analysis(validated: LLMAnalysis) -> Analysis:
        return Analysis(
            problem=validated.problem,
            required_skills=validated.required_skills,
            difficulty=Difficulty(validated.difficulty),
            estimated_time=validated.estimated_execution_time,
            estimated_hours=_parse_estimated_hours(validated.estimated_execution_time),
            price_min=validated.estimated_price_min,
            price_max=validated.estimated_price_max,
            confidence=validated.confidence,
            business_value_explanation=validated.business_value_explanation,
            missing_information=validated.missing_information,
        )
