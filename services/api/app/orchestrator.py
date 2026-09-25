"""The PROBE orchestrator: owns the lifecycle of one inspection."""

from __future__ import annotations

import asyncio
import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from .agents.base import SEVERITY_ORDER, Agent, AgentContext
from .agents.policy import create_policy
from .agents.review import ReviewAgent
from .agents.roles import build_agents
from .browser.base import BrowserController
from .browser.controller import PlaywrightController
from .browser.mock import MockBrowser
from .config import Settings
from .db import Database, new_id, utcnow
from .events import EventBus
from .evidence import EvidenceStore
from .llm import create_llm

logger = logging.getLogger("probe.orchestrator")

SEVERITY_LEVELS = ("critical", "high", "medium", "low", "info")


class BrowserPool:
    """Creates one browser per agent and cleans everything up afterwards.

    ``auto`` mode tries real Chromium first and transparently falls back to the
    built-in simulator, so PROBE always runs even where no browser is installed.
    """

    def __init__(self, settings: Settings, inspection_id: str) -> None:
        self.settings = settings
        self.inspection_id = inspection_id
        self._playwright_ok = settings.browser_mode in {"auto", "playwright"}
        self._pw = None
        self._controllers: list[BrowserController] = []
        self._video_dir = Path(settings.data_dir) / "inspections" / inspection_id / "videos"
        self.fell_back = False

    async def create(self, label: str) -> BrowserController:
        if self._playwright_ok:
            try:
                if self._pw is None:
                    from playwright.async_api import async_playwright

                    self._pw = await async_playwright().start()
                controller = PlaywrightController(
                    label=label,
                    headless=self.settings.headless,
                    viewport={
                        "width": self.settings.viewport_width,
                        "height": self.settings.viewport_height,
                    },
                    record_video=self.settings.record_video,
                    video_dir=self._video_dir,
                    playwright=self._pw,
                )
                await controller.start()
                self._controllers.append(controller)
                return controller
            except Exception as exc:  # noqa: BLE001 - degrade to the simulator
                logger.warning("Playwright unavailable (%s); using the simulator", exc)
                self._playwright_ok = False
                self.fell_back = True
                self._pw = None
        controller = MockBrowser(label=label, latency=self.settings.mock_latency)
        self._controllers.append(controller)
        # reached either because mock was requested outright or because
        # Playwright degraded — in both cases the report must not claim a real
        # browser was used
        self.fell_back = True
        return controller

    @property
    def controllers(self) -> list[BrowserController]:
        return list(self._controllers)

    async def close(self) -> None:
        for controller in self._controllers:
            try:
                await controller.close()
            except Exception:  # noqa: BLE001
                pass
        if self._pw is not None:
            try:
                await self._pw.stop()
            except Exception:  # noqa: BLE001
                pass


