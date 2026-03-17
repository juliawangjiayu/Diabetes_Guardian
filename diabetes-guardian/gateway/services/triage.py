"""
gateway/services/triage.py

Hard trigger and soft trigger evaluation logic.
- evaluate_hard_triggers: critically dangerous conditions -> immediate emergency response
- evaluate_soft_triggers: sliding window analysis -> enqueue Agent investigation task
- check_data_gap_trigger: demo-only data gap detection
"""

import asyncio
import collections
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import structlog
from celery import Celery
from sqlalchemy import func, select

from config import settings
from db.models import UserCGMLog, UserHRLog, UserWeeklyPattern
from db.session import AsyncSessionLocal
from gateway.constants import (
    GLUCOSE_HARD_LOW,
    GLUCOSE_SLOPE_TRIGGER,
    GLUCOSE_SOFT_LOW_MAX,
    GLUCOSE_SOFT_LOW_MIN,
    MAX_HR_RATIO,
    PRE_EXERCISE_WARN_MIN,
    SLOPE_WINDOW_MIN,
    TELEMETRY_GAP_ALERT_MIN,
)
from gateway.schemas import InvestigationTask
from gateway.services.emergency import EmergencyService

logger = structlog.get_logger(__name__)

celery_app = Celery("diabetes_guardian", broker=settings.redis_url)

# Sliding window: per-user deque of (recorded_at, glucose) tuples, max 20 entries
_glucose_windows: dict[str, collections.deque] = {}
_WINDOW_MAX_SIZE = 20


async def evaluate_hard_triggers(
    user_id: str,
    glucose: float | None = None,
    heart_rate: int | None = None,
    age: int | None = None,
) -> bool:
    """
    Evaluate hard trigger conditions. Any match fires emergency response immediately.
    Returns True if a hard trigger was fired.
    """
    # Check low glucose
    if glucose is not None and glucose < GLUCOSE_HARD_LOW:
        logger.warning("hard_trigger_fired", user_id=user_id, trigger_type="hard_low_glucose", glucose=glucose)
        await EmergencyService.fire(user_id, "hard_low_glucose")
        return True

    # Check high heart rate
    if heart_rate is not None and age is not None:
        max_hr = (220 - age) * MAX_HR_RATIO
        if heart_rate > max_hr:
            logger.warning(
                "hard_trigger_fired",
                user_id=user_id,
                trigger_type="hard_high_hr",
                heart_rate=heart_rate,
                max_hr=max_hr,
            )
            await EmergencyService.fire(user_id, "hard_high_hr")
            return True

    return False


async def evaluate_soft_triggers(
    user_id: str,
    glucose: float,
    payload_recorded_at: datetime,
) -> Optional[InvestigationTask]:
    """
    Evaluate soft trigger conditions using a sliding window of recent CGM data.
    Returns an InvestigationTask if a soft trigger fires, otherwise None.
    """
    reference_time = payload_recorded_at if settings.demo_mode else datetime.now()

    # Maintain sliding window
    if user_id not in _glucose_windows:
        _glucose_windows[user_id] = collections.deque(maxlen=_WINDOW_MAX_SIZE)
    window = _glucose_windows[user_id]
    window.append((payload_recorded_at, glucose))

    # Prune entries older than SLOPE_WINDOW_MIN
    cutoff = reference_time - timedelta(minutes=SLOPE_WINDOW_MIN)
    while window and window[0][0] < cutoff:
        window.popleft()

    trigger_type: str | None = None
    context_notes = ""

    # --- Soft trigger 1: Pre-exercise low buffer (higher specificity) ---
    in_buffer_zone = GLUCOSE_SOFT_LOW_MIN <= glucose <= GLUCOSE_SOFT_LOW_MAX
    logger.info(
        "pre_exercise_check",
        glucose=glucose,
        in_buffer_zone=in_buffer_zone,
        range_min=GLUCOSE_SOFT_LOW_MIN,
        range_max=GLUCOSE_SOFT_LOW_MAX,
    )
    if in_buffer_zone:
        upcoming = await _find_upcoming_activity(user_id, reference_time)
        logger.info("upcoming_activity_result", upcoming=upcoming, reference_time=str(reference_time))
        if upcoming is not None:
            trigger_type = "SOFT_PRE_EXERCISE_LOW_BUFFER"
            context_notes = (
                f"Glucose {glucose} in pre-exercise buffer zone; "
                f"upcoming {upcoming['activity_type']} at {upcoming['start_time']}"
            )
            logger.info(
                "soft_trigger_fired",
                user_id=user_id,
                trigger_type=trigger_type,
                glucose=glucose,
            )

    # --- Soft trigger 2: Glucose slope (fallback if pre-exercise didn't fire) ---
    if trigger_type is None and len(window) >= 3:
        timestamps = [(t - window[0][0]).total_seconds() / 60.0 for t, _ in window]
        values = [v for _, v in window]
        
        logger.info("slope_calc_input", timestamps=timestamps, values=values)
        
        slope = float(np.polyfit(timestamps, values, 1)[0])
        
        logger.info("slope_calc_result", calculated_slope=slope, trigger_threshold=0.11)

        if abs(slope) > GLUCOSE_SLOPE_TRIGGER:
            direction = "falling" if slope < 0 else "rising"
            trigger_type = "SOFT_RAPID_SLOPE"
            context_notes = f"Glucose {direction} at {slope:.3f} mmol/L/min"
            logger.info(
                "soft_trigger_fired",
                user_id=user_id,
                trigger_type=trigger_type,
                slope=slope,
            )
    elif trigger_type is None:
        logger.info("slope_skipped", window_size=len(window), required=3)

    if trigger_type is None:
        logger.info("no_soft_trigger", user_id=user_id, glucose=glucose)
        return None

    # Fetch last known GPS from HR log
    gps_lat, gps_lng = await _get_last_gps(user_id)

    task = InvestigationTask(
        user_id=user_id,
        trigger_type=trigger_type,
        trigger_at=reference_time,
        current_glucose=glucose,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        context_notes=context_notes,
    )

    # Enqueue to Celery via Redis
    celery_app.send_task(
        "agent.tasks.run_investigation",
        args=[task.model_dump_json()],
    )
    logger.info("investigation_enqueued", user_id=user_id, trigger_type=trigger_type)

    return task


