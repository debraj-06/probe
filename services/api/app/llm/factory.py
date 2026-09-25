"""LLM client factory."""

from __future__ import annotations

from .base import LLMClient
from .clients import AnthropicClient, GeminiClient, OpenAICompatibleClient

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "gemini": "gemini-1.5-flash",
    "openai-compatible": "local-model",
}


def create_llm(
    *,
    provider: str,
    model: str = "",
    api_key: str = "",
    base_url: str = "",
    timeout: float = 60.0,
    retries: int = 2,
    max_tokens: int = 2048,
) -> LLMClient | None:
    """Build an LLM client, or ``None`` when running in heuristic mode."""
    if provider in {"", "none"}:
        return None

    if provider == "openai":
        return OpenAICompatibleClient(
            model=model or DEFAULT_MODELS["openai"],
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            timeout=timeout,
            retries=retries,
            max_tokens=max_tokens,
        )

    if provider == "openai-compatible":
        if not base_url:
            raise ValueError("PROBE_LLM_BASE_URL is required for the openai-compatible provider")
        return OpenAICompatibleClient(
            model=model or DEFAULT_MODELS["openai-compatible"],
            api_key=api_key or "not-needed",
            base_url=base_url,
            timeout=timeout,
            retries=retries,
            max_tokens=max_tokens,
        )

    if provider == "anthropic":
        if not api_key:
            raise ValueError("PROBE_LLM_API_KEY is required for the anthropic provider")
        return AnthropicClient(
            model=model or DEFAULT_MODELS["anthropic"],
            api_key=api_key,
            base_url=base_url or "https://api.anthropic.com/v1",
            timeout=timeout,
            retries=retries,
            max_tokens=max_tokens,
        )

    if provider == "gemini":
        if not api_key:
            raise ValueError("PROBE_LLM_API_KEY is required for the gemini provider")
        return GeminiClient(
            model=model or DEFAULT_MODELS["gemini"],
            api_key=api_key,
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
            timeout=timeout,
            retries=retries,
            max_tokens=max_tokens,
        )

    raise ValueError(f"Unknown LLM provider: {provider!r}")
