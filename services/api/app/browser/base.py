"""Browser abstraction shared by every PROBE agent.

The agents only ever talk to this interface, which is what makes it possible to
run the exact same agent engine against real Chromium (Playwright) or against
the built-in simulator (used for offline demos and CI).
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ElementRef:
    """A single interactive element on the page."""

    id: str
    tag: str
    role: str = ""
    type: str = ""
    text: str = ""
    placeholder: str = ""
    aria_label: str = ""
    name: str = ""
    href: str = ""
    disabled: bool = False
    selector: str = ""
    bbox: dict[str, float] | None = None

    def describe(self) -> str:
        label = self.text or self.aria_label or self.placeholder or self.name or "(no label)"
        bits = [f"<{self.tag}>"]
        if self.type:
            bits.append(f"type={self.type}")
        if self.placeholder:
            bits.append(f'placeholder="{self.placeholder}"')
        return f"[{self.id}] {' '.join(bits)} {label[:80]}"


@dataclass(slots=True)
class Observation:
    """Everything an agent can know about the current page state."""

    url: str
    title: str
    elements: list[ElementRef] = field(default_factory=list)
    dom: str = ""
    text: str = ""
    console_errors: list[dict[str, Any]] = field(default_factory=list)
    network: list[dict[str, Any]] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    viewport: dict[str, int] = field(default_factory=dict)

    def signature(self) -> str:
        """Cheap fingerprint used to detect "nothing changed" responses."""
        parts = [self.url]
        parts += sorted(f"{el.id}:{el.tag}:{el.text}" for el in self.elements)
        parts += sorted(f"{k}={v}" for k, v in self.flags.items() if v)
        return "|".join(parts)


@dataclass(slots=True)
class ActionResult:
    """Result of executing one tool call."""

    ok: bool
    action: str
    target: Any = None
    detail: str = ""
    error: str | None = None
    error_kind: str = "app"  # "app" = the application misbehaved, "harness" = our tooling
    duration_ms: float = 0.0
    element_tag: str = ""
    element_label: str = ""
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "target": self.target,
            "detail": self.detail,
            "error": self.error,
            "error_kind": self.error_kind,
            "duration_ms": self.duration_ms,
        }


# ---------------------------------------------------------------------------
# Target resolution (shared by every implementation)
# ---------------------------------------------------------------------------
def _norm(value: str) -> str:
    return " ".join((value or "").lower().split())


def resolve_target(elements: list[ElementRef], target: Any) -> ElementRef | None:
    """Resolve a loose target spec (id / text / dict) to a concrete element."""
    if target is None:
        return None

    if isinstance(target, ElementRef):
        return target

    if isinstance(target, dict):
        for key in ("element_id", "id", "ref"):
            if key in target and target[key] is not None:
                resolved = resolve_target(elements, target[key])
                if resolved:
                    return resolved
        for key in ("text", "label", "name", "placeholder", "selector"):
            if target.get(key):
                resolved = resolve_target(elements, target[key])
                if resolved:
                    return resolved
        return None

    raw = str(target).strip()
    if not raw:
        return None

    # 1. element id, e.g. "e12" / "probe-12" / "12"
    probe_id = raw[6:] if raw.startswith("probe-") else raw[1:] if raw.startswith("e") and raw[1:].isdigit() else raw
    for element in elements:
        if element.id == raw or element.id == f"e{raw}" or element.id == f"probe-{raw}":
            return element
    if probe_id.isdigit():
        for element in elements:
            if element.id.endswith(probe_id):
                return element

    # 2. exact / partial text, aria-label, placeholder, name
    needle = _norm(raw)
    for element in elements:
        for candidate in (element.text, element.aria_label, element.placeholder, element.name):
            if candidate and _norm(candidate) == needle:
                return element
    for element in elements:
        for candidate in (element.text, element.aria_label, element.placeholder, element.name):
            if candidate and needle in _norm(candidate):
                return element

    # 3. last resort: tag name
    for element in elements:
        if element.tag == raw.lower():
            return element
    return None


# ---------------------------------------------------------------------------
# Controller interface
# ---------------------------------------------------------------------------
class BrowserController(abc.ABC):
    """The clean browser-tool API the agents call."""

    label: str = "agent"

    # -- lifecycle --------------------------------------------------------
    @abc.abstractmethod
    async def start(self) -> None: ...

    @abc.abstractmethod
    async def close(self) -> None: ...

    # -- navigation -------------------------------------------------------
    @abc.abstractmethod
    async def navigate(self, url: str) -> ActionResult: ...

    @abc.abstractmethod
    async def go_back(self) -> ActionResult: ...

    @abc.abstractmethod
    async def reload(self) -> ActionResult: ...

    # -- interaction ------------------------------------------------------
    @abc.abstractmethod
    async def click(self, target: Any) -> ActionResult: ...

    @abc.abstractmethod
    async def type_text(self, target: Any, text: str) -> ActionResult: ...

    @abc.abstractmethod
    async def scroll(self, direction: str = "down", amount: int = 600) -> ActionResult: ...

    @abc.abstractmethod
    async def press_key(self, key: str) -> ActionResult: ...

    @abc.abstractmethod
    async def wait(self, seconds: float) -> ActionResult: ...

    # -- observation ------------------------------------------------------
    @abc.abstractmethod
    async def screenshot(self, path_stem: Path, full_page: bool = False) -> Path: ...

    @abc.abstractmethod
    async def get_dom(self) -> str: ...

    @abc.abstractmethod
    async def get_console_errors(self) -> list[dict[str, Any]]: ...

    @abc.abstractmethod
    async def get_network_logs(self) -> list[dict[str, Any]]: ...

    @abc.abstractmethod
    async def get_state(self) -> dict[str, Any]: ...

    async def get_elements(self) -> list[ElementRef]:
        """Interactive elements currently on the page (implemented per driver)."""
        raise NotImplementedError

    async def observe(self) -> Observation:
        """Default observation built from the primitive tools above."""
        state = await self.get_state()
        elements = await self.get_elements()
        return Observation(
            url=state.get("url", ""),
            title=state.get("title", ""),
            elements=elements,
            dom=await self.get_dom(),
            text=state.get("text", ""),
            console_errors=await self.get_console_errors(),
            network=await self.get_network_logs(),
            flags=state.get("flags", {}),
            viewport=state.get("viewport", {}),
        )

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def timed(action: str, target: Any, started: float, **kwargs: Any) -> ActionResult:
        return ActionResult(
            ok=kwargs.pop("ok", True),
            action=action,
            target=target,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            **kwargs,
        )