async def check_data_gap_trigger(
    user_id: str,
) -> tuple[bool, datetime | None]:
    """
    Check if user has no CGM data in the last TELEMETRY_GAP_ALERT_MIN minutes.
    Returns (triggered, last_cgm_at).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.max(UserCGMLog.recorded_at)).where(
                UserCGMLog.user_id == user_id
            )
        )
        last_cgm_at = result.scalar_one_or_none()

    if last_cgm_at is None:
        await EmergencyService.fire(user_id, "data_gap")
        return True, None

    gap_minutes = (datetime.now() - last_cgm_at).total_seconds() / 60
    if gap_minutes >= TELEMETRY_GAP_ALERT_MIN:
        await EmergencyService.fire(user_id, "data_gap")
        return True, last_cgm_at

    return False, last_cgm_at


async def _find_upcoming_activity(
    user_id: str,
    reference_time: datetime,
) -> dict | None:
    """
    Check user_weekly_patterns for an activity starting within PRE_EXERCISE_WARN_MIN
    of reference_time. Returns activity dict or None.
    """
    day_of_week = reference_time.weekday()  # 0=Monday
    current_time = reference_time.time()
    warn_limit = (reference_time + timedelta(minutes=PRE_EXERCISE_WARN_MIN)).time()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserWeeklyPattern).where(
                UserWeeklyPattern.user_id == user_id,
                UserWeeklyPattern.day_of_week == day_of_week,
                UserWeeklyPattern.start_time >= current_time,
                UserWeeklyPattern.start_time <= warn_limit,
            )
        )
        pattern = result.scalars().first()

    if pattern is None:
        return None

    start_dt = datetime.combine(reference_time.date(), pattern.start_time)
    end_dt = datetime.combine(reference_time.date(), pattern.end_time)
    duration_min = int((end_dt - start_dt).total_seconds() / 60)

    return {
        "activity_type": pattern.activity_type,
        "start_time": pattern.start_time.strftime("%H:%M"),
        "end_time": pattern.end_time.strftime("%H:%M"),
        "duration_min": duration_min,
    }


async def _get_last_gps(user_id: str) -> tuple[float | None, float | None]:
    """Fetch last known GPS from user_hr_log."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserHRLog.gps_lat, UserHRLog.gps_lng)
            .where(UserHRLog.user_id == user_id)
            .order_by(UserHRLog.recorded_at.desc())
            .limit(1)
        )
        row = result.first()

    if row is None:
        return None, None
    return float(row.gps_lat) if row.gps_lat else None, float(row.gps_lng) if row.gps_lng else None
