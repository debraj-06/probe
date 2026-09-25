"""WebSocket stream of live inspection events."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/inspections/{inspection_id}")
async def inspection_stream(websocket: WebSocket, inspection_id: str) -> None:
    await websocket.accept()
    services = websocket.app.state.services

    if not services.db.get_inspection(inspection_id):
        await websocket.send_json(
            {"type": "error", "message": f"inspection {inspection_id} not found"}
        )
        await websocket.close()
        return

    # replay history so a refresh (or a late joiner) sees the full story
    for row in services.db.list_events(inspection_id, 0, 500):
        await websocket.send_json(row)

    queue = services.bus.subscribe(inspection_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.to_dict())
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:  # pragma: no cover - shutdown
        pass
    finally:
        services.bus.unsubscribe(inspection_id, queue)
