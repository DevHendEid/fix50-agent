"""OpenAI-compatible LLM provider.

Works with any endpoint that implements the OpenAI chat-completions API
(OpenAI, OpenRouter, Groq, local vLLM/LiteLLM servers, ...). Configuration
comes exclusively from environment variables — API keys are never hardcoded.

Contract with the model:
  - Structured JSON output (response_format json_object).
  - Output is validated with the strict LLMAnalysis schema before it enters
    the scoring pipeline.
  - Invalid/missing data raises a controlled LLMResponseError.
  - The LLM NEVER produces the final score; scoring stays deterministic in
    app/services/scorer.py.
"""
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
    '  "problem": string,  // the client problem in one clear sentence\n'
    '  "required_skills": string[],  // short skill names\n'
    '  "difficulty": "easy" | "medium" | "hard",\n'
    '  "estimated_execution_time": string,  // e.g. "4 hours", "1-2 days"\n'
    '  "estimated_price_min": number,  // realistic fixed price in USD\n'
    '  "estimated_price_max": number,\n'
    '  "confidence": number,  // 0.0 to 1.0, how sure the analysis is\n'
    '  "business_value_explanation": string,  // why solving this matters\n'
    '  "missing_information": string[]  // assumptions made or missing info\n'
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


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "OpenAI-compatible provider requires an API key "
                "(set OPENAI_API_KEY)."
            )
        self._model = model
        self._api_key = api_key
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"Content-Type": "application/json"},
        )

    def analyze(self, opportunity: OpportunityInput) -> Analysis:
        raw = self._call_llm(opportunity)
        validated = self._validate(raw)
        return self._to_analysis(validated)

    # --- LLM call ---------------------------------------------------------

    def _post_chat(self, payload: dict) -> httpx.Response:
        """Auth header is attached per-request so it also works when a
        pre-built client is injected (e.g. in tests)."""
        return self._client.post(
            "/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    def _call_llm(self, opportunity: OpportunityInput) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source": opportunity.source,
                            "title": opportunity.title,
                            "description": opportunity.description,
                            "url": opportunity.url,
                            "client_name": opportunity.client_name,
                            "market": opportunity.market,
                        }
                    ),
                },
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self._post_chat(payload)
        except httpx.HTTPError as exc:
            raise LLMResponseError(f"Could not reach the LLM API: {exc}") from exc

        if response.status_code != 200:
            raise LLMResponseError(
                f"LLM API returned HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(
                f"LLM API response has unexpected structure: {exc}"
            ) from exc

        try:
            return json.loads(_strip_code_fences(content))
        except ValueError as exc:
            raise LLMResponseError(f"LLM returned malformed JSON: {exc}") from exc

    # --- validation -------------------------------------------------------

    @staticmethod
    def _validate(raw: dict) -> LLMAnalysis:
        if not isinstance(raw, dict):
            raise LLMResponseError("LLM output is not a JSON object")
        try:
            return LLMAnalysis.model_validate(raw)
        except ValidationError as exc:
            raise LLMResponseError(
                f"LLM returned invalid or missing data: "
                f"{exc.error_count()} validation error(s), first: "
                f"{exc.errors()[0]['msg']}"
            ) from exc

    @staticmethod
    def _to_analysis(validated: LLMAnalysis) -> Analysis:
        return Analysis(
            problem=validated.problem,
            required_skills=validated.required_skills,
            difficulty=Difficulty(validated.difficulty),
            estimated_time=validated.estimated_execution_time,
            estimated_hours=None,  # label only; scorer handles unknown hours
            price_min=validated.estimated_price_min,
            price_max=validated.estimated_price_max,
            confidence=validated.confidence,
            business_value_explanation=validated.business_value_explanation,
            missing_information=validated.missing_information,
        )
