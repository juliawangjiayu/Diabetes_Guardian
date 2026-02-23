"""
gateway/services/triage.py

Hard trigger and soft trigger evaluation logic.
- evaluate_hard_triggers: critical conditions that fire emergency alerts directly
- evaluate_soft_triggers: sliding window analysis that queues an Agent investigation

Uses constants from gateway/constants.py; no magic numbers allowed.
"""

import asyncio
import collections
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import func, select

from db.models import AsyncSessionLocal, UserTelemetryLog, UserWeeklyPattern
from gateway.constants import (
    ACTIVITY_PROBABILITY_THRESHOLD,
    GLUCOSE_HARD_LOW,
    GLUCOSE_SLOPE_TRIGGER,
    GLUCOSE_SOFT_LOW_MAX,
    GLUCOSE_SOFT_LOW_MIN,
    MAX_HR_RATIO,
    PRE_EXERCISE_WARN_MIN,
    SLIDING_WINDOW_MAX_LEN,
    SLOPE_WINDOW_MIN,
    TELEMETRY_GAP_ALERT_MIN,
)
from gateway.schemas import InvestigationTask, TelemetryPayload
from gateway.services.notification import send_emergency_alert

logger = structlog.get_logger(__name__)

# Sliding window storage keyed by user_id
# Each deque entry: (timestamp, glucose, heart_rate)
_sliding_windows: dict[str, collections.deque] = {}


async def evaluate_hard_triggers(
    payload: TelemetryPayload,
    user_age: int,
) -> bool:
    """
    Evaluate emergency conditions that require immediate notification.

    Returns True if any hard trigger fires, False otherwise.
    Hard triggers bypass the Agent and send alerts directly.
    """
    reasons: list[str] = []

    # Condition 1: critically low glucose
    if payload.glucose < GLUCOSE_HARD_LOW:
        reasons.append(
            f"glucose={payload.glucose} below {GLUCOSE_HARD_LOW} mmol/L"
        )

    # Condition 2: heart rate exceeds age-adjusted maximum
    max_hr = (220 - user_age) * MAX_HR_RATIO
    if payload.heart_rate > max_hr:
        reasons.append(
            f"heart_rate={payload.heart_rate} exceeds max {max_hr:.0f} bpm"
        )

    # Condition 3: telemetry data gap > TELEMETRY_GAP_ALERT_MIN minutes
    try:
        async with AsyncSessionLocal() as session:
            cutoff = payload.timestamp - timedelta(minutes=TELEMETRY_GAP_ALERT_MIN)
            result = await session.execute(
                select(func.count())
                .select_from(UserTelemetryLog)
                .where(
                    UserTelemetryLog.user_id == payload.user_id,
                    UserTelemetryLog.recorded_at >= cutoff,
                )
            )
            recent_count = result.scalar_one()
            if recent_count == 0:
                reasons.append(
                    f"no telemetry in last {TELEMETRY_GAP_ALERT_MIN} minutes"
                )
    except Exception as exc:
        logger.warning(
            "hard_trigger_db_check_failed",
            user_id=payload.user_id,
            error=str(exc),
        )

    if reasons:
        reason_text = "; ".join(reasons)
        logger.info(
            "hard_trigger_fired",
            user_id=payload.user_id,
            reasons=reason_text,
        )
        await send_emergency_alert(payload.user_id, reason_text)
        return True

    return False


