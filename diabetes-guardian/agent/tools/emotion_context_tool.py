"""
agent/tools/emotion_context_tool.py

Emotion Context Tool.
Queries the most recent emotion label within the staleness window (default 2h).
Returns null if no record found.
"""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select

from config import settings
from db.models import UserEmotionLog
from db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


async def get_emotion_context(user_id: str) -> dict | None:
    """
    Return the most recent emotion label within EMOTION_STALENESS_HOURS.
    Returns null (None → JSON null) if no record found.
    """
    cutoff = datetime.now() - timedelta(hours=settings.emotion_staleness_hours)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserEmotionLog)
            .where(
                UserEmotionLog.user_id == user_id,
                UserEmotionLog.recorded_at >= cutoff,
            )
            .order_by(UserEmotionLog.recorded_at.desc())
            .limit(1)
        )
        record = result.scalar_one_or_none()

    if record is None:
        return None

    return {
        "emotion_label": record.emotion_label,
        "recorded_at": record.recorded_at.isoformat(),
        "source": record.source,
    }
