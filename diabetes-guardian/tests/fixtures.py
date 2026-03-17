"""
tests/fixtures.py

Shared test fixtures for all test modules.
"""

from datetime import datetime, time, timedelta


def make_cgm_payload(
    user_id: str = "user_001",
    glucose: float = 5.5,
    recorded_at: datetime | None = None,
) -> dict:
    return {
        "user_id": user_id,
        "recorded_at": (recorded_at or datetime.now()).isoformat(),
        "glucose": glucose,
    }


def make_hr_payload(
    user_id: str = "user_001",
    heart_rate: int = 75,
    recorded_at: datetime | None = None,
    gps_lat: float = 1.3521,
    gps_lng: float = 103.8198,
) -> dict:
    return {
        "user_id": user_id,
        "recorded_at": (recorded_at or datetime.now()).isoformat(),
        "heart_rate": heart_rate,
        "gps_lat": gps_lat,
        "gps_lng": gps_lng,
    }


def make_exercise_payload(
    user_id: str = "user_001",
    exercise_type: str = "resistance_training",
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> dict:
    start = started_at or datetime.now()
    end = ended_at or (start + timedelta(hours=1, minutes=30))
    return {
        "user_id": user_id,
        "exercise_type": exercise_type,
        "started_at": start.isoformat(),
        "ended_at": end.isoformat(),
        "avg_heart_rate": 145,
        "calories_burned": 420.0,
    }


def make_mental_health_alert(
    user_id: str = "user_001",
    emotion_label: str = "anxious",
) -> dict:
    return {
        "user_id": user_id,
        "emotion_label": emotion_label,
        "source": "meralion",
        "timestamp": datetime.now().isoformat(),
    }


# Demo user profile
DEMO_USER = {
    "user_id": "user_001",
    "name": "Demo User",
    "birth_year": 1990,
    "gender": "male",
    "weight_kg": 78.0,
    "height_cm": 175.0,
    "waist_cm": 85.0,
}

# Weekly pattern for Saturday resistance training at 14:00
DEMO_WEEKLY_PATTERN = {
    "user_id": "user_001",
    "day_of_week": 5,  # Saturday
    "start_time": time(14, 0),
    "end_time": time(15, 30),
    "activity_type": "resistance_training",
}
