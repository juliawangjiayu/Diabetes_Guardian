"""
gateway/services/persistence.py

Write telemetry and emotion data to PostgreSQL.
Each function handles one payload type and commits within its own session.
"""

import structlog
from sqlalchemy.exc import SQLAlchemyError

from db.models import UserCGMLog, UserEmotionLog, UserExerciseLog, UserHRLog
from db.session import AsyncSessionLocal
from gateway.schemas import (
    CGMPayload,
    ExercisePayload,
    HRPayload,
    MentalHealthAlert,
)

logger = structlog.get_logger(__name__)


async def persist_cgm(payload: CGMPayload) -> None:
    """Write a CGM glucose reading to user_cgm_log."""
    try:
        async with AsyncSessionLocal() as session:
            record = UserCGMLog(
                user_id=payload.user_id,
                recorded_at=payload.recorded_at.replace(tzinfo=None),
                glucose=payload.glucose,
            )
            session.add(record)
            await session.commit()
    except SQLAlchemyError as e:
        logger.error("persist_cgm_failed", user_id=payload.user_id, error=str(e))
        raise


async def persist_hr(payload: HRPayload) -> None:
    """Write a heart rate reading to user_hr_log."""
    try:
        async with AsyncSessionLocal() as session:
            record = UserHRLog(
                user_id=payload.user_id,
                recorded_at=payload.recorded_at.replace(tzinfo=None),
                heart_rate=payload.heart_rate,
                gps_lat=payload.gps_lat,
                gps_lng=payload.gps_lng,
            )
            session.add(record)
            await session.commit()
    except SQLAlchemyError as e:
        logger.error("persist_hr_failed", user_id=payload.user_id, error=str(e))
        raise


async def persist_exercise(payload: ExercisePayload) -> None:
    """Write an exercise session to user_exercise_log."""
    try:
        async with AsyncSessionLocal() as session:
            record = UserExerciseLog(
                user_id=payload.user_id,
                exercise_type=payload.exercise_type,
                started_at=payload.started_at.replace(tzinfo=None),
                ended_at=payload.ended_at.replace(tzinfo=None),
                avg_heart_rate=payload.avg_heart_rate,
                calories_burned=payload.calories_burned,
            )
            session.add(record)
            await session.commit()
    except SQLAlchemyError as e:
        logger.error("persist_exercise_failed", user_id=payload.user_id, error=str(e))
        raise


async def persist_emotion(alert: MentalHealthAlert) -> None:
    """Write an emotion label to user_emotion_log."""
    try:
        async with AsyncSessionLocal() as session:
            record = UserEmotionLog(
                user_id=alert.user_id,
                recorded_at=alert.timestamp.replace(tzinfo=None),
                user_input="",  # raw text not available from this endpoint
                emotion_label=alert.emotion_label,
                source=alert.source,
            )
            session.add(record)
            await session.commit()
    except SQLAlchemyError as e:
        logger.error("persist_emotion_failed", user_id=alert.user_id, error=str(e))
        raise
