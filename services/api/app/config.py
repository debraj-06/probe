"""Central configuration for the PROBE backend.

Everything is environment driven (prefix ``PROBE_``) so the same image can run
in "demo mode" (heuristic policies, simulated browser) or "real mode"
(LLM decisions, real Chromium) without code changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

BrowserMode = Literal["auto", "playwright", "mock"]
LLMProvider = Literal["none", "openai", "anthropic", "gemini", "openai-compatible"]

#: How many observe -> decide -> act cycles an agent gets per depth preset.
DEPTH_STEPS: dict[str, int] = {
    "quick": 8,
    "balanced": 16,
    "deep": 28,
    "extreme": 45,
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROBE_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- identity ---------------------------------------------------------
    app_name: str = "PROBE"
    environment: str = "development"

    # -- server -----------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
        ]
    )

    # -- storage ----------------------------------------------------------
    data_dir: Path = Path("data")

    # -- LLM --------------------------------------------------------------
    llm_provider: LLMProvider = "none"
    # Permit explicit offline policy runs only when an operator opts in.
    allow_heuristic_mode: bool = False
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2048
    llm_timeout: float = 60.0
    llm_retries: int = 2

    # -- browser ----------------------------------------------------------
    # Real Chromium is the default. The simulator is available only when it is
    # explicitly requested (e.g. for the DemoShop and CI tests).
    browser_mode: BrowserMode = "playwright"
    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 800
    record_video: bool = False
    mock_latency: float = 1.2

    # -- agents -----------------------------------------------------------
    max_steps_per_agent: int = 20
    agent_step_delay: float = 0.15
    slow_action_ms: int = 2500
    reproduce_attempts: int = 3
    max_investigations_per_agent: int = 4
    dom_excerpt_chars: int = 6000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def database_path(self) -> Path:
        return self.data_dir / "probe.db"

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none"

    def steps_for_depth(self, depth: str) -> int:
        return DEPTH_STEPS.get(depth, self.max_steps_per_agent)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
