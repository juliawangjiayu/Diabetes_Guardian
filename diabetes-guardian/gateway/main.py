"""
gateway/main.py

FastAPI application entry point for the Gateway layer (port 8000).
Receives telemetry data from devices, evaluates triggers, and dispatches tasks.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
import structlog
from fastapi import FastAPI

from gateway.routers import crud, telemetry, mental_health
from gateway.routers.telemetry import demo_router

logger = structlog.get_logger(__name__)

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Return the shared httpx client. Raises if not initialized."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    return _http_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _http_client
    _http_client = httpx.AsyncClient(timeout=5.0)
    logger.info("gateway_started")
    yield
    await _http_client.aclose()
    logger.info("gateway_stopped")


app = FastAPI(title="Diabetes Guardian Gateway", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to specific frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router)
app.include_router(mental_health.router)
app.include_router(crud.router)
app.include_router(demo_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
