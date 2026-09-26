"""API schemas (pydantic) — the contract between PROBE and its UI."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

Depth = Literal["quick", "balanced", "deep", "extreme"]

FocusArea = Literal[
    "technical",
    "ux",
    "chaos",
    "user",
    "functional",
    "reliability",
    "performance",
    "accessibility",
    "edge-cases",
]

InspectionStatus = Literal["queued", "running", "completed", "failed", "stopped"]

Severity = Literal["critical", "high", "medium", "low", "info"]

Classification = Literal["confirmed_defect", "ux_issue", "improvement"]


class InspectionCreate(BaseModel):
    url: str = Field(..., description="Website URL to inspect")
    depth: Depth = "balanced"
    focus: list[FocusArea] = Field(default_factory=lambda: ["technical", "ux", "chaos", "user"])
    goals: list[str] = Field(default_factory=list)
    # Consent is explicit and enforced at the API, not just by the UI.
    authorized: bool = False
    # By default the browser blocks write methods and high-impact controls.
    allow_mutations: bool = False
    autostart: bool = True

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        value = (value or "").strip()
        if not value:
            raise ValueError("url is required")
        if "://" not in value:
            value = f"https://{value}"
        try:
            parsed = urlsplit(value)
            # Accessing .port validates malformed/out-of-range ports.
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("url has an invalid host or port") from exc
        if parsed.scheme.lower() not in {"http", "https"}:
            raise ValueError("only http:// and https:// website URLs are supported")
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("url must contain a host and must not include credentials")
        if any(char.isspace() for char in value):
            raise ValueError("url must not contain spaces")
        return value

    @field_validator("goals")
    @classmethod
    def _clean_goals(cls, value: list[str]) -> list[str]:
        return [goal.strip() for goal in value if goal and goal.strip()][:5]


class InspectionOut(BaseModel):
    id: str
    url: str
    depth: str
    focus: list[str]
    goals: list[str]
    authorized: bool = False
    allow_mutations: bool = False
    status: str
    error: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    report: dict[str, Any] | None = None
    finding_count: int = 0
    agent_count: int = 0


class AgentRunOut(BaseModel):
    id: str
    inspection_id: str
    role: str
    status: str
    steps: int
    discoveries: int
    started_at: str | None = None
    finished_at: str | None = None
    summary: str | None = None


class EventOut(BaseModel):
    id: int
    inspection_id: str
    ts: str
    agent: str | None = None
    type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class EvidenceOut(BaseModel):
    id: str
    kind: str
    url: str | None = None
    path: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class FindingOut(BaseModel):
    id: str
    inspection_id: str
    title: str
    category: str
    classification: str
    severity: str
    confidence: float
    description: str
    expected: str | None = None
    actual: str | None = None
    steps: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    agents: list[str] = Field(default_factory=list)
    reproduced: str | None = None
    url: str | None = None
    correlated: bool = False
    created_at: str


class FindingDetailOut(FindingOut):
    correlation_note: str | None = None
    contributing_factors: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceOut] = Field(default_factory=list)


class InspectionDetailOut(InspectionOut):
    agents: list[AgentRunOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)


class ReportOut(BaseModel):
    application: str
    url: str
    inspection: str
    duration: str
    duration_s: float | None = None
    agents: list[dict[str, Any]]
    agent_count: int = 0
    findings: int
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    groups: dict[str, list[str]] = Field(default_factory=dict)
    top_findings: list[dict[str, Any]] = Field(default_factory=list)
    correlated: int = 0
    browser: str = "chromium"
    decision_engine: dict[str, Any] = Field(default_factory=dict)
    complete: bool = True
    warnings: list[str] = Field(default_factory=list)
    failed_agents: list[str] = Field(default_factory=list)
    allow_mutations: bool = False
    generated_at: str | None = None
    summary: str | None = None
    items: list[FindingOut] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: str
    app: str
    llm_provider: str
    llm_model: str
    allow_heuristic_mode: bool = False
    browser_mode: str
    active_inspections: int


class ScreenshotOut(BaseModel):
    url: str | None = None
    created_at: str | None = None
