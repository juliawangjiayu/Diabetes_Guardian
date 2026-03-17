"""
gateway/services/call_service.py

Twilio voice call service for emergency contacts.
Places automated TTS voice calls to each emergency contact.
"""

import structlog
from twilio.rest import Client

from config import settings

logger = structlog.get_logger(__name__)


def call_contacts(contacts: list[dict], user_id: str, reason: str) -> None:
    """
    Place automated voice calls to each emergency contact via Twilio.
    This is a synchronous function — call via asyncio.to_thread from async code.
    """
    reason_text = {
        "hard_low_glucose": "a critically low blood glucose alert",
        "hard_high_hr": "a dangerously high heart rate alert",
        "data_gap": "a CGM data gap alert — no readings for over 1 hour",
    }.get(reason, "a health alert")

    twiml = f"""
    <Response>
      <Say voice="Polly.Joanna">
        Hello, this is an automated message from the Diabetes Guardian system.
        User {user_id} has triggered {reason_text}.
        Please check on them immediately.
      </Say>
    </Response>
    """

    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("twilio_not_configured", user_id=user_id)
        return

    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        for contact in contacts:
            client.calls.create(
                to=contact["phone_number"],
                from_=settings.twilio_from_number,
                twiml=twiml,
            )
            logger.info(
                "call_placed",
                user_id=user_id,
                contact=contact["contact_name"],
            )
    except Exception as e:
        logger.error("twilio_call_failed", user_id=user_id, error=str(e))
