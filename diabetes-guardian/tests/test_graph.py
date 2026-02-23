"""
tests/test_graph.py

Integration tests for the LangGraph agent workflow.
All MCP calls and LLM invocations are mocked per agent.md Section 9.3.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tests.fixtures import build_initial_state


@pytest.mark.asyncio
async def test_investigator_node_gathers_context() -> None:
    """Investigator should call both MCP servers concurrently and populate state."""
    mock_location = {
        "semantic_location": "在家中",
        "is_at_home": True,
        "nearby_known_places": [],
    }
    mock_history = {
        "glucose_history_24h": [{"time": "2024-06-15T12:00:00", "glucose": 5.2}],
        "upcoming_activity": {
            "type": "resistance_training",
            "probability": 0.85,
            "expected_start_hour": 14,
            "avg_glucose_drop": 2.5,
        },
        "recent_exercise_drops": [2.1, 1.8, 2.5],
    }

    with patch(
        "agent.nodes.investigator.call_location_context_mcp",
        new_callable=AsyncMock,
        return_value=mock_location,
    ), patch(
        "agent.nodes.investigator.call_patient_history_mcp",
        new_callable=AsyncMock,
        return_value=mock_history,
    ):
        from agent.nodes.investigator import investigator_node

        state = build_initial_state()
        result = await investigator_node(state)

        assert result["location_context"] == "在家中"
        assert len(result["glucose_history_24h"]) == 1
        assert result["upcoming_activity"]["type"] == "resistance_training"
        assert len(result["recent_exercise_glucose_drops"]) == 3


@pytest.mark.asyncio
async def test_investigator_node_degrades_on_mcp_timeout() -> None:
    """Investigator should return fallback values when MCP servers timeout."""
    with patch(
        "agent.nodes.investigator.call_location_context_mcp",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ), patch(
        "agent.nodes.investigator.call_patient_history_mcp",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ):
        from agent.nodes.investigator import investigator_node

        state = build_initial_state()
        result = await investigator_node(state)

        assert result["location_context"] == "未知位置"
        assert result["glucose_history_24h"] == []


@pytest.mark.asyncio
async def test_reflector_node_returns_valid_assessment() -> None:
    """Reflector should parse LLM response into structured risk assessment."""
    mock_llm_response = AsyncMock()
    mock_llm_response.content = (
        '{"risk_level": "MEDIUM", '
        '"reasoning_summary": "Pre-exercise glucose buffer is low", '
        '"intervention_action": "SOFT_REMIND"}'
    )

    with patch(
        "agent.nodes.reflector.ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
        mock_llm_cls.return_value = mock_llm

        from agent.nodes.reflector import reflector_node

        state = build_initial_state()
        state["location_context"] = "在家中"
        state["glucose_history_24h"] = []
        state["upcoming_activity"] = None
        state["recent_exercise_glucose_drops"] = []

        result = await reflector_node(state)

        assert result["risk_level"] == "MEDIUM"
        assert result["intervention_action"] == "SOFT_REMIND"


@pytest.mark.asyncio
async def test_reflector_node_falls_back_on_llm_failure() -> None:
    """Reflector should use rule-based fallback when LLM fails."""
    with patch(
        "agent.nodes.reflector.ChatGoogleGenerativeAI"
    ) as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM unavailable"))
        mock_llm_cls.return_value = mock_llm

        from agent.nodes.reflector import reflector_node

        state = build_initial_state()
        state["location_context"] = "未知位置"
        state["glucose_history_24h"] = []
        state["upcoming_activity"] = None
        state["recent_exercise_glucose_drops"] = []

        result = await reflector_node(state)

        assert result["risk_level"] == "MEDIUM"
        assert result["intervention_action"] == "SOFT_REMIND"
        assert "规则兜底" in result["reasoning_summary"]
