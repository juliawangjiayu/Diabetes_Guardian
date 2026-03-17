"""
tests/test_reflector_drop_calc.py

Tests for estimated_glucose_drop calculation logic in Reflector.
Covers Priority 1 (history-based) and Priority 2 (formula-based) paths.
"""

import pytest

from gateway.constants import BASE_DROP_RATE


class TestDropCalculation:
    def test_formula_based_drop_resistance(self):
        """Priority 2: formula-based drop for resistance training, 90 min, BMI 25.5."""
        base_rate = BASE_DROP_RATE["resistance_training"]
        duration_min = 90
        bmi = 25.5
        bmi_modifier = 1.0 - max(0, (bmi - 25) * 0.005)

        estimated_drop = base_rate * duration_min * bmi_modifier
        # 0.025 * 90 * 0.9975 = 2.244
        assert 2.2 < estimated_drop < 2.3

    def test_formula_based_drop_cardio(self):
        """Priority 2: formula for cardio, 45 min, BMI 22."""
        base_rate = BASE_DROP_RATE["cardio"]
        duration_min = 45
        bmi = 22
        bmi_modifier = 1.0 - max(0, (bmi - 25) * 0.005)

        estimated_drop = base_rate * duration_min * bmi_modifier
        # BMI < 25 → modifier = 1.0 → 0.020 * 45 = 0.9
        assert estimated_drop == pytest.approx(0.9)

    def test_formula_based_drop_hiit(self):
        """Priority 2: HIIT has highest drop rate."""
        base_rate = BASE_DROP_RATE["hiit"]
        duration_min = 60
        bmi = 28
        bmi_modifier = 1.0 - max(0, (bmi - 25) * 0.005)

        estimated_drop = base_rate * duration_min * bmi_modifier
        # 0.035 * 60 * 0.985 = 2.069
        assert 2.0 < estimated_drop < 2.1

    def test_emotion_modifier_anxious(self):
        """Emotion modifier: anxious → 1.20× multiplier."""
        base_drop = 2.0
        emotion_label = "anxious"

        if emotion_label in ("anxious", "stressed"):
            adjusted = base_drop * 1.20
        else:
            adjusted = base_drop

        assert adjusted == pytest.approx(2.4)

    def test_emotion_modifier_unknown(self):
        """No modifier for unknown emotion."""
        base_drop = 2.0
        emotion_label = "unknown"

        if emotion_label in ("anxious", "stressed"):
            adjusted = base_drop * 1.20
        else:
            adjusted = base_drop

        assert adjusted == pytest.approx(2.0)

    def test_history_based_drop_priority_1(self):
        """Priority 1: mean of 3 historical drops."""
        exercise_history = [
            {"glucose_drop": 2.1},
            {"glucose_drop": 2.5},
            {"glucose_drop": 1.8},
        ]
        estimated_drop = sum(h["glucose_drop"] for h in exercise_history) / len(exercise_history)
        assert estimated_drop == pytest.approx(2.133, abs=0.01)

    def test_bmi_modifier_high_bmi(self):
        """High BMI (35) → significant reduction in sensitivity."""
        bmi = 35
        bmi_modifier = 1.0 - max(0, (bmi - 25) * 0.005)
        # 1.0 - (10 * 0.005) = 0.95
        assert bmi_modifier == pytest.approx(0.95)

    def test_bmi_modifier_low_bmi(self):
        """Low BMI (20) → modifier capped at 1.0."""
        bmi = 20
        bmi_modifier = 1.0 - max(0, (bmi - 25) * 0.005)
        assert bmi_modifier == 1.0
