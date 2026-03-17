"""
tests/test_graph.py

Integration tests for the LangGraph agent workflow.
Tests the Investigator → Reflector → Communicator pipeline.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest


class TestAgentGraph:
    @pytest.mark.asyncio
    async def test_graph_builds_without_error(self):
        """Verify the graph can be compiled."""
        from agent.graph import build_graph

        graph = build_graph()
        assert graph is not None

    @pytest.mark.asyncio
    async def test_no_action_skips_communicator(self):
        """When Reflector returns NO_ACTION, Communicator should be skipped."""
        from agent.graph import build_graph

        mock_investigator_output = {
            "location_context": "unknown location",
            "glucose_history_24h": [],
            "upcoming_activity": None,
            "exercise_history": [],
            "user_profile": {"age": 36, "bmi": 25.5, "gender": "male", "waist_cm": 85},
            "today_calories_burned": 0,
            "emotion_context": {"emotion_label": "unknown"},
            "glucose_daily_stats": None,
            "glucose_weekly_profile": None,
        }

        mock_reflector_output = {
            "estimated_glucose_drop": None,
            "risk_level": "LOW",
            "reasoning_summary": "No risk detected",
            "projected_glucose": None,
            "intervention_action": "NO_ACTION",
            "supplement_recommendation": None,
            "reflector_confidence": "HIGH",
        }

        with patch("agent.graph.investigator_node", new_callable=AsyncMock, return_value=mock_investigator_output), \
             patch("agent.graph.reflector_node", new_callable=AsyncMock, return_value=mock_reflector_output), \
             patch("agent.graph.communicator_node", new_callable=AsyncMock) as mock_comm:

            graph = build_graph()
            initial_state = {
                "task": {"user_id": "user_001", "trigger_type": "SOFT_RAPID_SLOPE", "trigger_at": datetime.now().isoformat(), "current_glucose": 6.5},
                "user_id": "user_001",
                "location_context": None,
                "glucose_history_24h": None,
                "upcoming_activity": None,
                "exercise_history": None,
                "user_profile": None,
                "today_calories_burned": None,
                "emotion_context": None,
                "glucose_daily_stats": None,
                "glucose_weekly_profile": None,
                "estimated_glucose_drop": None,
                "risk_level": None,
                "reasoning_summary": None,
                "projected_glucose": None,
                "intervention_action": None,
                "supplement_recommendation": None,
                "reflector_confidence": None,
                "message_to_user": None,
                "notification_sent": False,
            }

            result = await graph.ainvoke(initial_state)
            assert result["intervention_action"] == "NO_ACTION"
            # Communicator should NOT have been called
            mock_comm.assert_not_awaited()
