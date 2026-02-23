"""
gateway/schemas.py

Pydantic data models for the gateway layer.
- TelemetryPayload: incoming telemetry data from user devices
- InvestigationTask: message body pushed to Celery queue to invoke the LangGraph Agent
"""

from datetime import datetime

from pydantic import BaseModel


class TelemetryPayload(BaseModel):
    """Incoming telemetry data from a user's wearable device."""

    user_id: str
    timestamp: datetime
    heart_rate: int
    glucose: float  # mmol/L
    gps_lat: float
    gps_lng: float


class InvestigationTask(BaseModel):
    """Task payload pushed to Celery queue to trigger the LangGraph Agent."""

    user_id: str
    trigger_type: str  # e.g. "SOFT_PRE_EXERCISE_LOW_BUFFER"
    trigger_at: datetime
    current_glucose: float
    current_hr: int
    gps_lat: float
    gps_lng: float
    context_notes: str
