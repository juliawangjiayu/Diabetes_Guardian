"""
gateway/services/emergency.py

EmergencyService: orchestrates hard-trigger emergency response.
- Sends emergency push notification to user
- Sends SMS to emergency contacts
- Places automated voice call to emergency contacts
- Writes intervention_log record
"""

import asyncio
from datetime import datetime

import structlog
from sqlalchemy import select

from db.models import InterventionLog, UserEmergencyContact
from db.session import AsyncSessionLocal
from gateway.constants import DISPLAY_LABELS
from gateway.services.call_service import call_contacts
from gateway.services.notification import NotificationService

logger = structlog.get_logger(__name__)


class EmergencyService:
    """Handles all hard-trigger emergency actions concurrently."""

    @staticmethod
    async def fire(user_id: str, reason: str) -> None:
        """
        Execute emergency response for a hard trigger.
        All actions run concurrently via asyncio.gather.
        """
        display_label = DISPLAY_LABELS.get(reason, reason)

        # Fetch emergency contacts configured for this trigger type
        contacts = await _get_emergency_contacts(user_id, reason)

        # Run all emergency actions concurrently
        await asyncio.gather(
            NotificationService.send_emergency_push(user_id, reason, display_label),
            _notify_contacts(contacts, user_id, reason),
            _log_intervention(user_id, reason, display_label),
        )

        logger.info(
            "emergency_fired",
            user_id=user_id,
            trigger_type=reason,
            display_label=display_label,
            contacts_notified=len(contacts),
        )


async def _get_emergency_contacts(user_id: str, reason: str) -> list[dict]:
    """Fetch emergency contacts whose notify_on includes the given reason."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserEmergencyContact).where(
                UserEmergencyContact.user_id == user_id
            )
        )
        contacts_all = result.scalars().all()

    # Filter contacts that have this reason in their notify_on list
    contacts = []
    for c in contacts_all:
        notify_list = c.notify_on if isinstance(c.notify_on, list) else []
        if reason in notify_list:
            contacts.append({
                "contact_name": c.contact_name,
                "phone_number": c.phone_number,
                "relationship": c.relationship,
            })
    return contacts


async def _notify_contacts(
    contacts: list[dict],
    user_id: str,
    reason: str,
) -> None:
    """Send SMS and voice calls to all emergency contacts."""
    if not contacts:
        logger.warning("no_emergency_contacts", user_id=user_id, trigger_type=reason)
        return

    # Call contacts via Twilio (runs in thread pool to avoid blocking)
    try:
        await asyncio.to_thread(call_contacts, contacts, user_id, reason)
    except Exception as e:
        logger.error("call_contacts_failed", user_id=user_id, error=str(e))


async def _log_intervention(
    user_id: str,
    reason: str,
    display_label: str,
) -> None:
    """Write hard trigger intervention to intervention_log."""
    async with AsyncSessionLocal() as session:
        record = InterventionLog(
            user_id=user_id,
            triggered_at=datetime.now(),
            trigger_type=reason,
            display_label=display_label,
            agent_decision=None,
            message_sent=None,
        )
        session.add(record)
        await session.commit()
