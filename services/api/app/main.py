"""FastAPI application factory and entrypoint.

Run with::

    uv run uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import router as api_router
from .config import Settings
from .db import Database
from .events import EventBus
from .evidence import EvidenceStore
from .orchestrator import Orchestrator
from .ws import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
logger = logging.getLogger("probe")


@dataclass(slots=True)
class Services:
    """Everything the routes and the orchestrator need."""

    settings: Settings
    db: Database
    bus: EventBus
    evidence: EvidenceStore
    orchestrator: Orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    settings.ensure_dirs()
    db = Database(settings.database_path)
    bus = EventBus(db)
    evidence = EvidenceStore(db, settings.data_dir)
    orchestrator = Orchestrator(settings, db, bus, evidence)
    app.state.services = Services(
        settings=settings, db=db, bus=bus, evidence=evidence, orchestrator=orchestrator
    )
    logger.info(
        "PROBE backend ready — llm=%s browser=%s db=%s",
        settings.llm_provider,
        settings.browser_mode,
        settings.database_path,
    )
    try:
        yield
    finally:
        await orchestrator.shutdown()
        db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="PROBE API",
        description="Autonomous multi-agent web application testing & investigation platform",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    app.include_router(ws_router)

    evidence_root = Path(settings.data_dir)
    evidence_root.mkdir(parents=True, exist_ok=True)
    app.mount("/evidence", StaticFiles(directory=str(evidence_root)), name="evidence")

    @app.get("/", tags=["meta"])
    def root() -> dict[str, Any]:
        return {
            "app": settings.app_name,
            "version": "1.0.0",
            "docs": "/docs",
            "websocket": "/ws/inspections/{inspection_id}",
        }

    return app


app = create_app()
