"""
gateway/schemas.py

Pydantic request/response models for all Gateway endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Telemetry ────────────────────────────────────────────────
class CGMPayload(BaseModel):
    user_id: str
    recorded_at: datetime
    glucose: float  # mmol/L


class HRPayload(BaseModel):
    user_id: str
    recorded_at: datetime
    heart_rate: int  # bpm
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None


# ── Exercise (from Apple Watch / Demo Scenario Player) ───────
class ExercisePayload(BaseModel):
    user_id: str
    exercise_type: str  # 'resistance_training', 'cardio', 'hiit'
    started_at: datetime
    ended_at: datetime
    avg_heart_rate: Optional[int] = None
    calories_burned: Optional[float] = None


# ── Mental Health Alert (from chatbot / MERaLiON) ───────────
class MentalHealthAlert(BaseModel):
    user_id: str
    emotion_label: str  # e.g. 'anxious', 'stressed', 'suicidal_ideation'
    source: str = "meralion"
    timestamp: datetime


# ── Agent Task ───────────────────────────────────────────────
class InvestigationTask(BaseModel):
    """Payload pushed to Redis queue to wake up LangGraph agent."""

    user_id: str
    trigger_type: str  # e.g. "SOFT_PRE_EXERCISE_LOW_BUFFER"
    trigger_at: datetime
    current_glucose: float
    current_hr: Optional[int] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    context_notes: str = ""


# ── Data Gap Check (demo only) ──────────────────────────────
class DataGapCheckRequest(BaseModel):
    user_id: str


class DataGapCheckResponse(BaseModel):
    triggered: bool
    last_cgm_at: Optional[str] = None
