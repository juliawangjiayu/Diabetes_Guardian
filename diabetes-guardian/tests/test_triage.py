"""
tests/test_triage.py

Unit tests for gateway/services/triage.py.
Covers hard triggers, soft triggers, and no-trigger scenarios.
"""

import asyncio
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.services.triage import (
    _glucose_windows,
    evaluate_hard_triggers,
    evaluate_soft_triggers,
)


@pytest.fixture(autouse=True)
def clear_windows():
    """Clear sliding windows between tests."""
    _glucose_windows.clear()
    yield
    _glucose_windows.clear()


# ── Hard Trigger Tests ─────────────────────────────────────────


class TestHardTriggers:
    @pytest.mark.asyncio
    async def test_low_glucose_fires(self):
        """Scenario C: glucose=3.1 → hard_low_glucose."""
        with patch("gateway.services.triage.EmergencyService") as mock_es:
            mock_es.fire = AsyncMock()
            result = await evaluate_hard_triggers(
                user_id="user_001", glucose=3.1
            )
            assert result is True
            mock_es.fire.assert_awaited_once_with("user_001", "hard_low_glucose")

    @pytest.mark.asyncio
    async def test_high_hr_fires(self):
        """Scenario B: HR=185, age=36 → max_hr=165.6 → hard_high_hr."""
        with patch("gateway.services.triage.EmergencyService") as mock_es:
            mock_es.fire = AsyncMock()
            result = await evaluate_hard_triggers(
                user_id="user_001", heart_rate=185, age=36
            )
            assert result is True
            mock_es.fire.assert_awaited_once_with("user_001", "hard_high_hr")

    @pytest.mark.asyncio
    async def test_normal_glucose_no_trigger(self):
        """Scenario E: glucose=6.5 → no trigger."""
        with patch("gateway.services.triage.EmergencyService") as mock_es:
            mock_es.fire = AsyncMock()
            result = await evaluate_hard_triggers(
                user_id="user_001", glucose=6.5
            )
            assert result is False
            mock_es.fire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_normal_hr_no_trigger(self):
        """HR=78, age=36 → max_hr=165.6 → no trigger."""
        with patch("gateway.services.triage.EmergencyService") as mock_es:
            mock_es.fire = AsyncMock()
            result = await evaluate_hard_triggers(
                user_id="user_001", heart_rate=78, age=36
            )
            assert result is False
            mock_es.fire.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_boundary_glucose_no_trigger(self):
        """glucose=3.9 → exactly at boundary → no hard trigger (>= 3.9 is safe)."""
        with patch("gateway.services.triage.EmergencyService") as mock_es:
            mock_es.fire = AsyncMock()
            result = await evaluate_hard_triggers(
                user_id="user_001", glucose=3.9
            )
            assert result is False


# ── Soft Trigger Tests ─────────────────────────────────────────


class TestSoftTriggers:
    @pytest.mark.asyncio
    async def test_slope_trigger_fires(self):
        """Scenario B: rapid falling slope from 3 CGM readings."""
        with patch("gateway.services.triage.celery_app") as mock_celery, \
             patch("gateway.services.triage._get_last_gps", new_callable=AsyncMock, return_value=(None, None)), \
             patch("gateway.services.triage.settings") as mock_settings:
            mock_settings.demo_mode = True

            base = datetime(2024, 6, 15, 13, 0, 0)

            # Send 3 readings with rapid drop
            for i, glucose in enumerate([6.2, 5.0, 3.5]):
                ts = base + timedelta(minutes=i * 10)
                result = await evaluate_soft_triggers("user_001", glucose, ts)

            # The third reading should trigger
            assert result is not None
            assert result.trigger_type == "SOFT_RAPID_SLOPE"

    @pytest.mark.asyncio
    async def test_pre_exercise_trigger_fires(self):
        """Scenario A: glucose=4.8, upcoming resistance_training in < 60 min."""
        with patch("gateway.services.triage.celery_app") as mock_celery, \
             patch("gateway.services.triage._get_last_gps", new_callable=AsyncMock, return_value=(1.32, 103.84)), \
             patch("gateway.services.triage._find_upcoming_activity", new_callable=AsyncMock) as mock_activity, \
             patch("gateway.services.triage.settings") as mock_settings:
            mock_settings.demo_mode = True
            mock_activity.return_value = {
                "activity_type": "resistance_training",
                "start_time": "14:00",
                "end_time": "15:30",
                "duration_min": 90,
            }

            ts = datetime(2024, 6, 15, 13, 10, 0)  # Saturday
            result = await evaluate_soft_triggers("user_001", 4.8, ts)

            assert result is not None
            assert result.trigger_type == "SOFT_PRE_EXERCISE_LOW_BUFFER"

    @pytest.mark.asyncio
    async def test_no_trigger_normal(self):
        """Scenario E: glucose=6.5, no upcoming activity → no trigger."""
        with patch("gateway.services.triage._find_upcoming_activity", new_callable=AsyncMock, return_value=None), \
             patch("gateway.services.triage.settings") as mock_settings:
            mock_settings.demo_mode = True

            ts = datetime(2024, 6, 15, 13, 10, 0)
            result = await evaluate_soft_triggers("user_001", 6.5, ts)
            assert result is None
