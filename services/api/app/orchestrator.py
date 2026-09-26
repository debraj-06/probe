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

    A live website is never silently replaced by the DemoShop simulator. The
    simulator is selected only with ``PROBE_BROWSER_MODE=mock``; otherwise a
    missing Chromium installation fails the inspection visibly.
    """

    def __init__(
        self,
        settings: Settings,
        inspection_id: str,
        *,
        allow_mutations: bool = False,
    ) -> None:
        self.settings = settings
        self.inspection_id = inspection_id
        self.allow_mutations = allow_mutations
        self._pw = None
        self._controllers: list[BrowserController] = []
        self._video_dir = Path(settings.data_dir) / "inspections" / inspection_id / "videos"
        self.fell_back = settings.browser_mode == "mock"

    async def create(self, label: str) -> BrowserController:
        if self.settings.browser_mode == "mock":
            controller = MockBrowser(label=label, latency=self.settings.mock_latency)
            self._controllers.append(controller)
            return controller

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
                allow_mutations=self.allow_mutations,
            )
            await controller.start()
            self._controllers.append(controller)
            return controller
        except Exception as exc:  # noqa: BLE001 - fail closed; never fabricate a result
            logger.exception("Real Chromium could not be started for agent %s", label)
            raise RuntimeError(
                "Real Chromium could not start. Install it with "
                "`uv run --project services/api playwright install chromium` and retry. "
                "No simulator fallback was used."
            ) from exc

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

        pool = BrowserPool(
            self.settings,
            inspection_id,
            allow_mutations=bool(inspection.get("allow_mutations", False)),
        )
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
            failed_roles: list[str] = []
            for agent, result in zip(agents, results, strict=True):
                if isinstance(result, BaseException):
                    logger.error("agent %s escaped with an error: %r", agent.spec.role, result)
                    failed_roles.append(agent.spec.label)
                elif result.get("status") == "failed":
                    failed_roles.append(agent.spec.label)

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
                    complete=not failed_roles,
                    failed_roles=failed_roles,
                    model_info=(
                        {**self.llm.info(), "provider": self.settings.llm_provider}
                        if self.llm is not None
                        else None
                    ),
                    allow_mutations=bool(inspection.get("allow_mutations", False)),
                )
                await asyncio.to_thread(self.db.update_inspection, inspection_id, report=report)
                if failed_roles:
                    status = "failed"
                    error = (
                        "Some inspection agents could not complete, so this report is partial: "
                        + ", ".join(failed_roles)
                    )
        except asyncio.CancelledError:
            status = "stopped"
        except Exception:  # noqa: BLE001 - never leave the UI hanging
            status = "failed"
            error = "The inspection could not be completed. Check the server logs and engine configuration."
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
        complete: bool = True,
        failed_roles: list[str] | None = None,
        model_info: dict[str, str] | None = None,
        allow_mutations: bool = False,
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
        warnings: list[str] = [
            "Findings reflect only the pages and flows exercised; evidence and confidence do not guarantee accuracy or full site coverage. Verify important results independently."
        ]
        if fell_back:
            warnings.append("Simulator mode was used; this run did not inspect the live website.")
        if model_info is None:
            warnings.append("No LLM is configured; deterministic policies drove the agents.")
        if not allow_mutations:
            warnings.append(
                "Read-only protection was enabled: write requests and high-impact controls may be blocked."
            )
        else:
            warnings.append(
                "Mutation testing was enabled and may have changed or created data on the target site."
            )
        if failed_roles:
            warnings.append("The report is partial because one or more agents did not finish.")

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
            "decision_engine": (
                {"mode": "llm", **(model_info or {})}
                if model_info
                else {"mode": "heuristic", "provider": "none", "model": ""}
            ),
            "complete": complete,
            "warnings": warnings,
            "failed_agents": failed_roles or [],
            "allow_mutations": allow_mutations,
            "generated_at": utcnow(),
        }
