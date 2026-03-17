"""
agent/state.py

LangGraph AgentState definition.
Fields are only-append: existing field names and types must never be modified.
New fields must be Optional with default None.
"""

from typing import Optional, TypedDict


class AgentState(TypedDict):
    # ── Input (from InvestigationTask) ──────────────────────
    task: dict
    user_id: str

    # ── Investigator fills (pure data fetch, no computation) ─
    location_context: Optional[str]
    glucose_history_24h: Optional[list]
    upcoming_activity: Optional[dict]
    exercise_history: Optional[list]
    user_profile: Optional[dict]
    today_calories_burned: Optional[float]
    emotion_context: Optional[dict]
    glucose_daily_stats: Optional[dict]
    glucose_weekly_profile: Optional[dict]

    # ── Reflector fills (LLM reasoning + drop calculation) ──
    estimated_glucose_drop: Optional[float]
    risk_level: Optional[str]
    reasoning_summary: Optional[str]
    projected_glucose: Optional[float]
    intervention_action: Optional[str]
    supplement_recommendation: Optional[str]
    reflector_confidence: Optional[str]

    # ── Communicator fills ───────────────────────────────────
    message_to_user: Optional[str]
    notification_sent: bool
