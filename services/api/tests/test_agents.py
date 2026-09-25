"""Unit tests for the agent engine, simulator and Review AI."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import Agent, AgentContext, Decision, detect_anomalies
from app.agents.policy import ChaosPolicy, TechnicalPolicy, UserPolicy, create_policy
from app.agents.review import ReviewAgent, _similarity
from app.browser.base import ActionResult, Observation
from app.browser.mock import MockBrowser
from app.config import Settings
from app.db import Database
from app.events import EventBus
from app.evidence import EvidenceStore
from app.llm.base import to_gemini_schema, extract_json_object
from app.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# simulator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_simulator_reproduces_duplicate_payment(tmp_path):
    browser = MockBrowser(label="test")
    await browser.start()
    await browser.navigate("https://demoshop.local/#/checkout")
    await browser.click("Pay now")
    before = await browser.get_state()
    await browser.click("Pay now")  # rapid second click
    after = await browser.get_state()

    assert after["duplicate_payments"] == 1
    assert after["payments"] == 2
    assert after["flags"]["duplicate_payment"] is True
    console = await browser.get_console_errors()
    assert any("Duplicate payment" in entry["text"] for entry in console)
    await browser.close()


@pytest.mark.asyncio
async def test_simulator_search_crashes_without_recovery(tmp_path):
    browser = MockBrowser(label="test")
    await browser.start()
    await browser.navigate("https://demoshop.local")
    await browser.type_text("Search products…", "error")
    await browser.press_key("Enter")

    state = await browser.get_state()
    assert state["page"] == "search_error"
    assert state["flags"]["search_error"] == "unrecoverable"
    console = await browser.get_console_errors()
    assert any("TypeError" in entry["text"] for entry in console)

    # the only available action does not recover
    await browser.click("Dismiss")
    assert (await browser.get_state())["page"] == "search_error"
    await browser.close()


@pytest.mark.asyncio
async def test_simulator_long_input_overflows(tmp_path):
    browser = MockBrowser(label="test")
    await browser.start()
    await browser.navigate("https://demoshop.local/#/product/p1")
    await browser.type_text("Write a review…", "x" * 400)
    await browser.click("Submit review")
    assert (await browser.get_state())["flags"]["layout_overflow"] is True
    await browser.close()


@pytest.mark.asyncio
async def test_simulator_back_navigation_loses_cart(tmp_path):
    browser = MockBrowser(label="test")
    await browser.start()
    await browser.navigate("https://demoshop.local/#/product/p1")
    await browser.click("Add to cart")
    await browser.click("Cart (1)")
    assert (await browser.get_state())["cart"] == ["p1"]
    await browser.go_back()
    state = await browser.get_state()
    assert state["cart"] == []
    assert state["flags"]["cart_lost_on_back"] is True
    await browser.close()


@pytest.mark.asyncio
async def test_simulator_screenshot_is_written(tmp_path):
    browser = MockBrowser(label="test")
    await browser.start()
    await browser.navigate("https://demoshop.local")
    path = await browser.screenshot(tmp_path / "shot")
    assert path.exists()
    assert path.suffix == ".svg"
    assert b"DemoShop" in path.read_bytes()
    await browser.close()


# ---------------------------------------------------------------------------
# anomaly detection
# ---------------------------------------------------------------------------
def _observation(**kwargs) -> Observation:
    base = {"url": "https://x.test/#/a", "title": "A"}
    base.update(kwargs)
    return Observation(**base)  # type: ignore[arg-type]


def test_detect_anomalies_ignores_clean_clicks():
    before = _observation()
    after = _observation()
    # a navigation link that produces no request is not a defect
    result = ActionResult(ok=True, action="click", element_tag="a", element_label="Home")
    assert detect_anomalies(before, after, result) == []

    # a button that fires a request and changes nothing visible is fine too
    after_with_request = _observation(
        network=[{"kind": "response", "url": "https://x.test/api/cart", "status": 201}]
    )
    button = ActionResult(ok=True, action="click", element_tag="button", element_label="Add to cart")
    assert detect_anomalies(before, after_with_request, button) == []


def test_detect_anomalies_flags_new_console_errors():
    before = _observation()
    after = _observation(console_errors=[{"kind": "exception", "text": "boom"}])
    result = ActionResult(ok=True, action="click", element_tag="button")
    anomalies = detect_anomalies(before, after, result)
    assert any("console error" in item for item in anomalies)


def test_detect_anomalies_flags_dead_controls():
    before = _observation()
    after = _observation()
    result = ActionResult(ok=True, action="click", element_tag="button", element_label="Pay now")
    assert detect_anomalies(before, after, result) == [
        'no visible response from “Pay now” and no request was sent'
    ]


def test_detect_anomalies_ignores_links_without_feedback():
    before = _observation()
    after = _observation()
    result = ActionResult(ok=True, action="click", element_tag="a", element_label="Home")
    assert detect_anomalies(before, after, result) == []


# ---------------------------------------------------------------------------
# policies
# ---------------------------------------------------------------------------
def test_policies_progress_through_the_shop():
    async def scenario():
        browser = MockBrowser(label="test")
        await browser.start()
        await browser.navigate("https://demoshop.local")
        policy = UserPolicy(goals=["Find a product and complete checkout"])
        observation = await browser.observe()
        for _ in range(40):
            decision = policy.decide(observation, 1)
            if decision.action == "finish":
                break
            if decision.action == "click":
                await browser.click(decision.args["target"])
            elif decision.action == "type_text":
                await browser.type_text(decision.args["target"], decision.args.get("text", ""))
            elif decision.action == "press_key":
                await browser.press_key(decision.args.get("key", "Enter"))
            else:
                break
            observation = await browser.observe()
        state = await browser.get_state()
        await browser.close()
        return state

    state = asyncio.run(scenario())
    assert state["payments"] >= 1, "the user policy should reach the payment step"
    assert state["page"] in {"success", "checkout"}


def test_chaos_policy_hammers_the_primary_control():
    async def scenario():
        browser = MockBrowser(label="test")
        await browser.start()
        await browser.navigate("https://demoshop.local/#/checkout")
        policy = ChaosPolicy()
        observation = await browser.observe()
        duplicates = 0
        for _ in range(6):
            decision = policy.decide(observation, 1)
            if decision.action == "click":
                await browser.click(decision.args["target"])
            elif decision.action == "type_text":
                await browser.type_text(decision.args["target"], decision.args.get("text", ""))
            elif decision.action == "press_key":
                await browser.press_key(decision.args.get("key", "Enter"))
            else:
                break
            observation = await browser.observe()
            duplicates = (await browser.get_state())["duplicate_payments"]
        await browser.close()
        return duplicates

    assert asyncio.run(scenario()) >= 1


def test_technical_policy_probes_search_inputs():
    policy = TechnicalPolicy()
    observation = Observation(
        url="https://x.test/#/home",
        title="Home",
        elements=[],
    )
    # no fields -> it should not crash and should fall back to navigation
    decision = policy.decide(observation, 1)
    assert decision.action in {"click", "go_back", "reload", "finish"}


# ---------------------------------------------------------------------------
# Review AI
# ---------------------------------------------------------------------------
def _discovery(title, agents, url="https://x.test/#/checkout", target="Pay now", tags=("reliability",)):
    from app.agents.base import Discovery

    return Discovery(
        title=title,
        category="reliability",
        severity="high",
        confidence=0.8,
        description="desc",
        agents=list(agents),
        url=url,
        target=target,
        tags=list(tags),
    )


def test_review_deduplicates_and_correlates(tmp_path):
    db = Database(tmp_path / "probe.db")
    bus = EventBus(db)
    evidence = EvidenceStore(db, tmp_path)
    record = db.create_inspection(
        url="https://x.test", depth="quick", focus=["chaos"], goals=[]
    )
    context = AgentContext(
        inspection=record,
        db=db,
        bus=bus,
        evidence=evidence,
        llm=None,
        create_browser=lambda label: MockBrowser(label=label),
        cancel=asyncio.Event(),
    )

    discoveries = [
        _discovery("Repeated action triggers duplicate requests", ["chaos"], tags=("duplicate",)),
        _discovery("Interaction produces no visible feedback", ["ux"], tags=("feedback", "ux")),
        _discovery("Interaction produces no visible feedback", ["technical"], tags=("feedback", "ux")),
        _discovery("Unrelated problem elsewhere", ["technical"], url="https://x.test/#/home", target="Search", tags=("search",)),
    ]
    context.discoveries.extend(discoveries)

    findings = asyncio.run(ReviewAgent().review(context, context.discoveries))

    titles = [finding["title"] for finding in findings]
    assert "Repeated action triggers duplicate requests" in titles
    assert "Unrelated problem elsewhere" in titles

    duplicate = next(f for f in findings if "duplicate" in f["title"])
    assert sorted(duplicate["agents"]) == ["chaos", "technical", "ux"]
    assert duplicate["correlated"] is True
    assert duplicate["contributing_factors"]
    assert duplicate["confidence"] > 0.8  # multi-agent confirmation raises confidence

    db.close()


def test_similarity_helper():
    assert _similarity("Long input overflows the layout", "layout overflow from long input") > 0.2
    assert _similarity("cats", "dogs") == 0.0


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------
def test_gemini_schema_conversion():
    schema = {
        "type": "object",
        "properties": {
            "thought": {"type": "string"},
            "investigate": {"type": "boolean"},
            "args": {"type": "object", "properties": {"seconds": {"type": "number"}}},
        },
        "required": ["thought"],
        "additionalProperties": False,
    }
    converted = to_gemini_schema(schema)
    assert converted["type"] == "OBJECT"
    assert converted["properties"]["thought"]["type"] == "STRING"
    assert converted["properties"]["investigate"]["type"] == "BOOLEAN"
    assert converted["properties"]["args"]["type"] == "OBJECT"
    assert "additionalProperties" not in converted


def test_extract_json_object_from_messy_output():
    assert extract_json_object('noise {"a": 1} tail') == {"a": 1}
    assert extract_json_object('```json\n{"b": 2}\n```') == {"b": 2}
    assert extract_json_object("nothing here") is None


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------
def test_orchestrator_runs_a_full_inspection(tmp_path):
    settings = Settings(
        browser_mode="mock",
        data_dir=tmp_path,
        llm_provider="none",
        agent_step_delay=0.0,
        max_steps_per_agent=8,
    )
    db = Database(settings.database_path)
    bus = EventBus(db)
    evidence = EvidenceStore(db, settings.data_dir)
    orchestrator = Orchestrator(settings, db, bus, evidence)

    record = db.create_inspection(
        url="https://demoshop.local",
        depth="quick",
        focus=["technical", "chaos", "user"],
        goals=[],
    )

    async def run():
        await orchestrator.start(record["id"])
        for _ in range(200):
            current = db.get_inspection(record["id"])
            if current["status"] in {"completed", "failed", "stopped"}:
                break
            await asyncio.sleep(0.1)
        await orchestrator.shutdown()
        return current

    final = asyncio.run(run())
    assert final["status"] == "completed", final["error"]
    findings = db.list_findings(record["id"])
    assert findings, "the planted defects should be discovered"
    assert final["report"]["agent_count"] == 3
    assert evidence.list(record["id"]), "evidence should be collected"
    db.close()
