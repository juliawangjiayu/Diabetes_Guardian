"""
gateway/routers/mental_health.py

Endpoint for receiving emotion labels from the chatbot / MERaLiON inference layer.
All emotion labels are persisted for downstream consumption by Emotion Context MCP.
"""

import structlog
from fastapi import APIRouter

from gateway.schemas import MentalHealthAlert
from gateway.services.persistence import persist_emotion

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/alerts", tags=["mental_health"])


@router.post("/mental-health")
async def receive_mental_health_alert(alert: MentalHealthAlert) -> dict[str, str]:
    """Receive emotion label from chatbot/MERaLiON and persist to user_emotion_log."""
    await persist_emotion(alert)
    logger.info(
        "emotion_logged",
        user_id=alert.user_id,
        emotion_label=alert.emotion_label,
        source=alert.source,
    )
    return {"status": "received"}
