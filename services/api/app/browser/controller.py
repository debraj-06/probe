"""Playwright (Chromium) implementation of the PROBE browser controller."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from .base import ActionResult, BrowserController, ElementRef, resolve_target


class _HarnessError(RuntimeError):
    """Raised when a browser action cannot be performed by the harness itself.

    Distinct from an application defect: for example ``go_back`` when the
    browser has no history yet. These are recorded but never reported as
    findings.
    """

logger = logging.getLogger("probe.browser")
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HIGH_IMPACT_CONTROL = re.compile(
    r"\b(pay(?:\s+now)?|purchase|buy\s+now|place\s+order|delete|remove\s+account|cancel\s+subscription)\b",
    re.IGNORECASE,
)


def should_block_request(method: str, *, allow_mutations: bool) -> bool:
    """Return whether a request must be stopped by the browser's read-only guard."""
    return not allow_mutations and method.upper() in WRITE_METHODS


#: JS that tags every visible interactive element with a stable id and returns
#: a compact descriptor for each one.
COLLECT_ELEMENTS_JS = """
() => {
  const out = [];
  const selector = 'a[href], button, input, select, textarea, [role="button"], [role="link"], [role="textbox"], [role="checkbox"], [onclick], summary, [tabindex]:not([tabindex="-1"])';
  const nodes = Array.from(document.querySelectorAll(selector));
  const collected = [];
  for (const el of nodes) {
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    const visible = rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none' && style.opacity !== '0';
    if (!visible) continue;
    const isField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName);
    const raw = isField ? (el.value || '') : (el.innerText || '');
    const label = (el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('name') || el.getAttribute('title') || raw || '').trim();
    // unique-ish css path so a click stays valid even if ids get re-assigned
    let path = el.tagName.toLowerCase();
    if (el.id) { path = '#' + el.id; }
    else {
      const classes = Array.from(el.classList || []).slice(0, 2).map(c => '.' + c).join('');
      const parent = el.parentElement;
      const siblings = parent ? Array.from(parent.children).filter(n => n.tagName === el.tagName) : [];
      if (siblings.length > 1) {
        path = el.tagName.toLowerCase() + classes + ':nth-of-type(' + (Array.from(parent.children).indexOf(el) + 1) + ')';
      } else {
        path = el.tagName.toLowerCase() + classes;
      }
    }
    // identity used for stable numbering — deliberately excludes the current
    // value of a field so typing does not reshuffle every id on the page
    const identity = [
      el.tagName.toLowerCase(),
      el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('name') || el.getAttribute('title') || '',
      el.getAttribute('href') || '',
      el.getAttribute('type') || '',
      el.getAttribute('role') || '',
    ].join('|');
    collected.push({
      el, identity,
      item: {
        tag: el.tagName.toLowerCase(),
        role: el.getAttribute('role') || el.tagName.toLowerCase(),
        type: el.getAttribute('type') || '',
        text: String(raw).trim().slice(0, 140),
        placeholder: el.getAttribute('placeholder') || '',
        aria_label: el.getAttribute('aria-label') || '',
        name: el.getAttribute('name') || '',
        href: el.getAttribute('href') || '',
        disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true'),
        selector: path,
        bbox: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
      }
    });
  }
  // Number in a deterministic order so "e7" keeps meaning the same control
  // after the app re-renders. Without this, an id captured one step ago can
  // point at a completely different element on the next observation.
  collected.sort((a, b) => a.identity < b.identity ? -1 : (a.identity > b.identity ? 1 : 0));
  collected.forEach((entry, index) => {
    const id = 'e' + (index + 1);
    entry.el.setAttribute('data-probe-id', id);
    out.push(Object.assign({ id }, entry.item));
  });
  return out;
}
"""


