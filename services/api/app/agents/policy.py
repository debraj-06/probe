"""Deterministic per-role policies.

These drive the *same* observe -> decide -> act loop as the LLM, which means
PROBE stays fully functional (and demoable) with ``PROBE_LLM_PROVIDER=none``.
They are also the safety net whenever an LLM call fails mid-run.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..browser.base import Observation
from .base import Decision

#: hostile values Chaos AI rotates through
HOSTILE_INPUTS = [
    "",
    "error",
    "fail",
    "undefined",
    "<script>alert(1)</script>",
    "x" * 320,
    "🎉🔥" * 20,
    "null",
    "'; DROP TABLE products;--",
]

#: queries a senior exploratory QA engineer would actually try
TECHNICAL_QUERIES = [
    "headphones",
    "zzzz-no-such-product",
    "!!!",
    "x" * 240,
    "error",
    "",
]

UX_QUERIES = ["headphones", "wireless headphones", "desk lamp"]

SAMPLE_VALUES = {
    "search": "headphones",
    "name": "Asha Roy",
    "address": "12 Park Street, Kolkata 700016",
    "card": "4242 4242 4242 4242",
    "email": "asha@example.com",
    "phone": "+91 98300 00000",
    "review": "Great product, fast delivery and solid build quality.",
    "quantity": "1",
}


def _label(element: Any) -> str:
    return (element.text or element.placeholder or element.aria_label or element.name or "").lower()


def _links(obs: Observation) -> list[Any]:
    return [el for el in obs.elements if el.tag == "a" and el.href]


def _buttons(obs: Observation) -> list[Any]:
    return [el for el in obs.elements if el.tag == "button" or el.role == "button"]


def _fields(obs: Observation) -> list[Any]:
    return [el for el in obs.elements if el.tag in {"input", "textarea", "select"}]


def _sample_value(element: Any) -> str:
    label = _label(element)
    for key, value in SAMPLE_VALUES.items():
        if key in label:
            return value
    return "test value"


class Policy:
    """Shared bookkeeping for every heuristic policy."""

    role = "base"

    def __init__(self, agent: Any = None) -> None:
        self.agent = agent
        self.clicked: set[str] = set()
        self.typed: set[str] = set()
        self.visited: set[str] = set()
        self.field_attempts: Counter = Counter()
        self.awaiting_enter = False
        self.steps_taken = 0

    # -- identity ---------------------------------------------------------
    @staticmethod
    def _key(element: Any) -> str:
        """Stable identity for a control.

        Element ids are re-assigned on every render, so they cannot be used to
        remember what an agent already did. For form fields the *current value*
        must be excluded too, otherwise typing changes the identity.
        """
        if element.tag in {"input", "textarea", "select"}:
            ident = element.placeholder or element.aria_label or element.name
        else:
            ident = element.text or element.aria_label or element.placeholder or element.name
        return f"{element.tag}|{ident.lower().strip()}|{element.href}"

    @staticmethod
    def _is_search(element: Any) -> bool:
        return "search" in _label(element) or element.name in {"q", "query", "search"}

    # -- element pickers --------------------------------------------------
    def _first_unvisited_link(self, obs: Observation) -> Any | None:
        for element in _links(obs):
            if self._key(element) not in self.clicked:
                return element
        return None

    def _first_unclicked_button(self, obs: Observation) -> Any | None:
        for element in _buttons(obs):
            if self._key(element) not in self.clicked:
                return element
        return None

    def _first_untyped_field(self, obs: Observation) -> Any | None:
        for element in _fields(obs):
            if self._key(element) not in self.typed:
                return element
        return None

    def _next_field(
        self, obs: Observation, queries: list[str], max_attempts: int = 4
    ) -> tuple[Any | None, str]:
        """Pick a field to type into.

        Search boxes are re-tested with a series of queries (normal, no-match,
        oversized, hostile) because that is exactly where input handling breaks.
        Every other field is filled once with a realistic value.
        """
        field = self._first_untyped_field(obs)
        if field is not None:
            key = self._key(field)
            self.field_attempts[key] += 1
            if self._is_search(field):
                return field, queries[min(self.field_attempts[key] - 1, len(queries) - 1)]
            return field, _sample_value(field)

        for element in _fields(obs):
            if not self._is_search(element):
                continue
            key = self._key(element)
            if self.field_attempts[key] < max_attempts:
                self.field_attempts[key] += 1
                return element, queries[min(self.field_attempts[key] - 1, len(queries) - 1)]
        return None, ""

    def _primary_control(self, obs: Observation) -> Any | None:
        preferred = ("pay", "checkout", "place order", "submit", "add to cart", "search", "buy")
        buttons = _buttons(obs)
        for keyword in preferred:
            for element in buttons:
                if keyword in _label(element) and self._key(element) not in self.clicked:
                    return element
        return buttons[0] if buttons else None

    def _journey_control(self, obs: Observation) -> Any | None:
        """The control that moves a user deeper into a transactional flow."""
        keywords = ("pay", "checkout", "place order", "add to cart", "buy", "cart", "order")
        for keyword in keywords:
            for element in _buttons(obs):
                if keyword in _label(element) and self._key(element) not in self.clicked:
                    return element
        for keyword in keywords:
            for element in _links(obs):
                if keyword in _label(element) and self._key(element) not in self.clicked:
                    return element
        return None

    def _press_enter(self) -> Decision:
        self.awaiting_enter = False
        return Decision(
            thought="Submitting the form with Enter, the way a keyboard user would.",
            action="press_key",
            args={"key": "Enter"},
            source="policy",
        )

    def decide(self, obs: Observation, step: int) -> Decision:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Technical AI
# ---------------------------------------------------------------------------
class TechnicalPolicy(Policy):
    """Cover the app, exercise forms, keep an eye on console + network."""

    role = "technical"

    def decide(self, obs: Observation, step: int) -> Decision:
        self.steps_taken = step
        self.visited.add(obs.url)

        if step % 5 == 0:
            return Decision(
                thought="Auditing the browser console for errors before continuing.",
                action="get_console_errors",
                source="policy",
            )
        if step % 5 == 2:
            return Decision(
                thought="Auditing network requests for failures or slow responses.",
                action="get_network_logs",
                source="policy",
            )
        if self.awaiting_enter:
            return self._press_enter()

        # probe inputs first: search boxes are where input handling breaks
        field, value = self._next_field(obs, TECHNICAL_QUERIES, max_attempts=6)
        if field is not None:
            self.typed.add(self._key(field))
            self.awaiting_enter = True
            preview = value if len(value) <= 24 else f"{value[:20]}… ({len(value)} chars)"
            return Decision(
                thought=f"Testing “{field.placeholder or field.name}” with {preview!r}.",
                action="type_text",
                args={"target": field.id, "text": value},
                source="policy",
            )

        # state-changing controls next: that is where defects live
        button = self._first_unclicked_button(obs)
        if button:
            self.clicked.add(self._key(button))
            return Decision(
                thought=f"Exercising the “{button.text}” control and watching for errors.",
                action="click",
                args={"target": button.id},
                source="policy",
            )

        link = self._first_unvisited_link(obs)
        if link:
            self.clicked.add(self._key(link))
            return Decision(
                thought=f"“{link.text or link.href}” has not been explored yet — checking it.",
                action="click",
                args={"target": link.id},
                source="policy",
            )

        if step % 7 == 6 and len(self.visited) > 1:
            return Decision(
                thought="Going back to re-check an earlier page for state problems.",
                action="go_back",
                source="policy",
            )
        if step % 9 == 8:
            return Decision(
                thought="Reloading the page to check for state or loading problems.",
                action="reload",
                source="policy",
            )
        return Decision(
            thought="No untested surface left on this page — moving on.",
            action="finish",
            source="policy",
        )


# ---------------------------------------------------------------------------
# UX/UI AI
# ---------------------------------------------------------------------------
class UXPolicy(Policy):
    """Interact like a user, then judge the feedback the interface gave back."""

    role = "ux"

    def decide(self, obs: Observation, step: int) -> Decision:
        self.steps_taken = step
        self.visited.add(obs.url)

        if step % 4 == 1:
            return Decision(
                thought="Scrolling to review the whole layout, not just the first screen.",
                action="scroll",
                args={"direction": "down", "amount": 700},
                source="policy",
            )
        if step % 6 == 4:
            return Decision(
                thought="Scrolling back up to compare hierarchy and spacing.",
                action="scroll",
                args={"direction": "up", "amount": 700},
                source="policy",
            )
        if self.awaiting_enter:
            return Decision(
                thought="Submitting and watching how the interface communicates progress.",
                action="press_key",
                args={"key": "Enter"},
                source="policy",
            )

        # interact with the most prominent control and watch for feedback
        button = self._primary_control(obs)
        if button and self._key(button) not in self.clicked:
            self.clicked.add(self._key(button))
            return Decision(
                thought=f"Clicking “{button.text}” and checking whether the UI responds.",
                action="click",
                args={"target": button.id},
                source="policy",
            )

        field, value = self._next_field(obs, UX_QUERIES)
        if field is not None:
            self.typed.add(self._key(field))
            self.awaiting_enter = True
            if field.tag == "textarea" or "review" in _label(field):
                value = "A" * 260
            return Decision(
                thought=f"Entering realistic content into “{field.placeholder or field.name}”.",
                action="type_text",
                args={"target": field.id, "text": value},
                source="policy",
            )

        link = self._first_unvisited_link(obs)
        if link:
            self.clicked.add(self._key(link))
            return Decision(
                thought=f"Navigating to “{link.text}” to judge the flow a user would take.",
                action="click",
                args={"target": link.id},
                source="policy",
            )

        return Decision(
            thought="Evaluated the visible flows on this page.",
            action="finish",
            source="policy",
        )


# ---------------------------------------------------------------------------
# Chaos AI
# ---------------------------------------------------------------------------
class ChaosPolicy(Policy):
    """Try to break things: bursts, hostile input, reloads, navigation abuse."""

    role = "chaos"

    def __init__(self, agent: Any = None) -> None:
        super().__init__(agent)
        self.burst_remaining = 0
        self.burst_target: str | None = None

    def decide(self, obs: Observation, step: int) -> Decision:
        self.steps_taken = step
        self.visited.add(obs.url)

        if self.burst_remaining > 0 and self.burst_target:
            # a burst is only meaningful while the control is still on screen —
            # if the last click navigated away, hammering a stale id is just
            # noise (and looks exactly like a broken control)
            if any(el.id == self.burst_target for el in obs.elements):
                self.burst_remaining -= 1
                return Decision(
                    thought="Repeating the same action as fast as possible to look for "
                    "duplicate submissions or double charges.",
                    action="click",
                    args={"target": self.burst_target},
                    source="policy",
                )
            self.burst_remaining = 0
            self.burst_target = None

        if step % 11 == 3:
            return Decision(
                thought="Reloading in the middle of a flow to test state durability.",
                action="reload",
                source="policy",
            )
        if step % 11 == 5:
            return Decision(
                thought="Abusing back navigation to see what state gets lost.",
                action="go_back",
                source="policy",
            )
        if step % 11 == 7:
            base = obs.url.split("?")[0]
            return Decision(
                thought="Re-opening the page under hostile conditions (slow network).",
                action="navigate",
                args={"url": f"{base}?slow=1"},
                source="policy",
            )

        # get deeper into a transactional flow first — that is where chaos pays off
        journey = self._journey_control(obs)
        if journey:
            self.clicked.add(self._key(journey))
            if journey.tag == "button":
                self.burst_target = journey.id
                self.burst_remaining = 2
            return Decision(
                thought=f"Driving towards “{journey.text}” so there is a real flow to break.",
                action="click",
                args={"target": journey.id},
                source="policy",
            )

        primary = self._primary_control(obs)
        if primary and self._key(primary) not in self.clicked:
            self.clicked.add(self._key(primary))
            self.burst_target = primary.id
            self.burst_remaining = 2
            return Decision(
                thought=f"Triggering “{primary.text}” and immediately repeating it.",
                action="click",
                args={"target": primary.id},
                source="policy",
            )

        field, value = self._next_field(obs, HOSTILE_INPUTS)
        if field is not None:
            self.typed.add(self._key(field))
            self.awaiting_enter = True
            return Decision(
                thought=f"Submitting hostile input ({len(value)} chars) into "
                f"“{field.placeholder or field.name}”.",
                action="type_text",
                args={"target": field.id, "text": value},
                source="policy",
            )
        if self.awaiting_enter:
            return self._press_enter()

        link = self._first_unvisited_link(obs)
        if link:
            self.clicked.add(self._key(link))
            return Decision(
                thought=f"Entering “{link.text}” to find a new flow to stress.",
                action="click",
                args={"target": link.id},
                source="policy",
            )

        button = self._first_unclicked_button(obs)
        if button:
            self.clicked.add(self._key(button))
            self.burst_target = button.id
            self.burst_remaining = 2
            return Decision(
                thought=f"Hammering “{button.text}” repeatedly.",
                action="click",
                args={"target": button.id},
                source="policy",
            )

        return Decision(
            thought="Nothing left to stress on this page.",
            action="finish",
            source="policy",
        )


# ---------------------------------------------------------------------------
# User Behavior AI
# ---------------------------------------------------------------------------
class UserPolicy(Policy):
    """Chase a real user goal: find a product and get through checkout."""

    role = "user"

    def __init__(self, agent: Any = None, goals: list[str] | None = None) -> None:
        super().__init__(agent)
        self.goals = goals or []
        self.query = "headphones"

    def _goal_text(self) -> str:
        return self.goals[0] if self.goals else "Find a product and complete checkout"

    def decide(self, obs: Observation, step: int) -> Decision:
        self.steps_taken = step
        self.visited.add(obs.url)
        text = (obs.text or "").lower()
        flags = obs.flags or {}

        # 1. goal already achieved
        if "order is confirmed" in text or "payment requests received" in text:
            return Decision(
                thought="The goal is complete — the order is confirmed.",
                action="finish",
                source="policy",
            )

        # 2. checkout form — keyed off the URL because plenty of single-page
        #    apps never update <title> when the route changes
        field = self._first_untyped_field(obs)
        on_checkout = "/checkout" in (obs.url or "").lower() or "checkout" in (obs.title or "").lower()
        if on_checkout and field is not None:
            self.typed.add(self._key(field))
            return Decision(
                thought=f"Filling in “{field.placeholder or field.name}” to continue checkout.",
                action="type_text",
                args={"target": field.id, "text": _sample_value(field)},
                source="policy",
            )

        # 3. explicit controls, in journey order — buttons *and* nav links,
        #    because plenty of real apps link to /cart and /checkout
        for keyword, thought in (
            ("add to cart", "Adding the product to the cart."),
            ("checkout", "Proceeding to checkout."),
            ("pay", "Paying for the order."),
            ("cart", "Opening the cart to review it."),
        ):
            for element in list(_buttons(obs)) + list(_links(obs)):
                if keyword in _label(element) and self._key(element) not in self.clicked:
                    self.clicked.add(self._key(element))
                    return Decision(
                        thought=thought,
                        action="click",
                        args={"target": element.id},
                        source="policy",
                    )

        # 4. search box — a real user types before pressing search
        for element in _fields(obs):
            if self._is_search(element) and self._key(element) not in self.typed:
                self.typed.add(self._key(element))
                self.awaiting_enter = True
                return Decision(
                    thought=f"Searching for “{self.query}”.",
                    action="type_text",
                    args={"target": element.id, "text": self.query},
                    source="policy",
                )
        if self.awaiting_enter:
            self.awaiting_enter = False
            return Decision(
                thought="Submitting the search.",
                action="press_key",
                args={"key": "Enter"},
                source="policy",
            )

        # 5. a search button the user reached without typing
        for element in _buttons(obs):
            if "search" in _label(element) and self._key(element) not in self.clicked:
                self.clicked.add(self._key(element))
                return Decision(
                    thought="Running the search.",
                    action="click",
                    args={"target": element.id},
                    source="policy",
                )

        # 6. first product result
        for element in _links(obs):
            if "product" in (element.href or "") and self._key(element) not in self.clicked:
                self.clicked.add(self._key(element))
                return Decision(
                    thought=f"Opening “{element.text}” to have a look.",
                    action="click",
                    args={"target": element.id},
                    source="policy",
                )

        # 6. anything else that moves us forward
        link = self._first_unvisited_link(obs)
        if link:
            self.clicked.add(self._key(link))
            return Decision(
                thought=f"Following “{link.text}” to continue towards the goal.",
                action="click",
                args={"target": link.id},
                source="policy",
            )

        # 7. something went wrong earlier — a real user would try to recover
        if flags.get("search_error"):
            return Decision(
                thought="The search broke — trying the only available recovery action.",
                action="click",
                args={"target": "Dismiss"},
                source="policy",
            )

        return Decision(
            thought="I cannot find a way forward towards the goal.",
            action="finish",
            source="policy",
        )


POLICIES: dict[str, type[Policy]] = {
    "technical": TechnicalPolicy,
    "ux": UXPolicy,
    "chaos": ChaosPolicy,
    "user": UserPolicy,
    "review": Policy,
}


def create_policy(role: str, agent: Any = None, goals: list[str] | None = None) -> Policy:
    """Factory used by the orchestrator."""
    cls = POLICIES.get(role, Policy)
    if cls is UserPolicy:
        return cls(agent, goals=goals)
    return cls(agent)
