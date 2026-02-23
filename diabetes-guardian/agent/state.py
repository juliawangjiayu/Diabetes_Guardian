"""
agent/state.py

AgentState TypedDict definition for the LangGraph workflow.
Fields are append-only: existing field names and types must not be changed.
New fields must be Optional with default None.
"""

from typing import Optional, TypedDict


class AgentState(TypedDict):
    """Shared state passed through the LangGraph node pipeline."""

    # ── Input (set by Celery task) ───────────────────────────
    task: dict
    user_id: str

    # ── Investigator outputs ─────────────────────────────────
    location_context: Optional[str]
    glucose_history_24h: Optional[list]
    upcoming_activity: Optional[dict]
    recent_exercise_glucose_drops: Optional[list[float]]

    # ── Reflector outputs ────────────────────────────────────
    risk_level: Optional[str]  # "LOW" | "MEDIUM" | "HIGH"
    reasoning_summary: Optional[str]
    intervention_action: Optional[str]  # "NO_ACTION" | "SOFT_REMIND" | "STRONG_ALERT"

    # ── Communicator outputs ─────────────────────────────────
    message_to_user: Optional[str]
    notification_sent: bool
