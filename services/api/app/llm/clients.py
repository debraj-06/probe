"""Concrete provider clients (OpenAI, Anthropic, Gemini, OpenAI-compatible)."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from .base import (
    LLMClient,
    LLMError,
    extract_json_object,
    to_gemini_schema,
)

TOOL_NAME = "probe_action"
TOOL_DESCRIPTION = (
    "Choose the single next browser action for this autonomous testing agent, "
    "including any suspicion it wants to investigate."
)


# ---------------------------------------------------------------------------
# OpenAI (and any OpenAI-compatible endpoint)
# ---------------------------------------------------------------------------
class OpenAICompatibleClient(LLMClient):
    provider = "openai"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        retries: int = 2,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._retries = retries
        self._max_tokens = max_tokens

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.post(path, json=payload)
                if response.status_code >= 400:
                    raise LLMError(
                        f"{self.provider} HTTP {response.status_code}: {response.text[:300]}"
                    )
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self._retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise LLMError(f"{self.provider} request failed: {last_error}")

    async def decide(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": TOOL_NAME,
                        "description": TOOL_DESCRIPTION,
                        "parameters": schema,
                    },
                }
            ],
            "tool_choice": {"type": "function", "function": {"name": TOOL_NAME}},
        }
        data = await self._post("/chat/completions", payload)
        message = (data.get("choices") or [{}])[0].get("message") or {}
        for call in message.get("tool_calls") or []:
            if call.get("function", {}).get("name") == TOOL_NAME:
                arguments = call["function"].get("arguments") or "{}"
                try:
                    parsed = json.loads(arguments)
                except ValueError:
                    parsed = extract_json_object(arguments)
                if isinstance(parsed, dict):
                    return parsed
        return extract_json_object(message.get("content") or "") or {}

    async def complete(self, *, system: str, prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": self._max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        data = await self._post("/chat/completions", payload)
        message = (data.get("choices") or [{}])[0].get("message") or {}
        return message.get("content") or ""

    async def aclose(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------
class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 60.0,
        retries: int = 2,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._retries = retries
        self._max_tokens = max_tokens

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.post(path, json=payload)
                if response.status_code >= 400:
                    raise LLMError(
                        f"anthropic HTTP {response.status_code}: {response.text[:300]}"
                    )
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self._retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise LLMError(f"anthropic request failed: {last_error}")

    async def decide(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [
                {
                    "name": TOOL_NAME,
                    "description": TOOL_DESCRIPTION,
                    "input_schema": schema,
                }
            ],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
        }
        data = await self._post("/messages", payload)
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                value = block.get("input")
                if isinstance(value, dict):
                    return value
        text = "".join(
            block.get("text", "")
            for block in (data.get("content") or [])
            if isinstance(block, dict) and block.get("type") == "text"
        )
        return extract_json_object(text) or {}

    async def complete(self, *, system: str, prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        data = await self._post("/messages", payload)
        return "".join(
            block.get("text", "")
            for block in (data.get("content") or [])
            if isinstance(block, dict) and block.get("type") == "text"
        )

    async def aclose(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------
class GeminiClient(LLMClient):
    provider = "gemini"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 60.0,
        retries: int = 2,
        max_tokens: int = 2048,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)
        self._retries = retries
        self._max_tokens = max_tokens

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        url = f"{path}?key={self._api_key}"
        for attempt in range(self._retries + 1):
            try:
                response = await self._client.post(url, json=payload)
                if response.status_code >= 400:
                    raise LLMError(f"gemini HTTP {response.status_code}: {response.text[:300]}")
                return response.json()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self._retries:
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise LLMError(f"gemini request failed: {last_error}")

    async def decide(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": TOOL_NAME,
                            "description": TOOL_DESCRIPTION,
                            "parameters": to_gemini_schema(schema),
                        }
                    ]
                }
            ],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": [TOOL_NAME],
                }
            },
            "generationConfig": {"temperature": temperature, "maxOutputTokens": self._max_tokens},
        }
        data = await self._post(f"/models/{self.model}:generateContent", payload)
        for candidate in data.get("candidates") or []:
            for part in (candidate.get("content") or {}).get("parts") or []:
                call = part.get("functionCall")
                if call and call.get("name") == TOOL_NAME:
                    args = call.get("args")
                    if isinstance(args, dict):
                        return args
        text = "".join(
            part.get("text", "")
            for candidate in (data.get("candidates") or [])
            for part in ((candidate.get("content") or {}).get("parts") or [])
        )
        return extract_json_object(text) or {}

    async def complete(self, *, system: str, prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": self._max_tokens},
        }
        data = await self._post(f"/models/{self.model}:generateContent", payload)
        return "".join(
            part.get("text", "")
            for candidate in (data.get("candidates") or [])
            for part in ((candidate.get("content") or {}).get("parts") or [])
        )

    async def aclose(self) -> None:
        await self._client.aclose()
