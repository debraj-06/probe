"""Event bus: persists every event and fans it out to WebSocket subscribers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from .db import Database, utcnow


@dataclass(slots=True)
class ProbeEvent:
    id: int | None
    inspection_id: str
    ts: str
    agent: str | None
    type: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "inspection_id": self.inspection_id,
            "ts": self.ts,
            "agent": self.agent,
            "type": self.type,
            "message": self.message,
            "data": self.data,
        }


class EventBus:
    """One bus per process; subscribers are per inspection."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._subscribers: dict[str, set[asyncio.Queue]] = {}

    async def emit(
        self,
        inspection_id: str,
        type: str,
        message: str,
        *,
        agent: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> ProbeEvent:
        payload = data or {}
        ts = utcnow()
        event_id = await asyncio.to_thread(
            self._db.insert_event,
            inspection_id=inspection_id,
            ts=ts,
            agent=agent,
            type=type,
            message=message,
            data=__import__("json").dumps(payload, default=str),
        )
        event = ProbeEvent(
            id=event_id,
            inspection_id=inspection_id,
            ts=ts,
            agent=agent,
            type=type,
            message=message,
            data=payload,
        )
        for queue in tuple(self._subscribers.get(inspection_id, ())):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:  # pragma: no cover - defensive
                pass
        return event

    def subscribe(self, inspection_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subscribers.setdefault(inspection_id, set()).add(queue)
        return queue

    def unsubscribe(self, inspection_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(inspection_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(inspection_id, None)

    def history(self, inspection_id: str, after_id: int = 0, limit: int = 500) -> list[dict[str, Any]]:
        return self._db.list_events(inspection_id, after_id, limit)
