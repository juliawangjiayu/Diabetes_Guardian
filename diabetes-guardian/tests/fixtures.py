"""
tests/fixtures.py

Shared test data and helper functions for constructing test payloads.
All tests must use these fixtures instead of hardcoding test values.
"""

from datetime import datetime

from gateway.schemas import InvestigationTask, TelemetryPayload


def build_telemetry(
    user_id: str = "user_001",
    timestamp: datetime | None = None,
    heart_rate: int = 75,
    glucose: float = 5.5,
    gps_lat: float = 39.9042,
    gps_lng: float = 116.4074,
) -> TelemetryPayload:
    """Build a TelemetryPayload with sensible defaults for testing."""
    return TelemetryPayload(
        user_id=user_id,
        timestamp=timestamp or datetime(2024, 6, 15, 13, 30, 0),
        heart_rate=heart_rate,
        glucose=glucose,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )


def build_investigation_task(
    user_id: str = "user_001",
    trigger_type: str = "SOFT_PRE_EXERCISE_LOW_BUFFER",
    glucose: float = 4.8,
    heart_rate: int = 75,
) -> InvestigationTask:
    """Build an InvestigationTask with sensible defaults for testing."""
    return InvestigationTask(
        user_id=user_id,
        trigger_type=trigger_type,
        trigger_at=datetime(2024, 6, 15, 13, 30, 0),
        current_glucose=glucose,
        current_hr=heart_rate,
        gps_lat=39.9042,
        gps_lng=116.4074,
        context_notes="Test investigation task",
    )


def build_initial_state(
    user_id: str = "user_001",
    trigger_type: str = "SOFT_PRE_EXERCISE_LOW_BUFFER",
    glucose: float = 4.8,
    heart_rate: int = 75,
) -> dict:
    """Build an initial AgentState dict for LangGraph testing."""
    return {
        "task": {
            "user_id": user_id,
            "trigger_type": trigger_type,
            "trigger_at": "2024-06-15T13:30:00",
            "current_glucose": glucose,
            "current_hr": heart_rate,
            "gps_lat": 39.9042,
            "gps_lng": 116.4074,
            "context_notes": "Test state",
        },
        "user_id": user_id,
        "location_context": None,
        "glucose_history_24h": None,
        "upcoming_activity": None,
        "recent_exercise_glucose_drops": None,
        "risk_level": None,
        "reasoning_summary": None,
        "intervention_action": None,
        "message_to_user": None,
        "notification_sent": False,
    }


# ── Test user profile ───────────────────────────────────────

TEST_USER_BIRTH_YEAR: int = 1990
TEST_USER_AGE: int = 34