async def evaluate_soft_triggers(
    payload: TelemetryPayload,
    user_age: int,
) -> Optional[InvestigationTask]:
    """
    Evaluate soft trigger conditions using a sliding window of recent telemetry.

    Returns an InvestigationTask if a soft trigger condition is met,
    otherwise returns None.
    """
    # Maintain per-user sliding window
    if payload.user_id not in _sliding_windows:
        _sliding_windows[payload.user_id] = collections.deque(
            maxlen=SLIDING_WINDOW_MAX_LEN
        )
    window = _sliding_windows[payload.user_id]
    window.append((payload.timestamp, payload.glucose, payload.heart_rate))

    # Condition 1: glucose decline slope < GLUCOSE_SLOPE_TRIGGER mmol/L/min
    if len(window) >= 3:
        timestamps_sec = [
            (entry[0] - window[0][0]).total_seconds() / 60.0 for entry in window
        ]
        glucose_values = [entry[1] for entry in window]

        if timestamps_sec[-1] > 0:
            slope = float(np.polyfit(timestamps_sec, glucose_values, 1)[0])
            if slope < GLUCOSE_SLOPE_TRIGGER:
                logger.info(
                    "soft_trigger_fired",
                    user_id=payload.user_id,
                    trigger_type="SOFT_GLUCOSE_DECLINE_SLOPE",
                    glucose=payload.glucose,
                    slope=slope,
                )
                return InvestigationTask(
                    user_id=payload.user_id,
                    trigger_type="SOFT_GLUCOSE_DECLINE_SLOPE",
                    trigger_at=payload.timestamp,
                    current_glucose=payload.glucose,
                    current_hr=payload.heart_rate,
                    gps_lat=payload.gps_lat,
                    gps_lng=payload.gps_lng,
                    context_notes=f"Glucose slope={slope:.4f} mmol/L/min",
                )

    # Condition 2: pre-exercise low buffer
    if GLUCOSE_SOFT_LOW_MIN <= payload.glucose <= GLUCOSE_SOFT_LOW_MAX:
        try:
            upcoming = await _check_upcoming_activity(
                payload.user_id, payload.timestamp
            )
            if upcoming is not None:
                logger.info(
                    "soft_trigger_fired",
                    user_id=payload.user_id,
                    trigger_type="SOFT_PRE_EXERCISE_LOW_BUFFER",
                    glucose=payload.glucose,
                    upcoming_activity=upcoming["activity_type"],
                )
                return InvestigationTask(
                    user_id=payload.user_id,
                    trigger_type="SOFT_PRE_EXERCISE_LOW_BUFFER",
                    trigger_at=payload.timestamp,
                    current_glucose=payload.glucose,
                    current_hr=payload.heart_rate,
                    gps_lat=payload.gps_lat,
                    gps_lng=payload.gps_lng,
                    context_notes=(
                        f"Upcoming {upcoming['activity_type']} "
                        f"(probability={upcoming['probability']}, "
                        f"avg_drop={upcoming['avg_glucose_drop']})"
                    ),
                )
        except Exception as exc:
            logger.warning(
                "soft_trigger_activity_check_failed",
                user_id=payload.user_id,
                error=str(exc),
            )

    return None


async def _check_upcoming_activity(
    user_id: str,
    current_time: datetime,
) -> dict | None:
    """
    Query user_weekly_patterns for high-probability activities
    within ±30 minutes of the current time.

    Returns activity dict if found, None otherwise.
    """
    current_dow = current_time.weekday()  # 0=Monday
    current_hour = current_time.hour

    # Check hours within ±30 min range (may span adjacent hours)
    hours_to_check = {current_hour}
    if current_time.minute >= 30:
        hours_to_check.add((current_hour + 1) % 24)
    if current_time.minute <= 30:
        hours_to_check.add((current_hour - 1) % 24)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserWeeklyPattern)
            .where(
                UserWeeklyPattern.user_id == user_id,
                UserWeeklyPattern.day_of_week == current_dow,
                UserWeeklyPattern.hour_of_day.in_(hours_to_check),
                UserWeeklyPattern.probability >= ACTIVITY_PROBABILITY_THRESHOLD,
            )
            .order_by(UserWeeklyPattern.probability.desc())
            .limit(1)
        )
        pattern = result.scalar_one_or_none()

        if pattern is None:
            return None

        # Verify the activity is within PRE_EXERCISE_WARN_MIN minutes
        activity_start = current_time.replace(
            hour=pattern.hour_of_day, minute=0, second=0, microsecond=0
        )
        minutes_until = (activity_start - current_time).total_seconds() / 60.0

        if abs(minutes_until) <= PRE_EXERCISE_WARN_MIN:
            return {
                "activity_type": pattern.activity_type,
                "probability": float(pattern.probability),
                "avg_glucose_drop": float(pattern.avg_glucose_drop or 0),
                "expected_start_hour": pattern.hour_of_day,
            }

    return None
