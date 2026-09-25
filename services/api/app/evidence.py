"""Evidence collection: screenshots, console/network dumps, action timelines."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .browser.base import BrowserController
from .db import Database, new_id, utcnow


@dataclass(slots=True)
class EvidenceRef:
    id: str
    kind: str
    path: str
    url: str
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "url": self.url,
            "meta": self.meta,
        }


class EvidenceStore:
    """Writes evidence to the local filesystem and indexes it in SQLite."""

    def __init__(self, db: Database, data_dir: Path) -> None:
        self.db = db
        self.root = Path(data_dir)

    # -- paths ------------------------------------------------------------
    def inspection_dir(self, inspection_id: str) -> Path:
        return self.root / "inspections" / inspection_id

    def _public_url(self, inspection_id: str, relative: str) -> str:
        return f"/evidence/inspections/{inspection_id}/{relative}"

    # -- writers ----------------------------------------------------------
    async def save_screenshot(
        self,
        *,
        inspection_id: str,
        browser: BrowserController,
        name: str,
        agent: str | None = None,
        full_page: bool = False,
        finding_id: str | None = None,
        extra_meta: dict[str, Any] | None = None,
    ) -> EvidenceRef | None:
        try:
            directory = self.inspection_dir(inspection_id) / "screens"
            stem = directory / f"{name}-{int(time.time() * 1000)}"
            path = await browser.screenshot(stem, full_page=full_page)
        except Exception:  # noqa: BLE001 - evidence is best effort
            return None
        relative = f"screens/{path.name}"
        meta = {"name": name, "agent": agent, "full_page": full_page}
        meta.update(extra_meta or {})
        return self._record(
            inspection_id=inspection_id,
            finding_id=finding_id,
            kind="screenshot",
            path=path,
            relative=relative,
            meta=meta,
        )

    async def save_json(
        self,
        *,
        inspection_id: str,
        name: str,
        payload: Any,
        kind: str = "data",
        agent: str | None = None,
        finding_id: str | None = None,
    ) -> EvidenceRef | None:
        directory = self.inspection_dir(inspection_id) / "data"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{name}-{int(time.time() * 1000)}.json"
        try:
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        except Exception:  # noqa: BLE001
            return None
        relative = f"data/{path.name}"
        return self._record(
            inspection_id=inspection_id,
            finding_id=finding_id,
            kind=kind,
            path=path,
            relative=relative,
            meta={"name": name, "agent": agent},
        )

    def _record(
        self,
        *,
        inspection_id: str,
        finding_id: str | None,
        kind: str,
        path: Path,
        relative: str,
        meta: dict[str, Any],
    ) -> EvidenceRef:
        evidence_id = new_id("ev")
        url = self._public_url(inspection_id, relative)
        self.db.insert_evidence(
            evidence_id=evidence_id,
            inspection_id=inspection_id,
            finding_id=finding_id,
            kind=kind,
            path=str(path),
            url=url,
            meta=meta,
        )
        return EvidenceRef(id=evidence_id, kind=kind, path=str(path), url=url, meta=meta)

    # -- readers ----------------------------------------------------------
    def list(self, inspection_id: str, finding_id: str | None = None) -> list[dict[str, Any]]:
        return self.db.list_evidence(inspection_id, finding_id)

    def latest_screenshot(self, inspection_id: str) -> dict[str, Any] | None:
        return self.db.latest_screenshot(inspection_id)

    def attach(self, evidence_id: str, finding_id: str) -> None:
        self.db.attach_evidence(evidence_id, finding_id)


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return "—"
    minutes, secs = divmod(int(seconds), 60)
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def now_ts() -> str:
    return utcnow()
