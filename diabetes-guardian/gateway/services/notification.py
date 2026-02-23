"""
gateway/services/notification.py

Push notification service for emergency alerts and agent-generated messages.
Currently implements a stub for FCM/APNs integration.
"""

import structlog

from config import settings

logger = structlog.get_logger(__name__)


async def send_emergency_alert(user_id: str, reason: str) -> None:
    """
    Send an emergency push notification to the user.

    Called by hard triggers when immediate user attention is required.
    In production, this would integrate with FCM or APNs.
    """
    logger.info(
        "emergency_alert_sent",
        user_id=user_id,
        reason=reason,
        fcm_key_present=bool(settings.fcm_server_key),
    )
    # TODO: Integrate with FCM/APNs using settings.fcm_server_key


async def send_push(user_id: str, message: str) -> None:
    """
    Send a non-emergency push notification to the user.

    Called by the Communicator node after the agent generates a personalized message.
    In production, this would integrate with FCM or APNs.
    """
    logger.info(
        "push_notification_sent",
        user_id=user_id,
        message_length=len(message),
        fcm_key_present=bool(settings.fcm_server_key),
    )
    # TODO: Integrate with FCM/APNs using settings.fcm_server_key
