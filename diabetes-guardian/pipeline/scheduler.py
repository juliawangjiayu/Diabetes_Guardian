"""
pipeline/scheduler.py

Standalone APScheduler process for nightly pipeline execution.
No Celery dependency. Runs as an independent asyncio process.

Start with: python pipeline/run.py
"""

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from pipeline.analytics import run_nightly

logger = structlog.get_logger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_nightly,
        trigger="cron",
        hour=settings.pipeline_schedule_hour,
        minute=settings.pipeline_schedule_minute,
        id="nightly_glucose_profile",
        max_instances=1,
        misfire_grace_time=600,
    )
    return scheduler


async def start() -> None:
    """Start the scheduler and run forever."""
    scheduler = create_scheduler()
    scheduler.start()
    logger.info(
        "pipeline_scheduler_started",
        schedule=f"{settings.pipeline_schedule_hour:02d}:{settings.pipeline_schedule_minute:02d}",
    )

    # Keep the event loop running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("pipeline_scheduler_stopped")
