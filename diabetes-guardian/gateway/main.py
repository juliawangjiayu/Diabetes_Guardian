"""
gateway/main.py

FastAPI application entry point for the Gateway service.
Initializes the httpx client lifecycle and registers routers.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI

from gateway.routers.telemetry import router as telemetry_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: startup and shutdown."""
    logger.info("gateway_starting", port=8000)
    yield
    logger.info("gateway_shutting_down")


app = FastAPI(
    title="Diabetes Guardian Gateway",
    description="Telemetry ingestion and trigger evaluation service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(telemetry_router)
