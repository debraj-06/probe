"""REST API for PROBE."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..schemas import (
    AgentRunOut,
    EventOut,
    FindingDetailOut,
    FindingOut,
    HealthOut,
    InspectionCreate,
    InspectionDetailOut,
    InspectionOut,
    ReportOut,
    ScreenshotOut,
)

router = APIRouter(prefix="/api", tags=["probe"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def services(request: Request) -> Any:
    return request.app.state.services


def _inspection_out(record: dict[str, Any], db) -> InspectionOut:
    findings = db.list_findings(record["id"])
    agents = db.list_agent_runs(record["id"])
    fields = {key: record[key] for key in InspectionOut.model_fields if key in record}
    return InspectionOut(**fields, finding_count=len(findings), agent_count=len(agents))


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------
@router.get("/health", response_model=HealthOut)
def health(request: Request) -> HealthOut:
    svc = services(request)
    settings = svc.settings
    return HealthOut(
        status="ok",
        app=settings.app_name,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model or ("—" if not settings.llm_enabled else "default"),
        browser_mode=settings.browser_mode,
        active_inspections=len(svc.orchestrator.active()),
    )


# ---------------------------------------------------------------------------
# inspections
# ---------------------------------------------------------------------------
@router.post("/inspections", response_model=InspectionOut, status_code=201)
async def create_inspection(payload: InspectionCreate, request: Request) -> InspectionOut:
    svc = services(request)
    record = await asyncio.to_thread(
        svc.db.create_inspection,
        url=payload.url,
        depth=payload.depth,
        focus=list(payload.focus),
        goals=list(payload.goals),
    )
    await svc.bus.emit(
        record["id"],
        "inspection.created",
        f"Inspection queued for {payload.url}",
        data={"url": payload.url, "depth": payload.depth, "focus": list(payload.focus)},
    )
    if payload.autostart:
        await svc.orchestrator.start(record["id"])
    return _inspection_out(record, svc.db)


@router.get("/inspections", response_model=list[InspectionOut])
def list_inspections(request: Request, limit: int = 50) -> list[InspectionOut]:
    svc = services(request)
    records = svc.db.list_inspections(limit=min(max(limit, 1), 200))
    return [_inspection_out(record, svc.db) for record in records]


@router.get("/inspections/{inspection_id}", response_model=InspectionDetailOut)
def get_inspection(request: Request, inspection_id: str) -> InspectionDetailOut:
    svc = services(request)
    record = svc.db.get_inspection(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="inspection not found")
    agents = [AgentRunOut(**run) for run in svc.db.list_agent_runs(inspection_id)]
    findings = [FindingOut(**f) for f in svc.db.list_findings(inspection_id)]
    events = [EventOut(**e) for e in svc.db.list_events(inspection_id, 0, 200)]
    base = _inspection_out(record, svc.db)
    return InspectionDetailOut(**base.model_dump(), agents=agents, findings=findings, events=events)


@router.post("/inspections/{inspection_id}/stop")
def stop_inspection(request: Request, inspection_id: str) -> dict[str, Any]:
    svc = services(request)
    record = svc.db.get_inspection(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="inspection not found")
    stopped = svc.orchestrator.stop(inspection_id)
    return {"id": inspection_id, "stopping": stopped, "status": record["status"]}


@router.post("/inspections/{inspection_id}/restart")
async def restart_inspection(request: Request, inspection_id: str) -> dict[str, Any]:
    svc = services(request)
    record = svc.db.get_inspection(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="inspection not found")
    await svc.orchestrator.start(inspection_id)
    return {"id": inspection_id, "restarted": True}


@router.get("/inspections/{inspection_id}/events", response_model=list[EventOut])
def inspection_events(
    request: Request, inspection_id: str, after_id: int = 0, limit: int = 500
) -> list[EventOut]:
    svc = services(request)
    if not svc.db.get_inspection(inspection_id):
        raise HTTPException(status_code=404, detail="inspection not found")
    rows = svc.db.list_events(inspection_id, after_id, min(max(limit, 1), 2000))
    return [EventOut(**row) for row in rows]


@router.get("/inspections/{inspection_id}/findings", response_model=list[FindingOut])
def inspection_findings(request: Request, inspection_id: str) -> list[FindingOut]:
    svc = services(request)
    if not svc.db.get_inspection(inspection_id):
        raise HTTPException(status_code=404, detail="inspection not found")
    return [FindingOut(**f) for f in svc.db.list_findings(inspection_id)]


@router.get("/inspections/{inspection_id}/report", response_model=ReportOut)
def inspection_report(request: Request, inspection_id: str) -> ReportOut:
    svc = services(request)
    record = svc.db.get_inspection(inspection_id)
    if not record:
        raise HTTPException(status_code=404, detail="inspection not found")
    findings = svc.db.list_findings(inspection_id)
    report = record.get("report") or {}
    summary = next(
        (f.get("source", {}).get("report_summary") for f in findings if f.get("source")),
        None,
    )
    return ReportOut(**{**report, "items": [FindingOut(**f) for f in findings]}, summary=summary)


@router.get("/inspections/{inspection_id}/screenshot/latest", response_model=ScreenshotOut)
def latest_screenshot(request: Request, inspection_id: str) -> ScreenshotOut:
    svc = services(request)
    if not svc.db.get_inspection(inspection_id):
        raise HTTPException(status_code=404, detail="inspection not found")
    shot = svc.evidence.latest_screenshot(inspection_id)
    if not shot:
        return ScreenshotOut()
    return ScreenshotOut(url=shot["url"], created_at=shot["created_at"])


@router.get("/inspections/{inspection_id}/evidence")
def inspection_evidence(request: Request, inspection_id: str) -> list[dict[str, Any]]:
    svc = services(request)
    if not svc.db.get_inspection(inspection_id):
        raise HTTPException(status_code=404, detail="inspection not found")
    return svc.evidence.list(inspection_id)


# ---------------------------------------------------------------------------
# findings
# ---------------------------------------------------------------------------
@router.get("/findings/{finding_id}", response_model=FindingDetailOut)
def get_finding(request: Request, finding_id: str) -> FindingDetailOut:
    svc = services(request)
    finding = svc.db.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="finding not found")
    evidence = [
        {
            "id": e["id"],
            "kind": e["kind"],
            "url": e["url"],
            "path": e["path"],
            "meta": e["meta"],
            "created_at": e["created_at"],
        }
        for e in svc.evidence.list(finding["inspection_id"], finding_id)
    ]
    source = finding.pop("source", None) or {}
    return FindingDetailOut(
        **finding,
        correlation_note=source.get("correlation_note"),
        contributing_factors=source.get("contributing_factors", []),
        source=source,
        evidence=evidence,
    )


@router.get("/findings/{finding_id}/screenshot")
def finding_screenshot(request: Request, finding_id: str) -> FileResponse:
    svc = services(request)
    finding = svc.db.get_finding(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="finding not found")
    for item in svc.evidence.list(finding["inspection_id"], finding_id):
        if item["kind"] == "screenshot" and item["path"]:
            return FileResponse(item["path"])
    raise HTTPException(status_code=404, detail="no screenshot for this finding")