class Orchestrator:
    """Runs inspections end to end and keeps them cancellable."""

    def __init__(self, settings: Settings, db: Database, bus: EventBus, evidence: EvidenceStore) -> None:
        self.settings = settings
        self.db = db
        self.bus = bus
        self.evidence = evidence
        self.llm = create_llm(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout,
            retries=settings.llm_retries,
            max_tokens=settings.llm_max_tokens,
        )
        self._tasks: dict[str, asyncio.Task] = {}
        self._cancels: dict[str, threading.Event] = {}

    # ------------------------------------------------------------------
    async def start(self, inspection_id: str) -> None:
        if inspection_id in self._tasks and not self._tasks[inspection_id].done():
            return
        cancel = threading.Event()
        self._cancels[inspection_id] = cancel
        task = asyncio.create_task(self._run(inspection_id, cancel), name=f"probe-{inspection_id}")
        self._tasks[inspection_id] = task

    def stop(self, inspection_id: str) -> bool:
        """Signal a running inspection to stop at the next safe point."""
        cancel = self._cancels.get(inspection_id)
        if cancel is None:
            return False
        cancel.set()
        return True

    def active(self) -> list[str]:
        return [i for i, task in self._tasks.items() if not task.done()]

    async def shutdown(self) -> None:
        for cancel in self._cancels.values():
            cancel.set()
        for task in list(self._tasks.values()):
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=10)
            except BaseException:  # noqa: BLE001 - shutdown must not raise
                task.cancel()
        if self.llm is not None:
            await self.llm.aclose()

    # ------------------------------------------------------------------
    async def _run(self, inspection_id: str, cancel: asyncio.Event) -> None:
        started = time.perf_counter()
        inspection = await asyncio.to_thread(self.db.get_inspection, inspection_id)
        if inspection is None:
            logger.error("inspection %s vanished", inspection_id)
            return

        await asyncio.to_thread(
            self.db.update_inspection,
            inspection_id,
            status="running",
            started_at=utcnow(),
        )
        await self.bus.emit(
            inspection_id,
            "inspection.started",
            f"Inspection started for {inspection['url']} "
            f"({inspection['depth']} depth, focus: {', '.join(inspection['focus'])})",
            data={
                "url": inspection["url"],
                "depth": inspection["depth"],
                "focus": inspection["focus"],
            },
        )

        pool = BrowserPool(self.settings, inspection_id)
        agents: list[Agent] = build_agents(
            focus=inspection["focus"],
            depth=inspection["depth"],
            goals=inspection["goals"],
            settings=self.settings,
            llm=self.llm,
            policy_factory=lambda spec: create_policy(spec.role, goals=inspection["goals"]),
        )
        agent_names = ", ".join(agent.spec.label for agent in agents)
        await self.bus.emit(
            inspection_id,
            "agents.assigned",
            f"{len(agents)} agent(s) assigned: {agent_names}",
            data={
                "agents": [a.spec.role for a in agents],
                "llm": bool(self.llm),
                "llm_provider": self.settings.llm_provider,
            },
        )

        context = AgentContext(
            inspection=inspection,
            db=self.db,
            bus=self.bus,
            evidence=self.evidence,
            llm=self.llm,
            create_browser=pool.create,
            cancel=cancel,
            slow_ms=self.settings.slow_action_ms,
            agent_delay=self.settings.agent_step_delay,
            reproduce_attempts=self.settings.reproduce_attempts,
            max_investigations=self.settings.max_investigations_per_agent,
        )

        status = "completed"
        error: str | None = None
        findings: list[dict[str, Any]] = []

        try:
            if cancel.is_set():
                raise asyncio.CancelledError()

            results = await asyncio.gather(
                *(agent.run(context) for agent in agents), return_exceptions=True
            )
            for result in results:
                if isinstance(result, Exception):
                    logger.exception("agent failed", exc_info=result)

            if cancel.is_set():
                status = "stopped"
            else:
                review = ReviewAgent(self.llm)
                findings = await review.review(context, context.discoveries)
                await self._persist_findings(inspection_id, findings)
                report = self._build_report(
                    inspection=inspection,
                    findings=findings,
                    agents=agents,
                    started=started,
                    fell_back=pool.fell_back,
                )
                await asyncio.to_thread(self.db.update_inspection, inspection_id, report=report)
        except asyncio.CancelledError:
            status = "stopped"
        except Exception as exc:  # noqa: BLE001 - never leave the UI hanging
            status = "failed"
            error = f"{type(exc).__name__}: {exc}"
            logger.exception("inspection %s failed", inspection_id)
        finally:
            await pool.close()
            await self._save_videos(inspection_id, pool)

        duration = time.perf_counter() - started
        await asyncio.to_thread(
            self.db.update_inspection,
            inspection_id,
            status=status,
            error=error,
            finished_at=utcnow(),
            duration_s=round(duration, 2),
        )
        await self.bus.emit(
            inspection_id,
            "inspection.finished",
            f"Inspection {status} in {duration:.1f}s — {len(findings)} finding(s)",
            data={
                "status": status,
                "duration_s": round(duration, 2),
                "findings": len(findings),
                "error": error,
            },
        )
        self._cancels.pop(inspection_id, None)

    # ------------------------------------------------------------------
    async def _persist_findings(self, inspection_id: str, findings: list[dict[str, Any]]) -> None:
        for finding in findings:
            finding["inspection_id"] = inspection_id
            await asyncio.to_thread(self.db.insert_finding, finding)
            for item in finding.get("source", {}).get("evidence", []):
                evidence_id = item.get("id")
                if evidence_id:
                    self.evidence.attach(evidence_id, finding["id"])

    async def _save_videos(self, inspection_id: str, pool: BrowserPool) -> None:
        if not self.settings.record_video:
            return
        target_dir = Path(self.settings.data_dir) / "inspections" / inspection_id / "videos"
        for controller in pool.controllers:
            video = getattr(controller, "video_path", None)
            if not video:
                continue
            source = Path(video)
            if not source.exists():
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            destination = target_dir / f"{controller.label}-{source.name}"
            try:
                shutil.copyfile(source, destination)
            except OSError:  # noqa: BLE001
                continue
            self.db.insert_evidence(
                evidence_id=new_id("ev"),
                inspection_id=inspection_id,
                finding_id=None,
                kind="video",
                path=str(destination),
                url=f"/evidence/inspections/{inspection_id}/videos/{destination.name}",
                meta={"agent": controller.label},
            )

    # ------------------------------------------------------------------
    @staticmethod
    def _build_report(
        *,
        inspection: dict[str, Any],
        findings: list[dict[str, Any]],
        agents: list[Agent],
        started: float,
        fell_back: bool,
    ) -> dict[str, Any]:
        duration = time.perf_counter() - started
        counts = {level: 0 for level in SEVERITY_LEVELS}
        for finding in findings:
            counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1

        by_category: dict[str, int] = {}
        for finding in findings:
            by_category[finding["category"]] = by_category.get(finding["category"], 0) + 1

        groups: dict[str, list[str]] = {}
        for finding in findings:
            groups.setdefault(finding["category"], []).append(finding["id"])

        # a compact digest so the dashboard can show findings without a second call
        ordered = sorted(
            findings,
            key=lambda f: (SEVERITY_ORDER.get(f["severity"], 3), -f["confidence"]),
        )
        top_findings = [
            {
                "id": f["id"],
                "title": f["title"],
                "severity": f["severity"],
                "category": f["category"],
                "classification": f["classification"],
                "confidence": f["confidence"],
                "correlated": f["correlated"],
                "agents": f["agents"],
            }
            for f in ordered
        ]

        host = inspection["url"].split("//")[-1].split("/")[0]
        minutes, seconds = divmod(int(duration), 60)

        return {
            "application": host or inspection["url"],
            "url": inspection["url"],
            "inspection": inspection["depth"],
            "duration": f"{minutes}m {seconds:02d}s",
            "duration_s": round(duration, 2),
            "agents": [
                {
                    "role": agent.spec.role,
                    "label": agent.spec.label,
                    "goal": agent.spec.goal,
                    "discoveries": len(agent.discoveries),
                }
                for agent in agents
            ],
            "agent_count": len(agents),
            "findings": len(findings),
            **counts,
            "by_category": by_category,
            "groups": groups,
            "top_findings": top_findings,
            "correlated": sum(1 for f in findings if f.get("correlated")),
            "browser": "simulator" if fell_back else "chromium",
            "generated_at": utcnow(),
        }
