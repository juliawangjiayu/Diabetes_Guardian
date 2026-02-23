"""
gateway/constants.py

Medical threshold constants used by the triage engine.
All clinical numeric values must be referenced from this module.
Magic numbers in business logic are prohibited per agent.md Section 10.
"""

# ── Glucose thresholds (mmol/L) ──────────────────────────────
GLUCOSE_HARD_LOW: float = 3.9
GLUCOSE_SOFT_LOW_MIN: float = 4.0
GLUCOSE_SOFT_LOW_MAX: float = 5.6
GLUCOSE_EXERCISE_SAFE_MIN: float = 5.6
GLUCOSE_EXERCISE_SAFE_MAX: float = 10.0

# ── Heart rate threshold ─────────────────────────────────────
MAX_HR_RATIO: float = 0.90  # (220 - age) * MAX_HR_RATIO

# ── Time windows (minutes) ───────────────────────────────────
TELEMETRY_GAP_ALERT_MIN: int = 30
SLOPE_WINDOW_MIN: int = 20
PRE_EXERCISE_WARN_MIN: int = 60

# ── Soft trigger thresholds ──────────────────────────────────
ACTIVITY_PROBABILITY_THRESHOLD: float = 0.70
GLUCOSE_SLOPE_TRIGGER: float = -0.1  # mmol/L per minute

# ── Location thresholds (meters) ─────────────────────────────
KNOWN_PLACE_RADIUS_M: int = 200

# ── Sliding window config ────────────────────────────────────
SLIDING_WINDOW_MAX_LEN: int = 20
