from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.init_db import init_db


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title="Intelligent Document Processing", version="0.1.0")
    app.include_router(router)
    
    @app.get("/")
    async def root():
        return {
            "message": "Welcome to the Intelligent Document Processing API",
            "docs": "/docs",
            "health": "/health"
        }

    @app.on_event("startup")
    async def _startup() -> None:
        logging.getLogger(__name__).info("startup")
        await init_db()

    return app


app = create_app()
