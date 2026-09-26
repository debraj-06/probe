"""SQLite persistence for PROBE.

A single connection guarded by a re-entrant lock keeps things simple: FastAPI
sync routes run in a thread pool and the orchestrator wraps every call in
``asyncio.to_thread``, so all access is serialised and safe.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS inspections (
    id           TEXT PRIMARY KEY,
    url          TEXT NOT NULL,
    depth        TEXT NOT NULL DEFAULT 'balanced',
    focus        TEXT NOT NULL DEFAULT '[]',
    goals        TEXT NOT NULL DEFAULT '[]',
    authorized   INTEGER NOT NULL DEFAULT 0,
    allow_mutations INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'queued',
    error        TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT,
    duration_s   REAL,
    report       TEXT
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id             TEXT PRIMARY KEY,
    inspection_id  TEXT NOT NULL,
    role           TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'running',
    steps          INTEGER NOT NULL DEFAULT 0,
    discoveries    INTEGER NOT NULL DEFAULT 0,
    started_at     TEXT,
    finished_at    TEXT,
    summary        TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_inspection ON agent_runs(inspection_id);

CREATE TABLE IF NOT EXISTS events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id  TEXT NOT NULL,
    ts             TEXT NOT NULL,
    agent          TEXT,
    type           TEXT NOT NULL,
    message        TEXT NOT NULL,
    data           TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_inspection ON events(inspection_id, id);

CREATE TABLE IF NOT EXISTS findings (
    id             TEXT PRIMARY KEY,
    inspection_id  TEXT NOT NULL,
    title          TEXT NOT NULL,
    category       TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'confirmed_defect',
    severity       TEXT NOT NULL DEFAULT 'medium',
    confidence     REAL NOT NULL DEFAULT 0.5,
    description    TEXT NOT NULL DEFAULT '',
    expected       TEXT,
    actual         TEXT,
    steps          TEXT NOT NULL DEFAULT '[]',
    recommendation TEXT,
    agents         TEXT NOT NULL DEFAULT '[]',
    reproduced     TEXT,
    url            TEXT,
    correlated     INTEGER NOT NULL DEFAULT 0,
    source         TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_inspection ON findings(inspection_id);

CREATE TABLE IF NOT EXISTS evidence (
    id             TEXT PRIMARY KEY,
    inspection_id  TEXT NOT NULL,
    finding_id     TEXT,
    kind           TEXT NOT NULL,
    path           TEXT,
    url            TEXT,
    meta           TEXT NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_inspection ON evidence(inspection_id);
CREATE INDEX IF NOT EXISTS idx_evidence_finding ON evidence(finding_id);
"""


def utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def dumps(value: Any) -> str:
    return json.dumps(value, default=str)


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class Database:
    """Small typed repository over SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            # Keep existing local databases usable when the inspection schema
            # grows. SQLite has no ``ADD COLUMN IF NOT EXISTS`` on all supported
            # versions, so inspect first and apply only missing columns.
            inspection_columns = {
                row[1] for row in self._conn.execute("PRAGMA table_info(inspections)").fetchall()
            }
            if "authorized" not in inspection_columns:
                self._conn.execute(
                    "ALTER TABLE inspections ADD COLUMN authorized INTEGER NOT NULL DEFAULT 0"
                )
            if "allow_mutations" not in inspection_columns:
                self._conn.execute(
                    "ALTER TABLE inspections ADD COLUMN allow_mutations INTEGER NOT NULL DEFAULT 0"
                )
            self._conn.commit()

    # -- low level --------------------------------------------------------
    def _write(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _read(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- inspections ------------------------------------------------------
    def create_inspection(
        self,
        *,
        url: str,
        depth: str,
        focus: list[str],
        goals: list[str],
        authorized: bool = False,
        allow_mutations: bool = False,
    ) -> dict[str, Any]:
        record = {
            "id": new_id("insp"),
            "url": url,
            "depth": depth,
            "focus": focus,
            "goals": goals,
            "authorized": bool(authorized),
            "allow_mutations": bool(allow_mutations),
            "status": "queued",
            "error": None,
            "created_at": utcnow(),
            "started_at": None,
            "finished_at": None,
            "duration_s": None,
            "report": None,
        }
        self._write(
            """
            INSERT INTO inspections (id, url, depth, focus, goals, authorized, allow_mutations,
                                     status, error, created_at, started_at, finished_at,
                                     duration_s, report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                url,
                depth,
                dumps(focus),
                dumps(goals),
                int(record["authorized"]),
                int(record["allow_mutations"]),
                record["status"],
                None,
                record["created_at"],
                None,
                None,
                None,
                None,
            ),
        )
        return record

    def update_inspection(self, inspection_id: str, **fields: Any) -> None:
        if not fields:
            return
        columns: list[str] = []
        params: list[Any] = []
        for key, value in fields.items():
            columns.append(f"{key} = ?")
            params.append(dumps(value) if isinstance(value, (dict, list)) else value)
        params.append(inspection_id)
        self._write(f"UPDATE inspections SET {', '.join(columns)} WHERE id = ?", tuple(params))

    @staticmethod
    def _row_to_inspection(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "url": row["url"],
            "depth": row["depth"],
            "focus": loads(row["focus"], []),
            "goals": loads(row["goals"], []),
            "authorized": bool(row["authorized"]),
            "allow_mutations": bool(row["allow_mutations"]),
            "status": row["status"],
            "error": row["error"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "duration_s": row["duration_s"],
            "report": loads(row["report"], None),
        }

    def get_inspection(self, inspection_id: str) -> dict[str, Any] | None:
        rows = self._read("SELECT * FROM inspections WHERE id = ?", (inspection_id,))
        return self._row_to_inspection(rows[0]) if rows else None

    def list_inspections(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._read("SELECT * FROM inspections ORDER BY created_at DESC LIMIT ?", (limit,))
        return [self._row_to_inspection(row) for row in rows]

    # -- agent runs -------------------------------------------------------
    def insert_agent_run(self, *, inspection_id: str, role: str) -> str:
        run_id = new_id("run")
        self._write(
            """
            INSERT INTO agent_runs (id, inspection_id, role, status, steps, discoveries,
                                    started_at, finished_at, summary)
            VALUES (?, ?, ?, 'running', 0, 0, ?, NULL, NULL)
            """,
            (run_id, inspection_id, role, utcnow()),
        )
        return run_id

    def update_agent_run(self, run_id: str, **fields: Any) -> None:
        allowed = {"status", "steps", "discoveries", "finished_at", "summary"}
        columns = [f"{key} = ?" for key in fields if key in allowed]
        params = [fields[key] for key in fields if key in allowed]
        if not columns:
            return
        params.append(run_id)
        self._write(f"UPDATE agent_runs SET {', '.join(columns)} WHERE id = ?", tuple(params))

    def list_agent_runs(self, inspection_id: str) -> list[dict[str, Any]]:
        rows = self._read(
            "SELECT * FROM agent_runs WHERE inspection_id = ? ORDER BY started_at ASC",
            (inspection_id,),
        )
        return [dict(row) for row in rows]

    # -- events -----------------------------------------------------------
    def insert_event(
        self,
        *,
        inspection_id: str,
        ts: str,
        agent: str | None,
        type: str,
        message: str,
        data: str,
    ) -> int:
        cur = self._write(
            """
            INSERT INTO events (inspection_id, ts, agent, type, message, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (inspection_id, ts, agent, type, message, data),
        )
        return int(cur.lastrowid or 0)

    def list_events(
        self, inspection_id: str, after_id: int = 0, limit: int = 500
    ) -> list[dict[str, Any]]:
        rows = self._read(
            """
            SELECT * FROM events
            WHERE inspection_id = ? AND id > ?
            ORDER BY id ASC LIMIT ?
            """,
            (inspection_id, after_id, limit),
        )
        return [
            {
                "id": row["id"],
                "inspection_id": row["inspection_id"],
                "ts": row["ts"],
                "agent": row["agent"],
                "type": row["type"],
                "message": row["message"],
                "data": loads(row["data"], {}),
            }
            for row in rows
        ]

    # -- findings ---------------------------------------------------------
    def insert_finding(self, finding: dict[str, Any]) -> str:
        self._write(
            """
            INSERT INTO findings (id, inspection_id, title, category, classification,
                                  severity, confidence, description, expected, actual,
                                  steps, recommendation, agents, reproduced, url,
                                  correlated, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                finding["id"],
                finding["inspection_id"],
                finding["title"],
                finding["category"],
                finding.get("classification", "confirmed_defect"),
                finding["severity"],
                finding["confidence"],
                finding.get("description", ""),
                finding.get("expected"),
                finding.get("actual"),
                dumps(finding.get("steps", [])),
                finding.get("recommendation"),
                dumps(finding.get("agents", [])),
                finding.get("reproduced"),
                finding.get("url"),
                1 if finding.get("correlated") else 0,
                dumps(finding.get("source", {})),
                utcnow(),
            ),
        )
        return finding["id"]

    @staticmethod
    def _row_to_finding(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "inspection_id": row["inspection_id"],
            "title": row["title"],
            "category": row["category"],
            "classification": row["classification"],
            "severity": row["severity"],
            "confidence": row["confidence"],
            "description": row["description"],
            "expected": row["expected"],
            "actual": row["actual"],
            "steps": loads(row["steps"], []),
            "recommendation": row["recommendation"],
            "agents": loads(row["agents"], []),
            "reproduced": row["reproduced"],
            "url": row["url"],
            "correlated": bool(row["correlated"]),
            "source": loads(row["source"], {}),
            "created_at": row["created_at"],
        }

    def get_finding(self, finding_id: str) -> dict[str, Any] | None:
        rows = self._read("SELECT * FROM findings WHERE id = ?", (finding_id,))
        return self._row_to_finding(rows[0]) if rows else None

    def list_findings(self, inspection_id: str) -> list[dict[str, Any]]:
        rows = self._read(
            "SELECT * FROM findings WHERE inspection_id = ? ORDER BY created_at ASC",
            (inspection_id,),
        )
        return [self._row_to_finding(row) for row in rows]

    def count_findings_by_severity(self, inspection_id: str) -> dict[str, int]:
        rows = self._read(
            "SELECT severity, COUNT(*) AS n FROM findings WHERE inspection_id = ? GROUP BY severity",
            (inspection_id,),
        )
        return {row["severity"]: row["n"] for row in rows}

    # -- evidence ---------------------------------------------------------
    def insert_evidence(
        self,
        *,
        evidence_id: str,
        inspection_id: str,
        finding_id: str | None,
        kind: str,
        path: str | None,
        url: str | None,
        meta: dict[str, Any],
    ) -> None:
        self._write(
            """
            INSERT OR REPLACE INTO evidence (id, inspection_id, finding_id, kind, path,
                                             url, meta, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                inspection_id,
                finding_id,
                kind,
                path,
                url,
                dumps(meta),
                utcnow(),
            ),
        )

    def attach_evidence(self, evidence_id: str, finding_id: str) -> None:
        self._write("UPDATE evidence SET finding_id = ? WHERE id = ?", (finding_id, evidence_id))

    def list_evidence(
        self, inspection_id: str, finding_id: str | None = None
    ) -> list[dict[str, Any]]:
        if finding_id:
            rows = self._read(
                "SELECT * FROM evidence WHERE inspection_id = ? AND finding_id = ? ORDER BY created_at ASC",
                (inspection_id, finding_id),
            )
        else:
            rows = self._read(
                "SELECT * FROM evidence WHERE inspection_id = ? ORDER BY created_at ASC",
                (inspection_id,),
            )
        return [
            {
                "id": row["id"],
                "inspection_id": row["inspection_id"],
                "finding_id": row["finding_id"],
                "kind": row["kind"],
                "path": row["path"],
                "url": row["url"],
                "meta": loads(row["meta"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def latest_screenshot(self, inspection_id: str) -> dict[str, Any] | None:
        rows = self._read(
            """
            SELECT * FROM evidence
            WHERE inspection_id = ? AND kind = 'screenshot'
            ORDER BY created_at DESC, id DESC LIMIT 1
            """,
            (inspection_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {"url": row["url"], "path": row["path"], "created_at": row["created_at"]}
