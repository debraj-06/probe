"""Agent tools, action names and the structured decision schema."""

from __future__ import annotations

from typing import Any

#: Every action an agent may take. The automation engine implements each one.
ACTIONS: tuple[str, ...] = (
    "navigate",
    "click",
    "type_text",
    "scroll",
    "press_key",
    "go_back",
    "reload",
    "wait",
    "screenshot",
    "get_dom",
    "get_console_errors",
    "get_network_logs",
    "report_finding",
    "finish",
)

SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low", "info")

CATEGORIES: tuple[str, ...] = (
    "functional",
    "reliability",
    "ux",
    "ui",
    "performance",
    "accessibility",
    "edge-case",
    "data-integrity",
)

#: Aliases models like to invent -> canonical action names.
ACTION_ALIASES: dict[str, str] = {
    "type": "type_text",
    "input": "type_text",
    "fill": "type_text",
    "enter_text": "type_text",
    "tap": "click",
    "press": "click",
    "click_element": "click",
    "open": "navigate",
    "goto": "navigate",
    "visit": "navigate",
    "browser_back": "go_back",
    "back": "go_back",
    "refresh": "reload",
    "sleep": "wait",
    "capture_screenshot": "screenshot",
    "screenshot_page": "screenshot",
    "dom": "get_dom",
    "console": "get_console_errors",
    "network": "get_network_logs",
    "report": "report_finding",
    "report_bug": "report_finding",
    "done": "finish",
    "stop": "finish",
}

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "Your reasoning about what the page shows and what to try next.",
        },
        "action": {
            "type": "string",
            "enum": list(ACTIONS),
            "description": "The single next action to execute.",
        },
        "args": {
            "type": "object",
            "description": "Arguments for the chosen action.",
            "properties": {
                "url": {"type": "string", "description": "Absolute URL for navigate."},
                "target": {
                    "type": "string",
                    "description": "Element id from the element list (e.g. 'e4'), or its visible text.",
                },
                "text": {"type": "string", "description": "Text to type."},
                "direction": {"type": "string", "description": "up or down"},
                "key": {"type": "string", "description": "Key to press, e.g. Enter"},
                "seconds": {"type": "number", "description": "Seconds to wait."},
            },
        },
        "suspicion": {
            "type": "string",
            "description": "Empty string when nothing looks wrong, otherwise what looks suspicious.",
        },
        "investigate": {
            "type": "boolean",
            "description": "True when the previous result should be reproduced and evidenced.",
        },
        "finding": {
            "type": "object",
            "description": "Only fill this in when you already have solid evidence.",
            "properties": {
                "title": {"type": "string"},
                "category": {"type": "string", "enum": list(CATEGORIES)},
                "severity": {"type": "string", "enum": list(SEVERITIES)},
                "confidence": {"type": "number"},
                "description": {"type": "string"},
                "expected": {"type": "string"},
                "actual": {"type": "string"},
                "recommendation": {"type": "string"},
            },
        },
        "finish_reason": {
            "type": "string",
            "description": "Why you are stopping, when action is finish.",
        },
    },
    "required": ["thought", "action"],
}


def agent_tool_definition() -> dict[str, Any]:
    """Single forced tool-call definition used by every provider."""
    return {
        "name": "probe_action",
        "description": (
            "Choose the single next browser action for this autonomous testing agent. "
            "Include a suspicion when something looks wrong so the orchestrator can "
            "investigate and collect evidence."
        ),
        "parameters": DECISION_SCHEMA,
    }


def normalize_action(action: str | None) -> str:
    if not action:
        return "wait"
    cleaned = action.strip().lower().replace("-", "_").replace(" ", "_")
    return ACTION_ALIASES.get(cleaned, cleaned)
