"""Provider-agnostic LLM client interface.

PROBE never talks to an SDK directly. Every provider implements the same two
primitives:

* ``decide``  — structured "what should I do next?" (forced tool call)
* ``complete`` — free-form text generation (used for prose polish)

That keeps the agent engine identical no matter which model is plugged in.
"""

from __future__ import annotations

import abc
import json
import re
from typing import Any


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------
def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert a JSON-schema subset to Gemini's ``functionDeclarations`` format."""
    type_map = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }

    def convert(node: Any) -> Any:
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in {"additionalProperties", "strict", "default"}:
                continue
            if key == "type":
                out["type"] = type_map.get(value, "STRING") if isinstance(value, str) else value
            elif key == "properties":
                out["properties"] = {name: convert(spec) for name, spec in value.items()}
            elif key == "items":
                out["items"] = convert(value)
            elif key == "enum":
                out["enum"] = value
            elif key == "required":
                out["required"] = value
            else:
                out[key] = convert(value)
        return out

    converted = convert(schema)
    if isinstance(converted, dict) and converted.get("type") == "object":
        converted.setdefault("required", list(converted.get("properties", {}).keys()))
    return converted


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort JSON object extraction from messy model output."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : index + 1]
                    try:
                        parsed = json.loads(candidate)
                    except ValueError:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
        start = text.find("{", start + 1)
    return None


class LLMError(RuntimeError):
    """Raised when a provider call fails after retries."""


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
class LLMClient(abc.ABC):
    """One decision interface, many providers."""

    provider: str = "abstract"
    model: str = ""

    @abc.abstractmethod
    async def decide(
        self,
        *,
        system: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Return the model's next action as a validated-ish dict."""

    @abc.abstractmethod
    async def complete(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """Return free-form text."""

    async def aclose(self) -> None:  # pragma: no cover - optional
        return None

    def info(self) -> dict[str, str]:
        return {"provider": self.provider, "model": self.model}
