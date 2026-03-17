"""
gateway/services/notification.py

Push notification service for both hard triggers and soft triggers.
Uses FCM (Firebase Cloud Messaging) for delivery.
"""

import structlog

from config import settings

logger = structlog.get_logger(__name__)


class NotificationService:
    """Sends push notifications to the user's mobile device via FCM."""

    @staticmethod
    async def send_emergency_push(
        user_id: str,
        reason: str,
        display_label: str,
    ) -> None:
        """
        Send hard-trigger emergency push notification.
        Payload format follows spec — red emergency style on frontend.
        """
        from datetime import datetime

        payload = {
            "notification": {
                "title": f"\u26a0\ufe0f {display_label}",
                "body": "An emergency alert has been triggered. Please check immediately.",
            },
            "data": {
                "type": "hard_trigger",
                "trigger_type": reason,
                "display_label": display_label,
                "user_id": user_id,
                "triggered_at": datetime.now().isoformat(),
            },
        }

        # TODO: Integrate FCM SDK to send actual push notification
        logger.info(
            "emergency_push_sent",
            user_id=user_id,
            trigger_type=reason,
            payload=payload,
        )

    @staticmethod
    async def send_push(
        user_id: str,
        message: str,
        state: dict,
    ) -> None:
        """
        Send soft-trigger push notification with Communicator-generated message.
        Payload format follows spec — blue/orange style depending on intervention level.
        """
        from datetime import datetime

        intervention = state.get("intervention_action", "SOFT_REMIND")

        # Title varies by intervention level
        title = (
            "\u26a0\ufe0f Glucose Alert"
            if intervention == "STRONG_ALERT"
            else "\U0001fa7a Health Check"
        )

        payload = {
            "notification": {
                "title": title,
                "body": message,
            },
            "data": {
                "type": "soft_trigger",
                "trigger_type": state.get("task", {}).get("trigger_type", ""),
                "intervention": intervention,
                "message": message,
                "user_id": user_id,
                "triggered_at": datetime.now().isoformat(),
            },
        }

        # TODO: Integrate FCM SDK to send actual push notification
        logger.info(
            "soft_push_sent",
            user_id=user_id,
            intervention=intervention,
            payload=payload,
        )
