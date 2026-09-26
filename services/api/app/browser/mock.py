"""Built-in website simulator.

This is *not* a toy: it is a small but realistic e-commerce application with the
same deliberately planted defects as the DemoShop reference app. It lets the
full PROBE pipeline (agents -> investigation -> evidence -> findings -> report)
run end to end without a browser binary, which is invaluable for demos and CI.

Planted defects (mirrored from ``demoshop``):

1. duplicate payment requests when the pay action is triggered repeatedly
2. no loading/progress feedback while a payment is pending
3. search crashes with no recovery path
4. long free-text input overflows the layout
5. cart state is lost when the user navigates back
6. artificially slow network on demand (``?slow=1``)
"""

from __future__ import annotations

import html
import time
from pathlib import Path
from typing import Any

from .base import ActionResult, BrowserController, ElementRef

PRODUCTS = [
    {"id": "p1", "name": "Aurora Wireless Headphones", "price": 129.0, "tag": "audio"},
    {"id": "p2", "name": "Nimbus Mechanical Keyboard", "price": 89.5, "tag": "desk"},
    {"id": "p3", "name": "Vector 4K Webcam", "price": 74.0, "tag": "video"},
    {"id": "p4", "name": "Halo Desk Lamp", "price": 42.0, "tag": "desk"},
    {"id": "p5", "name": "Pulse Fitness Band", "price": 59.99, "tag": "wearable"},
]

#: how long a payment stays "in flight" — clicking pay again inside this window
#: fires a duplicate request (planted defect #1)
DEFAULT_PAYMENT_LATENCY = 3.0
LONG_INPUT_THRESHOLD = 200


