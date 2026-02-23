"""
gateway/routers/telemetry.py

POST /telemetry endpoint.
Receives telemetry data, persists it, and evaluates trigger conditions concurrently.
"""

import asyncio

import structlog
from fastapi import APIRouter

from gateway.schemas import TelemetryPayload
from gateway.services.persistence import get_user_age, persist_telemetry
from gateway.services.triage import evaluate_hard_triggers, evaluate_soft_triggers

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/telemetry")
async def receive_telemetry(payload: TelemetryPayload) -> dict[str, str]:
    """
    Receive telemetry data from a user device.

    Flow:
    1. Look up user age from the database
    2. Concurrently persist the record and evaluate triggers
    3. If hard trigger fires, skip soft trigger evaluation
    4. If soft trigger fires, enqueue a Celery task for the Agent
    """
    logger.info(
        "telemetry_received",
        user_id=payload.user_id,
        glucose=payload.glucose,
        heart_rate=payload.heart_rate,
    )

    # Retrieve user age for heart rate threshold calculation
    user_age = await get_user_age(payload.user_id)
    if user_age is None:
        # Default age if user profile is missing
        user_age = 30
        logger.warning(
            "user_age_defaulted",
            user_id=payload.user_id,
            default_age=user_age,
        )

    # Run persistence and hard trigger evaluation concurrently
    _, hard_triggered = await asyncio.gather(
        persist_telemetry(payload),
        evaluate_hard_triggers(payload, user_age),
    )

    # If hard trigger fired, do not evaluate soft triggers
    if hard_triggered:
        return {"status": "received", "trigger": "hard"}

    # Evaluate soft triggers
    investigation_task = await evaluate_soft_triggers(payload, user_age)
    if investigation_task is not None:
        # Enqueue investigation task via Celery
        try:
            from agent.main import celery_app

            celery_app.send_task(
                "agent.tasks.run_investigation",
                args=[investigation_task.model_dump_json()],
            )
            logger.info(
                "investigation_task_enqueued",
                user_id=payload.user_id,
                trigger_type=investigation_task.trigger_type,
            )
        except Exception as exc:
            logger.error(
                "celery_enqueue_failed",
                user_id=payload.user_id,
                error=str(exc),
            )
        return {"status": "received", "trigger": "soft"}

    return {"status": "received"}
