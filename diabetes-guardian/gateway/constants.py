"""
gateway/constants.py

All medical thresholds and domain constants.
No magic numbers in business code — always reference this module.
"""

# Blood glucose thresholds (mmol/L)
GLUCOSE_HARD_LOW: float = 3.9
GLUCOSE_SOFT_LOW_MIN: float = 4.0
GLUCOSE_SOFT_LOW_MAX: float = 5.6
GLUCOSE_EXERCISE_SAFE_MIN: float = 5.6
GLUCOSE_EXERCISE_SAFE_MAX: float = 10.0

# Heart rate threshold
MAX_HR_RATIO: float = 0.90  # (220 - age) * 0.90

# Time windows (minutes)
TELEMETRY_GAP_ALERT_MIN: int = 60
SLOPE_WINDOW_MIN: int = 20
PRE_EXERCISE_WARN_MIN: int = 60

# Emotion staleness window (hours)
EMOTION_STALENESS_HOURS: int = 2

# Glucose drop estimation: base rates per activity type (mmol/L per minute)
BASE_DROP_RATE: dict[str, float] = {
    "resistance_training": 0.025,
    "cardio": 0.020,
    "hiit": 0.035,
}

# Glucose slope trigger threshold (mmol/L/min)
# Triggers when |slope| > this value (both rapid rise and rapid fall)
GLUCOSE_SLOPE_TRIGGER: float = 0.11

# Location proximity threshold (metres)
KNOWN_PLACE_RADIUS_M: int = 200

# Hard trigger display labels (mapped into intervention_log.display_label)
DISPLAY_LABELS: dict[str, str] = {
    "hard_low_glucose": "Low Blood Glucose",
    "hard_high_hr": "High Heart Rate",
    "data_gap": "CGM Signal Lost",
}
