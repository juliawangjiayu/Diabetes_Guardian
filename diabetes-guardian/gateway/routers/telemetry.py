"""
gateway/routers/telemetry.py

HTTP endpoints for CGM, heart rate, exercise telemetry, and demo data-gap check.
Each endpoint persists data then evaluates triggers concurrently.
"""

import asyncio

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select

from config import settings
from db.models import (
    InterventionLog,
    User,
    UserCGMLog,
    UserExerciseLog,
    UserHRLog,
)
from db.session import AsyncSessionLocal
from gateway.schemas import (
    CGMPayload,
    DataGapCheckRequest,
    DataGapCheckResponse,
    ExercisePayload,
    HRPayload,
)
from gateway.services.persistence import (
    persist_cgm,
    persist_exercise,
    persist_hr,
)
from gateway.services.triage import evaluate_hard_triggers, evaluate_soft_triggers

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/cgm")
async def receive_cgm(payload: CGMPayload) -> dict[str, str]:
    """Receive CGM glucose reading, persist and evaluate triggers."""
    await persist_cgm(payload)

    hard_fired, soft_task = await asyncio.gather(
        evaluate_hard_triggers(
            user_id=payload.user_id,
            glucose=payload.glucose,
        ),
        evaluate_soft_triggers(
            user_id=payload.user_id,
            glucose=payload.glucose,
            payload_recorded_at=payload.recorded_at.replace(tzinfo=None),
        ),
    )

    logger.info(
        "cgm_processed",
        user_id=payload.user_id,
        glucose=payload.glucose,
        hard_fired=hard_fired,
        soft_task=soft_task is not None,
    )
    return {"status": "received"}


@router.post("/hr")
async def receive_hr(payload: HRPayload) -> dict[str, str]:
    """Receive heart rate reading, persist and evaluate hard triggers."""
    await persist_hr(payload)

    # Look up user age for HR threshold calculation
    age: int | None = None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.birth_year).where(User.user_id == payload.user_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            from datetime import datetime

            age = datetime.now().year - row

    hard_fired = await evaluate_hard_triggers(
        user_id=payload.user_id,
        heart_rate=payload.heart_rate,
        age=age,
    )

    logger.info(
        "hr_processed",
        user_id=payload.user_id,
        heart_rate=payload.heart_rate,
        hard_fired=hard_fired,
    )
    return {"status": "received"}


@router.post("/exercise")
async def receive_exercise(payload: ExercisePayload) -> dict[str, str]:
    """Receive exercise session data. Pure persistence, no trigger logic."""
    await persist_exercise(payload)
    logger.info(
        "exercise_logged",
        user_id=payload.user_id,
        exercise_type=payload.exercise_type,
    )
    return {"status": "received"}


# ── Demo-only endpoint ──────────────────────────────────────

demo_router = APIRouter(prefix="/test", tags=["demo"])


@demo_router.post("/check-data-gap", response_model=DataGapCheckResponse)
async def check_data_gap(body: DataGapCheckRequest) -> DataGapCheckResponse:
    """
    Manually check whether a user has a CGM data gap (>60 min).
    Only available when DEMO_MODE=true.
    """
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    from gateway.services.triage import check_data_gap_trigger

    triggered, last_cgm_at = await check_data_gap_trigger(body.user_id)
    return DataGapCheckResponse(
        triggered=triggered,
        last_cgm_at=last_cgm_at.isoformat() if last_cgm_at else None,
    )


class ResetTodayRequest(BaseModel):
    user_id: str = "user_001"


@demo_router.post("/reset-today")
async def reset_today(body: ResetTodayRequest) -> dict:
    """
    Delete all of today's test data for a user (CGM, HR, Exercise, Intervention logs)
    and clear the in-memory glucose sliding window.
    Only available when DEMO_MODE=true.
    """
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="Demo mode is not enabled")

    from datetime import datetime, time as dt_time
    from gateway.services.triage import _glucose_windows

    today_start = datetime.combine(datetime.now().date(), dt_time(0, 0))
    user_id = body.user_id
    deleted = {}

    async with AsyncSessionLocal() as session:
        # CGM log
        result = await session.execute(
            delete(UserCGMLog).where(
                UserCGMLog.user_id == user_id,
                UserCGMLog.recorded_at >= today_start,
            )
        )
        deleted["user_cgm_log"] = result.rowcount

        # HR log
        result = await session.execute(
            delete(UserHRLog).where(
                UserHRLog.user_id == user_id,
                UserHRLog.recorded_at >= today_start,
            )
        )
        deleted["user_hr_log"] = result.rowcount

        # Exercise log
        result = await session.execute(
            delete(UserExerciseLog).where(
                UserExerciseLog.user_id == user_id,
                UserExerciseLog.started_at >= today_start,
            )
        )
        deleted["user_exercise_log"] = result.rowcount

        # Intervention log
        result = await session.execute(
            delete(InterventionLog).where(
                InterventionLog.user_id == user_id,
                InterventionLog.triggered_at >= today_start,
            )
        )
        deleted["intervention_log"] = result.rowcount

        await session.commit()

    # Clear in-memory glucose sliding window
    if user_id in _glucose_windows:
        _glucose_windows[user_id].clear()

    total = sum(deleted.values())
    logger.info("reset_today_completed", user_id=user_id, deleted=deleted, total=total)

    return {"status": "ok", "user_id": user_id, "deleted": deleted, "total_deleted": total}

