"""Controlled errors raised by AI providers.

These let the API and CLI fail safely with clear messages instead of
crashing on bad model output or missing configuration.
"""
from __future__ import annotations


class AIProviderError(Exception):
    """Base class for all AI provider errors."""


class ConfigurationError(AIProviderError):
    """Provider is misconfigured (e.g. missing API key)."""


class LLMResponseError(AIProviderError):
    """The LLM API failed or returned invalid/unusable output."""