class PlaywrightController(BrowserController):
    """Drives a real Chromium page and records evidence while doing so."""

    def __init__(
        self,
        *,
        label: str = "agent",
        headless: bool = True,
        viewport: dict[str, int] | None = None,
        record_video: bool = False,
        video_dir: Path | None = None,
        playwright: Playwright | None = None,
        allow_mutations: bool = False,
    ) -> None:
        self.label = label
        self._headless = headless
        self._viewport = viewport or {"width": 1280, "height": 800}
        self._record_video = record_video
        self._video_dir = video_dir
        self._pw = playwright
        self._owns_pw = playwright is None
        self.allow_mutations = allow_mutations
        self.simulated = False
        self._blocked_request_keys: dict[tuple[str, str], int] = {}

        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._console: list[dict[str, Any]] = []
        self._network: list[dict[str, Any]] = []
        self._request_starts: dict[int, float] = {}
        self._video_path: str | None = None

    # -- lifecycle --------------------------------------------------------
    async def start(self) -> None:
        if self._pw is None:
            self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self._headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context_kwargs: dict[str, Any] = {
            "viewport": self._viewport,
            "ignore_https_errors": True,
            "user_agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36 PROBE-Agent"
            ),
        }
        if self._record_video and self._video_dir:
            self._video_dir.mkdir(parents=True, exist_ok=True)
            context_kwargs["record_video_dir"] = str(self._video_dir)
            context_kwargs["record_video_size"] = self._viewport
        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(15_000)
        await self._page.route("**/*", self._guard_route)
        self._attach_listeners()

    async def _guard_route(self, route: Any) -> None:
        request = route.request
        if should_block_request(request.method, allow_mutations=self.allow_mutations):
            key = (request.method.upper(), request.url)
            self._blocked_request_keys[key] = self._blocked_request_keys.get(key, 0) + 1
            await route.abort("blockedbyclient")
            return
        await route.continue_()

    def _attach_listeners(self) -> None:
        page = self._page
        assert page is not None

        def on_console(message: Any) -> None:
            if message.type in {"error", "warning"}:
                self._console.append(
                    {
                        "kind": "console",
                        "level": message.type,
                        "text": str(message.text)[:500],
                        "ts": time.time(),
                    }
                )

        def on_page_error(error: Any) -> None:
            self._console.append(
                {"kind": "exception", "level": "error", "text": str(error)[:500], "ts": time.time()}
            )

        def on_request(request: Any) -> None:
            self._request_starts[id(request)] = time.perf_counter()

        def on_response(response: Any) -> None:
            started = self._request_starts.pop(id(response.request), None)
            duration = (time.perf_counter() - started) * 1000 if started else 0.0
            entry = {
                "kind": "response",
                "method": response.request.method,
                "url": response.url,
                "status": response.status,
                "duration_ms": round(duration, 1),
                "resource_type": response.request.resource_type,
                "ts": time.time(),
            }
            self._network.append(entry)

        def on_request_failed(request: Any) -> None:
            request_id = id(request)
            self._request_starts.pop(request_id, None)
            key = (request.method.upper(), request.url)
            blocked_count = self._blocked_request_keys.get(key, 0)
            blocked = blocked_count > 0
            if blocked_count > 1:
                self._blocked_request_keys[key] = blocked_count - 1
            elif blocked_count:
                self._blocked_request_keys.pop(key, None)
            self._network.append(
                {
                    "kind": "blocked" if blocked else "failed",
                    "method": request.method,
                    "url": request.url,
                    "status": None,
                    "reason": "read-only protection" if blocked else None,
                    "failure": "" if blocked else (request.failure or "")[:200],
                    "duration_ms": 0.0,
                    "ts": time.time(),
                }
            )

        page.on("console", on_console)
        page.on("pageerror", on_page_error)
        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)

    async def close(self) -> None:
        try:
            if self._page is not None and self._page.video:
                try:
                    self._video_path = await self._page.video.path()
                except Exception:  # noqa: BLE001 - video is best effort
                    self._video_path = None
            if self._context is not None:
                await self._context.close()
            if self._browser is not None:
                await self._browser.close()
        finally:
            if self._pw is not None and self._owns_pw:
                await self._pw.stop()

    @property
    def video_path(self) -> str | None:
        return self._video_path

    # -- helpers ----------------------------------------------------------
    async def _run(
        self,
        action: str,
        target: Any,
        fn: Any,
        detail: str = "",
        element_tag: str = "",
        element_label: str = "",
    ) -> ActionResult:
        page = self._page
        assert page is not None
        before = await self.get_state()
        started = time.perf_counter()
        error: str | None = None
        error_kind = "app"
        ok = True
        try:
            await fn()
        except _HarnessError as exc:
            ok = False
            error = str(exc)
            error_kind = "harness"
        except Exception as exc:  # noqa: BLE001 - surfaced as evidence
            ok = False
            error = f"{type(exc).__name__}: {exc}".strip()[:300]
        duration = (time.perf_counter() - started) * 1000
        after = await self.get_state()
        return ActionResult(
            ok=ok,
            action=action,
            target=target,
            detail=detail,
            error=error,
            error_kind=error_kind,
            duration_ms=round(duration, 1),
            element_tag=element_tag,
            element_label=element_label,
            before=before,
            after=after,
        )

    async def _elements(self) -> list[ElementRef]:
        page = self._page
        assert page is not None
        try:
            raw = await page.evaluate(COLLECT_ELEMENTS_JS)
        except Exception:  # noqa: BLE001 - page may be navigating
            return []
        return [ElementRef(**item) for item in raw]

    async def _resolve_live(self, target: Any) -> tuple[ElementRef | None, str]:
        """Resolve a target to an element that exists *right now*.

        Ids are re-assigned on every observation, so a target captured one step
        ago can miss a freshly collected list even though the very same DOM node
        is still on the page. When that happens, fall back to the
        ``data-probe-id`` attribute written onto the node itself — that is the
        identity that actually survives a re-render.
        """
        elements = await self._elements()
        element = resolve_target(elements, target)
        if element is not None:
            return element, ""

        page = self._page
        assert page is not None
        raw = str(target or "").strip()
        probe_id = (
            raw[6:]
            if raw.startswith("probe-")
            else raw[1:]
            if raw.startswith("e") and raw[1:].isdigit()
            else raw
        )
        if not probe_id.isdigit():
            return None, f"element not found: {target!r}"
        selector = f'[data-probe-id="{probe_id}"]'
        try:
            node = await page.query_selector(selector)
        except Exception:  # noqa: BLE001 - page may be navigating
            return None, f"element not found: {target!r}"
        if node is None:
            return None, f"element not found: {target!r}"
        try:
            tag = (await node.evaluate("el => el.tagName.toLowerCase()")) or ""
            label = (
                await node.evaluate(
                    "el => (el.getAttribute('aria-label') || el.getAttribute('placeholder')"
                    " || el.getAttribute('name') || el.getAttribute('title')"
                    " || el.innerText || '').trim()"
                )
            ) or ""
        except Exception:  # noqa: BLE001
            tag, label = "", ""
        return (
            ElementRef(id=probe_id, tag=tag, role=tag, text=label[:140], selector=selector),
            "",
        )

    # -- navigation -------------------------------------------------------
    async def navigate(self, url: str) -> ActionResult:
        self._console.clear()
        self._network.clear()
        return await self._run("navigate", url, lambda: self._page.goto(url, wait_until="domcontentloaded"))

    async def go_back(self) -> ActionResult:
        async def _back() -> None:
            response = await self._page.go_back(wait_until="domcontentloaded")
            if response is None:
                # there is genuinely nothing to go back to yet — that is a
                # limitation of the exploration harness, not an app defect
                raise _HarnessError("no history entry to go back to")

        return await self._run("go_back", None, _back)

    async def reload(self) -> ActionResult:
        self._console.clear()
        self._network.clear()
        return await self._run("reload", None, lambda: self._page.reload(wait_until="domcontentloaded"))

    # -- interaction ------------------------------------------------------
    async def click(self, target: Any) -> ActionResult:
        element, error = await self._resolve_live(target)
        if element is None:
            return ActionResult(
                ok=False,
                action="click",
                target=target,
                error=error,
            )
        element_label = element.text or element.aria_label or element.placeholder or element.name
        sensitive_label = " ".join(
            (element_label, element.href, element.name, element.type)
        )
        if not self.allow_mutations and HIGH_IMPACT_CONTROL.search(sensitive_label):
            return ActionResult(
                ok=False,
                action="click",
                target=target,
                error="blocked by read-only safety mode",
                error_kind="harness",
                element_tag=element.tag,
                element_label=element_label,
            )

        async def _click() -> None:
            locator = self._page.locator(f'[data-probe-id="{element.id}"]').first
            if element.selector and element.selector.startswith("#"):
                locator = self._page.locator(element.selector).first
            await locator.scroll_into_view_if_needed(timeout=5000)
            await locator.click(timeout=8000)

        return await self._run(
            "click",
            element.describe(),
            _click,
            element_tag=element.tag,
            element_label=element.text or element.aria_label or element.placeholder,
        )

    async def type_text(self, target: Any, text: str) -> ActionResult:
        element, error = await self._resolve_live(target)
        if element is None:
            return ActionResult(
                ok=False,
                action="type_text",
                target=target,
                error=error,
            )

        async def _type() -> None:
            locator = self._page.locator(f'[data-probe-id="{element.id}"]').first
            await locator.click(timeout=5000)
            await locator.fill("")
            await locator.type(text, delay=15)

        return await self._run(
            "type_text",
            element.describe(),
            _type,
            detail=text[:80],
            element_tag=element.tag,
            element_label=element.placeholder or element.aria_label or element.name,
        )

    async def scroll(self, direction: str = "down", amount: int = 600) -> ActionResult:
        delta = amount if direction != "up" else -amount
        return await self._run(
            "scroll",
            direction,
            lambda: self._page.mouse.wheel(0, delta),
        )

    async def press_key(self, key: str) -> ActionResult:
        return await self._run("press_key", key, lambda: self._page.keyboard.press(key))

    async def wait(self, seconds: float) -> ActionResult:
        async def _sleep() -> None:
            await asyncio.sleep(max(0.0, min(float(seconds), 30.0)))

        return await self._run("wait", seconds, _sleep)

    # -- observation ------------------------------------------------------
    async def get_elements(self) -> list[ElementRef]:
        return await self._elements()

    async def screenshot(self, path_stem: Path, full_page: bool = False) -> Path:
        page = self._page
        assert page is not None
        target = Path(str(path_stem) + ".png")
        target.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(target), full_page=full_page)
        return target

    async def get_dom(self) -> str:
        page = self._page
        assert page is not None
        try:
            return await page.content()
        except Exception:  # noqa: BLE001
            return ""

    async def get_console_errors(self) -> list[dict[str, Any]]:
        return list(self._console[-100:])

    async def get_network_logs(self) -> list[dict[str, Any]]:
        return list(self._network[-200:])

    async def get_state(self) -> dict[str, Any]:
        page = self._page
        assert page is not None
        try:
            url = page.url
        except Exception:  # noqa: BLE001
            url = "about:blank"
        title = ""
        text = ""
        element_count = 0
        try:
            title = await page.title()
        except Exception:  # noqa: BLE001
            pass
        try:
            text = (await page.evaluate("() => document.body ? document.body.innerText.slice(0, 4000) : ''")) or ""
        except Exception:  # noqa: BLE001
            pass
        try:
            element_count = len(await page.evaluate(COLLECT_ELEMENTS_JS))
        except Exception:  # noqa: BLE001
            pass
        return {
            "url": url,
            "title": title,
            "text": text,
            "element_count": element_count,
            "viewport": self._viewport,
            "flags": {},
        }
