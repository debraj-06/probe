"""End-to-end API tests: create an inspection and let the agents run."""

from __future__ import annotations

from conftest import wait_for_finish


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["browser_mode"] == "mock"


def test_create_and_run_inspection(client):
    response = client.post(
        "/api/inspections",
        json={
            "url": "https://demoshop.local",
            "authorized": True,
            "depth": "quick",
            "focus": ["technical", "chaos"],
        },
    )
    assert response.status_code == 201, response.text
    inspection = response.json()
    assert inspection["status"] in {"queued", "running"}
    assert inspection["url"] == "https://demoshop.local"

    finished = wait_for_finish(client, inspection["id"])
    assert finished["status"] == "completed", finished.get("error")
    assert finished["agent_count"] == 2
    assert finished["duration_s"] is not None


def test_url_is_normalised(client):
    response = client.post(
        "/api/inspections",
        json={
            "url": "demoshop.local",
            "depth": "quick",
            "authorized": True,
            "allow_mutations": True,
            "autostart": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["url"] == "https://demoshop.local"
    assert response.json()["authorized"] is True
    assert response.json()["allow_mutations"] is True


def test_invalid_url_is_rejected(client):
    response = client.post("/api/inspections", json={"url": "not a url", "autostart": False})
    assert response.status_code == 422


def test_inspection_requires_site_authorization(client):
    response = client.post(
        "/api/inspections",
        json={"url": "https://example.com", "autostart": False},
    )
    assert response.status_code == 403
    assert "permission to test it" in response.json()["detail"]


def test_inspection_requires_configured_llm_unless_heuristics_are_explicitly_allowed(client):
    client.app.state.services.settings.allow_heuristic_mode = False
    response = client.post(
        "/api/inspections",
        json={"url": "https://example.com", "authorized": True, "autostart": False},
    )
    assert response.status_code == 503
    assert "No LLM is configured" in response.json()["detail"]


def test_events_stream_and_findings(client):
    created = client.post(
        "/api/inspections",
        json={"url": "https://demoshop.local", "authorized": True, "depth": "quick", "focus": ["chaos", "technical"]},
    ).json()
    wait_for_finish(client, created["id"])

    events = client.get(f"/api/inspections/{created['id']}/events").json()
    assert events, "expected a stream of events"
    types = {event["type"] for event in events}
    assert "inspection.started" in types
    assert "agent.started" in types
    assert "agent.action" in types
    assert "review.completed" in types
    for event in events:
        if event["type"] == "agent.thinking":
            assert "args" not in event["data"]
            assert "thought" not in event["message"].lower()
        if event["type"] == "agent.action":
            assert "args" not in event["data"]
            assert "detail" not in event["data"]

    findings = client.get(f"/api/inspections/{created['id']}/findings").json()
    assert findings, "the simulator contains deliberate defects"
    for finding in findings:
        assert finding["severity"] in {"critical", "high", "medium", "low", "info"}
        assert 0 < finding["confidence"] <= 1
        assert finding["agents"]

    detail = client.get(f"/api/findings/{findings[0]['id']}").json()
    assert detail["id"] == findings[0]["id"]
    assert isinstance(detail["evidence"], list)


def test_report(client):
    created = client.post(
        "/api/inspections",
        json={"url": "https://demoshop.local", "authorized": True, "depth": "quick", "focus": ["chaos"]},
    ).json()
    wait_for_finish(client, created["id"])

    report = client.get(f"/api/inspections/{created['id']}/report").json()
    assert report["application"] == "demoshop.local"
    assert report["agent_count"] == 1
    assert report["findings"] == len(report["items"])
    assert report["browser"] == "simulator"
    assert report["decision_engine"]["mode"] == "heuristic"
    assert report["complete"] is True
    assert any("did not inspect the live website" in warning for warning in report["warnings"])
    assert any("do not guarantee accuracy" in warning for warning in report["warnings"])
    assert report["high"] + report["medium"] + report["low"] + report["info"] + report[
        "critical"
    ] == report["findings"]


def test_stop_inspection(client):
    created = client.post(
        "/api/inspections",
        json={"url": "https://demoshop.local", "authorized": True, "depth": "extreme", "focus": ["technical"]},
    ).json()
    stopped = client.post(f"/api/inspections/{created['id']}/stop").json()
    assert stopped["stopping"] is True
    wait_for_finish(client, created["id"])
    final = client.get(f"/api/inspections/{created['id']}").json()
    assert final["status"] in {"stopped", "completed"}


def test_unknown_inspection_returns_404(client):
    assert client.get("/api/inspections/nope").status_code == 404
    assert client.get("/api/findings/nope").status_code == 404


def test_websocket_streams_events(client):
    created = client.post(
        "/api/inspections",
        json={"url": "https://demoshop.local", "authorized": True, "depth": "quick", "focus": ["chaos"]},
    ).json()

    with client.websocket_connect(f"/ws/inspections/{created['id']}") as socket:
        seen = []
        for _ in range(500):
            message = socket.receive_json()
            seen.append(message["type"])
            if message["type"] == "inspection.finished":
                break
        assert "inspection.started" in seen
        assert seen[-1] == "inspection.finished"
