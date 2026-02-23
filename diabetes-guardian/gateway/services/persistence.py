"""
gateway/services/persistence.py

Persists incoming telemetry records to the MySQL database.
Uses SQLAlchemy 2.0 async sessions.
"""

import structlog
from sqlalchemy import select

from db.models import AsyncSessionLocal, User, UserTelemetryLog
from gateway.schemas import TelemetryPayload

logger = structlog.get_logger(__name__)


async def persist_telemetry(payload: TelemetryPayload) -> None:
    """Insert a telemetry record into user_telemetry_log."""
    try:
        async with AsyncSessionLocal() as session:
            record = UserTelemetryLog(
                user_id=payload.user_id,
                recorded_at=payload.timestamp,
                heart_rate=payload.heart_rate,
                glucose=payload.glucose,
                gps_lat=payload.gps_lat,
                gps_lng=payload.gps_lng,
            )
            session.add(record)
            await session.commit()
            logger.info(
                "telemetry_persisted",
                user_id=payload.user_id,
                recorded_at=str(payload.timestamp),
            )
    except Exception as exc:
        logger.error(
            "telemetry_persist_failed",
            user_id=payload.user_id,
            error=str(exc),
        )
        raise


async def get_user_age(user_id: str) -> int | None:
    """Retrieve the user's age from the users table based on birth_year."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User.birth_year).where(User.user_id == user_id)
            )
            birth_year = result.scalar_one_or_none()
            if birth_year is None:
                logger.warning("user_birth_year_missing", user_id=user_id)
                return None
            from datetime import datetime

            return datetime.now().year - birth_year
    except Exception as exc:
        logger.error(
            "user_age_query_failed",
            user_id=user_id,
            error=str(exc),
        )
        return None
