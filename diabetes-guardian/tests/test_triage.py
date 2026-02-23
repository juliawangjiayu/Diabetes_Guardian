"""
tests/test_triage.py

Unit tests for gateway/services/triage.py.
Covers hard triggers, soft triggers, and degradation scenarios.
All database and external calls are mocked per agent.md Section 9.3.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.schemas import TelemetryPayload
from tests.fixtures import TEST_USER_AGE, build_telemetry


@pytest.mark.asyncio
async def test_hard_trigger_fires_on_low_glucose() -> None:
    """Glucose below GLUCOSE_HARD_LOW should trigger emergency alert."""
    payload = build_telemetry(glucose=3.1)
    with patch(
        "gateway.services.triage.send_emergency_alert", new_callable=AsyncMock
    ) as mock_alert, patch(
        "gateway.services.triage.AsyncSessionLocal"
    ) as mock_session_cls:
        # Mock database query returning 0 recent records
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from gateway.services.triage import evaluate_hard_triggers

        result = await evaluate_hard_triggers(payload, user_age=TEST_USER_AGE)

        assert result is True
        mock_alert.assert_called_once()


@pytest.mark.asyncio
async def test_hard_trigger_fires_on_high_heart_rate() -> None:
    """Heart rate exceeding age-adjusted max should trigger emergency alert."""
    # For age 34: max HR = (220 - 34) * 0.90 = 167.4
    payload = build_telemetry(heart_rate=170, glucose=6.0)
    with patch(
        "gateway.services.triage.send_emergency_alert", new_callable=AsyncMock
    ) as mock_alert, patch(
        "gateway.services.triage.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from gateway.services.triage import evaluate_hard_triggers

        result = await evaluate_hard_triggers(payload, user_age=TEST_USER_AGE)

        assert result is True
        mock_alert.assert_called_once()


@pytest.mark.asyncio
async def test_hard_trigger_skips_on_normal_values() -> None:
    """Normal glucose and heart rate should not trigger."""
    payload = build_telemetry(glucose=5.5, heart_rate=80)
    with patch(
        "gateway.services.triage.send_emergency_alert", new_callable=AsyncMock
    ) as mock_alert, patch(
        "gateway.services.triage.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from gateway.services.triage import evaluate_hard_triggers

        result = await evaluate_hard_triggers(payload, user_age=TEST_USER_AGE)

        assert result is False
        mock_alert.assert_not_called()


@pytest.mark.asyncio
async def test_soft_trigger_skips_on_safe_glucose() -> None:
    """Glucose outside the soft trigger range should not fire."""
    payload = build_telemetry(glucose=6.2, heart_rate=80)
    with patch(
        "gateway.services.triage._check_upcoming_activity",
        new_callable=AsyncMock,
        return_value=None,
    ):
        from gateway.services.triage import evaluate_soft_triggers

        result = await evaluate_soft_triggers(payload, user_age=TEST_USER_AGE)

        assert result is None
