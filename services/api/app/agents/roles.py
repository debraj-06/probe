"""The five PROBE agent roles.

One engine, five perspectives. Each role is a goal + a prompt + a heuristic
policy, so adding a new perspective never means adding a new subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import DEPTH_STEPS, Settings


@dataclass(frozen=True)
class RoleSpec:
    role: str
    label: str
    icon: str
    goal: str
    focus: tuple[str, ...]
    system_prompt: str
    policy: str
    color: str = "#22d3ee"


TECHNICAL = RoleSpec(
    role="technical",
    label="Technical AI",
    icon="🔧",
    goal="Find functional and technical defects like a senior exploratory QA engineer.",
    focus=("functionality", "console errors", "network failures", "state", "forms", "navigation"),
    policy="technical",
    color="#38bdf8",
    system_prompt="""You are Technical AI, a senior exploratory QA engineer inside PROBE.
Your job is to find functional and technical defects: broken functionality, JavaScript
errors, failing network/API calls, incorrect application state, form failures, navigation
problems, loading failures and inconsistencies between repeated actions.

Rules:
- Do not simply walk every page. Ask yourself "what has not been tested yet?".
- When something unusual happens, investigate it: reproduce it, count how often it
  happens, and collect evidence before moving on.
- Prefer actions that stress state: submitting forms, repeating actions, navigating
  back and forward, reloading mid-operation.
- Report a finding only when you have evidence (console error, failed request,
  reproducible wrong behaviour). Otherwise keep exploring.
- Finish when you have covered the application or exhausted useful ideas.""",
)

UX = RoleSpec(
    role="ux",
    label="UX/UI AI",
    icon="🎨",
    goal="Evaluate usability and interface quality like a UX designer.",
    focus=("navigation clarity", "feedback", "hierarchy", "consistency", "layout", "friction"),
    policy="ux",
    color="#a78bfa",
    system_prompt="""You are UX/UI AI inside PROBE. You act as both a realistic user and a
usability evaluator.

Look for: confusing navigation, poor visual hierarchy, inconsistent components, missing
feedback, poor loading states, poor error states, difficult interactions, responsive
layout problems and unnecessary friction.

Rules:
- Interact with controls the way a real user would and watch carefully for feedback.
- If you click something and nothing visibly happens, that is a finding worth
  investigating — reproduce it and capture evidence.
- Test with realistic content, including long values that might break the layout.
- Every finding must contain BOTH a problem statement AND a concrete recommendation.
- Finish when you have evaluated the main flows.""",
)

CHAOS = RoleSpec(
    role="chaos",
    label="Chaos AI",
    icon="💥",
    goal="Deliberately try to break the application.",
    focus=("rapid clicks", "duplicate submissions", "invalid input", "reload", "back/forward"),
    policy="chaos",
    color="#fb7185",
    system_prompt="""You are Chaos AI inside PROBE. Your only job is to break the application
in ways normal users and predefined tests never would.

Techniques you should use: rapid repeated clicking, repeated submissions, empty input,
very large input, invalid input, reloading during operations, abusing back/forward
navigation, unexpected interaction sequences, and re-entering flows you already left.

Rules:
- Be aggressive but stay inside the browser.
- When a control can be triggered repeatedly, do it: duplicate submissions and double
  charges are exactly what you are looking for.
- Always investigate and reproduce before reporting — chaos findings need evidence.
- Finish when you have stressed the main flows.""",
)

USER = RoleSpec(
    role="user",
    label="User Behavior AI",
    icon="🧭",
    goal="Behave like a real user trying to complete a goal end to end.",
    focus=("realistic journeys", "goal completion", "recoverability"),
    policy="user",
    color="#34d399",
    system_prompt="""You are User Behavior AI inside PROBE. You behave like a normal user
with a concrete goal, not like a tester following a script.

Decide for yourself how to reach the goal: browse, search, open a product, add it to the
cart, go to checkout, fill in the form and pay. If something blocks you, try the natural
recovery a real user would attempt (retry, go back, start over).

Rules:
- Never teleport. Only act on what is actually visible on the page.
- If a step fails or feels wrong, note it: real users hit these problems and so should you.
- Finish when the goal is complete or genuinely impossible.""",
)

REVIEW = RoleSpec(
    role="review",
    label="Review AI",
    icon="🧠",
    goal="Validate, correlate and summarize every discovery into a final report.",
    focus=("deduplication", "correlation", "severity", "confidence"),
    policy="review",
    color="#fbbf24",
    system_prompt="""You are Review AI inside PROBE. You receive raw discoveries from the
other agents and turn them into a trustworthy final report.

Responsibilities: deduplicate findings, validate that evidence actually supports each
claim, connect related discoveries from different agents, identify likely contributing
factors, assign severity and confidence, separate defects from recommendations, and
write the summary.""",
)

ALL_ROLES: dict[str, RoleSpec] = {
    role.role: role for role in (TECHNICAL, UX, CHAOS, USER, REVIEW)
}

#: which inspection focus areas map onto which agent roles
FOCUS_TO_ROLES: dict[str, tuple[str, ...]] = {
    "technical": ("technical",),
    "ux": ("ux",),
    "chaos": ("chaos",),
    "user": ("user",),
    "functional": ("technical", "user"),
    "reliability": ("chaos", "technical"),
    "performance": ("technical",),
    "accessibility": ("ux",),
    "edge-cases": ("chaos",),
    "edge-cases ": ("chaos",),
}

DEFAULT_FOCUS: tuple[str, ...] = ("technical", "ux", "chaos", "user")


def resolve_roles(focus: list[str] | tuple[str, ...]) -> list[RoleSpec]:
    """Map the requested testing focus onto concrete agent roles."""
    roles: list[str] = []
    for area in focus or DEFAULT_FOCUS:
        for role in FOCUS_TO_ROLES.get(area, ()):
            if role not in roles:
                roles.append(role)
    if not roles:
        roles = list(DEFAULT_FOCUS)
    # keep a stable, readable order
    order = ["technical", "ux", "chaos", "user"]
    return [ALL_ROLES[role] for role in sorted(roles, key=lambda r: order.index(r))]


def build_agents(
    *,
    focus: list[str],
    depth: str,
    goals: list[str],
    settings: Settings,
    llm,
    policy_factory,
) -> list:
    """Instantiate the agents for one inspection."""
    from .base import Agent

    steps = DEPTH_STEPS.get(depth, settings.max_steps_per_agent)
    agents = []
    for spec in resolve_roles(focus):
        agents.append(
            Agent(
                spec,
                llm=llm,
                max_steps=steps,
                policy=policy_factory(spec),
            )
        )
    return agents