class MockBrowser(BrowserController):
    """In-memory DemoShop simulator for CI and explicitly requested demos only."""

    simulated = True

    def __init__(self, *, label: str = "agent", latency: float = 1.2) -> None:
        self.label = label
        self._latency = latency
        self._slow = False

        self.page = "home"
        self.history: list[str] = ["home"]
        self.query = ""
        self.cart: list[str] = []
        self.product: str | None = None
        self.payments = 0
        self.duplicate_payments = 0
        self.review_text = ""
        self._pending_payment_until: float | None = None
        self._console: list[dict[str, Any]] = []
        self._network: list[dict[str, Any]] = []
        self.flags: dict[str, Any] = {}
        self._element_seq = 0

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:  # nothing to boot
        return None

    async def close(self) -> None:
        return None

    # ------------------------------------------------------------------
    # page model
    # ------------------------------------------------------------------
    @property
    def _url(self) -> str:
        suffix = "?slow=1" if self._slow else ""
        if self.page == "home":
            return f"https://demoshop.local/#/home{suffix}"
        if self.page == "search":
            return f"https://demoshop.local/#/search?q={self.query}{suffix}"
        if self.page == "search_error":
            return f"https://demoshop.local/#/search?q={self.query}&error=1{suffix}"
        if self.page == "product":
            return f"https://demoshop.local/#/product/{self.product}{suffix}"
        if self.page == "cart":
            return f"https://demoshop.local/#/cart{suffix}"
        if self.page == "checkout":
            return f"https://demoshop.local/#/checkout{suffix}"
        if self.page == "success":
            return f"https://demoshop.local/#/order/confirmed{suffix}"
        return f"https://demoshop.local/#/{self.page}{suffix}"

    @property
    def _title(self) -> str:
        return {
            "home": "DemoShop — Home",
            "search": f"Search results for “{self.query}”",
            "search_error": "DemoShop — Search",
            "product": f"{self._product_name()} — DemoShop",
            "cart": f"Your cart ({len(self.cart)})",
            "checkout": "Checkout — DemoShop",
            "success": "Order confirmed — DemoShop",
        }.get(self.page, "DemoShop")

    def _product_name(self) -> str:
        for product in PRODUCTS:
            if product["id"] == self.product:
                return product["name"]
        return "Product"

    def _results(self) -> list[dict[str, Any]]:
        needle = self.query.lower().strip()
        if not needle:
            return PRODUCTS
        return [p for p in PRODUCTS if needle in p["name"].lower() or needle in p["tag"]]

    def _page_elements(self) -> list[ElementRef]:
        elements: list[ElementRef] = []
        seq = 0

        def add(**kwargs: Any) -> None:
            nonlocal seq
            seq += 1
            elements.append(ElementRef(id=f"e{seq}", **kwargs))

        if self.page == "home":
            add(
                tag="input",
                role="textbox",
                type="text",
                placeholder="Search products…",
                name="q",
                text=self.query,
            )
            add(tag="button", role="button", text="Search", type="submit")
            for product in PRODUCTS[:3]:
                add(tag="a", role="link", text=product["name"], href=f"#/product/{product['id']}")
            add(tag="a", role="link", text=f"Cart ({len(self.cart)})", href="#/cart")

        elif self.page == "search":
            add(tag="input", role="textbox", type="text", placeholder="Search products…", name="q", text=self.query)
            add(tag="button", role="button", text="Search", type="submit")
            for product in self._results():
                add(tag="a", role="link", text=product["name"], href=f"#/product/{product['id']}")
            add(tag="a", role="link", text="Back to home", href="#/home")

        elif self.page == "search_error":
            add(tag="p", role="text", text="Something went wrong.")
            add(tag="button", role="button", text="Dismiss", type="button")

        elif self.page == "product":
            add(tag="button", role="button", text="Add to cart", type="button")
            add(tag="input", role="spinbutton", type="number", text="1", name="quantity")
            add(tag="textarea", role="textbox", placeholder="Write a review…", name="review", text=self.review_text)
            add(tag="button", role="button", text="Submit review", type="submit")
            add(tag="a", role="link", text=f"Cart ({len(self.cart)})", href="#/cart")
            add(tag="a", role="link", text="Back to results", href="#/search")

        elif self.page == "cart":
            if not self.cart:
                add(tag="p", role="text", text="Your cart is empty.")
            for item in self.cart:
                add(tag="p", role="text", text=self._product_name_by_id(item))
            add(tag="button", role="button", text="Checkout", type="button")
            add(tag="a", role="link", text="Continue shopping", href="#/home")

        elif self.page == "checkout":
            add(tag="input", role="textbox", type="text", placeholder="Full name", name="name")
            add(tag="input", role="textbox", type="text", placeholder="Address", name="address")
            add(tag="input", role="textbox", type="text", placeholder="Card number", name="card")
            add(tag="button", role="button", text="Pay now", type="submit")

        elif self.page == "success":
            add(tag="p", role="text", text="Thank you! Your order is confirmed.")
            add(tag="p", role="text", text=f"Payment requests received: {self.payments}")
            add(tag="a", role="link", text="Back to home", href="#/home")

        return elements

    def _product_name_by_id(self, product_id: str) -> str:
        for product in PRODUCTS:
            if product["id"] == product_id:
                return product["name"]
        return product_id

    def _page_text(self) -> str:
        if self.page == "home":
            return (
                "DemoShop — Home. Search products… Search. "
                + " ".join(p["name"] for p in PRODUCTS[:3])
                + f" Cart ({len(self.cart)})"
            )
        if self.page == "search":
            return f"Search results for “{self.query}”: " + ", ".join(
                p["name"] for p in self._results()
            )
        if self.page == "search_error":
            return (
                "Something went wrong. Uncaught TypeError: Cannot read properties of "
                "undefined (reading 'map'). [Dismiss]"
            )
        if self.page == "product":
            return f"{self._product_name()} — Add to cart — Write a review… — Submit review"
        if self.page == "cart":
            if not self.cart:
                return "Your cart is empty. Checkout. Continue shopping."
            return "Your cart: " + ", ".join(self._product_name_by_id(i) for i in self.cart) + " Checkout."
        if self.page == "checkout":
            return "Checkout — Full name — Address — Card number — Pay now"
        if self.page == "success":
            return (
                f"Thank you! Your order is confirmed. Payment requests received: {self.payments}"
            )
        return ""

    def _dom(self) -> str:
        body = html.escape(self._page_text())
        elements = "".join(
            f'<button data-probe-id="{el.id}">{html.escape(el.text or el.placeholder)}</button>'
            if el.tag in {"button", "a"}
            else f'<input data-probe-id="{el.id}" placeholder="{html.escape(el.placeholder)}" value="{html.escape(el.text)}">'
            for el in self._page_elements()
        )
        return f"<!doctype html><html><head><title>{html.escape(self._title)}</title></head><body><main>{body}</main>{elements}</body></html>"

    # ------------------------------------------------------------------
    # network / console simulation
    # ------------------------------------------------------------------
    def _log_response(self, method: str, path: str, status: int, duration_ms: float, **extra: Any) -> None:
        entry: dict[str, Any] = {
            "kind": "response",
            "method": method,
            "url": f"https://demoshop.local/api{path}",
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "resource_type": "xhr",
            "ts": time.time(),
        }
        entry.update(extra)
        self._network.append(entry)

    def _log_error(self, text: str, level: str = "error") -> None:
        self._console.append({"kind": "console", "level": level, "text": text[:400], "ts": time.time()})

    # ------------------------------------------------------------------
    # state transitions
    # ------------------------------------------------------------------
    def _reset_page_state(self) -> None:
        """Client state a fresh page load would clear."""
        self.flags.pop("duplicate_payment", None)
        self.flags.pop("layout_overflow", None)
        self.flags.pop("search_error", None)
        self.flags.pop("cart_lost_on_back", None)
        self.flags.pop("slow_response", None)
        self.flags.pop("no_payment_feedback", None)
        self.flags.pop("no_payment_feedback", None)
        self._pending_payment_until = None

    def _goto(self, page: str, *, push_history: bool = True) -> None:
        self.page = page
        if push_history:
            self.history.append(page)
        self._console.clear()
        self._network.clear()
        self._reset_page_state()
        self._log_response("GET", f"/{page}", 200, 45.0)

    def _do_action(self, element: ElementRef) -> str:
        text = (element.text or "").lower()
        placeholder = (element.placeholder or "").lower()

        if "search" in text and element.tag == "button":
            return self._submit_search()
        if "add to cart" in text:
            self.cart.append(self.product or "p1")
            self._log_response("POST", "/cart", 201, 90.0)
            return f"added {self._product_name()} to cart"
        if text.startswith("cart"):
            self._goto("cart")
            return "opened cart"
        if "checkout" in text:
            self._goto("checkout")
            return "opened checkout"
        if "pay" in text:
            return self._pay()
        if "continue shopping" in text or "back to home" in text:
            self._goto("home")
            return "returned home"
        if "back to results" in text:
            self._goto("search")
            return "returned to search results"
        if "dismiss" in text:
            # planted defect #3: the only offered action does not recover
            self.flags["search_error"] = "unrecoverable"
            return "dismissed error banner (search still broken)"
        if "submit review" in text:
            if len(self.review_text) > LONG_INPUT_THRESHOLD:
                self.flags["layout_overflow"] = True
                self._log_error(
                    "Layout overflow detected: content width 1420px exceeds viewport 1280px",
                    level="warning",
                )
            self._log_response("POST", "/reviews", 201, 140.0)
            return "submitted review"
        if element.tag == "a" and element.href:
            target = element.href.replace("#/", "").split("?")[0]
            if target.startswith("product/"):
                self.product = target.split("/")[1]
                self._goto("product")
                return f"opened product {self._product_name()}"
            self._goto(target or "home")
            return f"navigated to {target or 'home'}"
        if element.tag == "input" and "search" in placeholder:
            return "focused search field"
        return f"clicked {element.text or element.tag}"

    def _submit_search(self) -> str:
        query = self.query.lower()
        if any(token in query for token in ("error", "fail", "crash", "undefined")):
            self._goto("search_error")
            self.flags["search_error"] = "unrecoverable"
            self._console.append(
                {
                    "kind": "exception",
                    "level": "error",
                    "text": (
                        "Uncaught TypeError: Cannot read properties of undefined (reading 'map') "
                        "at SearchResults (Search.jsx:24:11)"
                    ),
                    "ts": time.time(),
                }
            )
            self._log_response("GET", f"/search?q={self.query}", 500, 220.0)
            return "search crashed with a 500"
        self._goto("search")
        return f"searched for “{self.query}” ({len(self._results())} results)"

    def _pay(self) -> str:
        now = time.monotonic()
        latency = 6.0 if self._slow else DEFAULT_PAYMENT_LATENCY
        if self._pending_payment_until is not None and now < self._pending_payment_until:
            # planted defect #1: the button stays enabled while a request is in
            # flight and there is no idempotency key
            self.payments += 1
            self.duplicate_payments += 1
            self.flags["duplicate_payment"] = True
            self._console.append(
                {
                    "kind": "exception",
                    "level": "error",
                    "text": "Duplicate payment request detected — idempotency key missing",
                    "ts": time.time(),
                }
            )
            self._log_response(
                "POST", "/payments", 201, 40.0, duplicate=True, attempt=self.payments
            )
            return "duplicate payment request fired"
        self._pending_payment_until = now + latency
        self.payments += 1
        if self._slow:
            self.flags["slow_response"] = f"{latency:.1f}s"
        # planted defect #2: the button stays enabled and nothing on screen
        # tells the user that a request is in flight
        self.flags["no_payment_feedback"] = "no loading indicator while payment is pending"
        self._log_response("POST", "/payments", 201, latency * 1000, attempt=self.payments)
        return "payment submitted"

    # ------------------------------------------------------------------
    # controller API
    # ------------------------------------------------------------------
    async def navigate(self, url: str) -> ActionResult:
        started = time.perf_counter()
        self._slow = "slow=1" in url
        # accept both "https://host/#/cart" and a bare "https://host"
        route = (url.split("#/")[-1].split("?")[0] or "home") if "#/" in url else "home"
        if route.startswith("product/"):
            self.product = route.split("/")[1]
            self._goto("product")
        elif route.startswith("search"):
            self._goto("search")
        else:
            self._goto(route)
        return ActionResult(
            ok=True,
            action="navigate",
            target=url,
            detail=f"loaded {self._title}",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            before={"url": "", "page": ""},
            after=await self.get_state(),
        )

    async def go_back(self) -> ActionResult:
        started = time.perf_counter()
        if len(self.history) > 1:
            previous = self.history[-2]
            self.history.pop()
            # planted defect #5: leaving the cart destroys its contents
            cart_was_lost = (
                self.page == "cart"
                and previous in {"home", "search", "product"}
                and bool(self.cart)
            )
            if cart_was_lost:
                self.cart = []
            self._goto(previous, push_history=False)
            # the flag is set after _goto so it survives the page-state reset
            if cart_was_lost:
                self.flags["cart_lost_on_back"] = True
                self._log_error("Cart state discarded on back navigation", level="warning")
            detail = f"went back to {previous}"
        else:
            detail = "no history entry"
        return ActionResult(
            ok=True,
            action="go_back",
            detail=detail,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            before={},
            after=await self.get_state(),
        )

    async def reload(self) -> ActionResult:
        started = time.perf_counter()
        self._goto(self.page, push_history=False)
        return ActionResult(
            ok=True,
            action="reload",
            detail="reloaded page",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            after=await self.get_state(),
        )

    async def click(self, target: Any) -> ActionResult:
        started = time.perf_counter()
        elements = self._page_elements()
        from .base import resolve_target

        element = resolve_target(elements, target)
        if element is None:
            return ActionResult(
                ok=False,
                action="click",
                target=target,
                error=f"element not found: {target!r}",
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        before = await self.get_state()
        detail = self._do_action(element)
        return ActionResult(
            ok=True,
            action="click",
            target=element.describe(),
            detail=detail,
            element_tag=element.tag,
            element_label=element.text or element.placeholder or element.aria_label,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            before=before,
            after=await self.get_state(),
        )

    async def type_text(self, target: Any, text: str) -> ActionResult:
        started = time.perf_counter()
        elements = self._page_elements()
        from .base import resolve_target

        element = resolve_target(elements, target)
        if element is None:
            return ActionResult(
                ok=False,
                action="type_text",
                target=target,
                error=f"input not found: {target!r}",
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
        before = await self.get_state()
        if "search" in (element.placeholder or "").lower() or element.name == "q":
            self.query = text
        elif element.name == "review":
            self.review_text = text
        # planted defect #4: long values are accepted and break the layout
        if len(text) > LONG_INPUT_THRESHOLD:
            self.flags["layout_overflow"] = True
            self._log_error(
                f"Layout overflow detected: content width 1420px exceeds viewport 1280px "
                f"(input length {len(text)})",
                level="warning",
            )
        return ActionResult(
            ok=True,
            action="type_text",
            target=element.describe(),
            detail=f"typed {len(text)} characters",
            element_tag=element.tag,
            element_label=element.placeholder or element.aria_label or element.name,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            before=before,
            after=await self.get_state(),
        )

    async def scroll(self, direction: str = "down", amount: int = 600) -> ActionResult:
        return ActionResult(
            ok=True,
            action="scroll",
            target=direction,
            detail=f"scrolled {direction}",
            duration_ms=8.0,
            after=await self.get_state(),
        )

    async def press_key(self, key: str) -> ActionResult:
        started = time.perf_counter()
        detail = f"pressed {key}"
        if key.lower() == "enter":
            for element in self._page_elements():
                if element.tag == "button" and "search" in (element.text or "").lower():
                    detail = self._submit_search()
                    break
        return ActionResult(
            ok=True,
            action="press_key",
            target=key,
            detail=detail,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            after=await self.get_state(),
        )

    async def wait(self, seconds: float) -> ActionResult:
        await_safe = max(0.0, min(float(seconds), 30.0))
        import asyncio

        await asyncio.sleep(await_safe)
        return ActionResult(
            ok=True,
            action="wait",
            target=seconds,
            detail=f"waited {await_safe:.1f}s",
            duration_ms=await_safe * 1000,
            after=await self.get_state(),
        )

    async def screenshot(self, path_stem: Path, full_page: bool = False) -> Path:
        target = Path(str(path_stem) + ".svg")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self._render_svg(), encoding="utf-8")
        return target

    async def get_dom(self) -> str:
        return self._dom()

    async def get_console_errors(self) -> list[dict[str, Any]]:
        return list(self._console[-50:])

    async def get_network_logs(self) -> list[dict[str, Any]]:
        return list(self._network[-100:])

    async def get_elements(self) -> list[ElementRef]:
        return self._page_elements()

    async def get_state(self) -> dict[str, Any]:
        return {
            "url": self._url,
            "title": self._title,
            "page": self.page,
            "text": self._page_text(),
            "element_count": len(self._page_elements()),
            "cart": list(self.cart),
            "payments": self.payments,
            "duplicate_payments": self.duplicate_payments,
            "pending_payment": self._pending_payment_until is not None
            and time.monotonic() < self._pending_payment_until,
            "viewport": {"width": 1280, "height": 800},
            "flags": dict(self.flags),
        }

    # ------------------------------------------------------------------
    # rendering (used for the live preview + evidence screenshots)
    # ------------------------------------------------------------------
    def _render_svg(self) -> str:
        width, height = (1280, 800) if True else (1280, 800)
        palette = {
            "home": "#0ea5e9",
            "search": "#8b5cf6",
            "search_error": "#ef4444",
            "product": "#10b981",
            "cart": "#f59e0b",
            "checkout": "#ec4899",
            "success": "#22c55e",
        }
        accent = palette.get(self.page, "#64748b")
        rows: list[str] = []
        y = 250
        for element in self._page_elements():
            label = element.text or element.placeholder or element.tag
            fill = "#0f172a" if element.tag != "button" else accent
            stroke = "#334155"
            text_fill = "#e2e8f0"
            rows.append(
                f'<rect x="360" y="{y}" width="560" height="44" rx="8" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="1"/>'
                f'<text x="380" y="{y + 27}" font-family="monospace" font-size="15" '
                f'fill="{text_fill}">{html.escape(label[:58])}</text>'
                f'<text x="330" y="{y + 27}" font-family="monospace" font-size="12" '
                f'fill="#64748b" text-anchor="end">{element.id}</text>'
            )
            y += 56
            if y > 700:
                break
        flags_text = ", ".join(f"{k}={v}" for k, v in self.flags.items()) or "none"
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="#0b1220"/>
  <rect x="0" y="0" width="{width}" height="70" fill="#111c2e"/>
  <text x="40" y="45" font-family="sans-serif" font-size="26" font-weight="700" fill="#f8fafc">DemoShop</text>
  <text x="{width - 40}" y="45" font-family="monospace" font-size="15" fill="{accent}" text-anchor="end">{html.escape(self.page.upper())}</text>
  <text x="40" y="120" font-family="monospace" font-size="15" fill="#94a3b8">URL: {html.escape(self._url)}</text>
  <text x="40" y="150" font-family="monospace" font-size="15" fill="#94a3b8">TITLE: {html.escape(self._title)}</text>
  <text x="40" y="180" font-family="monospace" font-size="13" fill="#64748b">STATE: cart={len(self.cart)} payments={self.payments} duplicates={self.duplicate_payments}</text>
  <text x="40" y="205" font-family="monospace" font-size="13" fill="#64748b">FLAGS: {html.escape(flags_text)}</text>
  <text x="40" y="235" font-family="monospace" font-size="13" fill="#475569">SIMULATED BROWSER VIEW</text>
  {''.join(rows)}
  <text x="40" y="770" font-family="monospace" font-size="12" fill="#475569">PROBE simulator — {html.escape(self.label)}</text>
</svg>"""
