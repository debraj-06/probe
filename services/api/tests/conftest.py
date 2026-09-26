"""Shared fixtures: a full PROBE app running against the built-in simulator."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TERMINAL = {"completed", "failed", "stopped"}


@pytest.fixture()
def settings(tmp_path):
    return Settings(
        browser_mode="mock",
        data_dir=tmp_path,
        llm_provider="none",
        allow_heuristic_mode=True,
        agent_step_delay=0.0,
        max_steps_per_agent=6,
        slow_action_ms=4000,
    )


@pytest.fixture()
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def wait_for_finish(client: TestClient, inspection_id: str, timeout: float = 60.0) -> dict:
    """Poll an inspection until it reaches a terminal state."""
    deadline = time.time() + timeout
    payload: dict = {}
    while time.time() < deadline:
        response = client.get(f"/api/inspections/{inspection_id}")
        assert response.status_code == 200, response.text
        payload = response.json()
        if payload["status"] in TERMINAL:
            return payload
        time.sleep(0.2)
    raise AssertionError(f"inspection {inspection_id} still {payload.get('status')}")
