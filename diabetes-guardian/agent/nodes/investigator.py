"""
agent/nodes/investigator.py

Node 1: Pure data-fetch node. No computation or reasoning.
Concurrently calls all three local tool functions and returns structured data for Reflector.
"""

import asyncio
import structlog

from agent.state import AgentState
from agent.tools.emotion_context_tool import get_emotion_context
from agent.tools.location_context_tool import get_semantic_location
from agent.tools.patient_history_tool import get_patient_context
from config import settings

logger = structlog.get_logger(__name__)

# Default fallback values per spec
_LOCATION_FALLBACK: dict = {
    "semantic_location": "unknown location",
    "is_at_home": False,
    "nearby_known_places": [],
}

_HISTORY_FALLBACK: dict = {
    "glucose_history_24h": [],
    "upcoming_activity": None,
    "exercise_history": [],
    "user_profile": None,
    "today_calories_burned": 0.0,
    "glucose_daily_stats": None,
    "glucose_weekly_profile": None,
}


async def investigator_node(state: AgentState) -> dict:
    """Fetch all context data concurrently from MCP servers."""
    task = state["task"]
    user_id = task["user_id"]

    location, history, emotion = await asyncio.gather(
        call_location_context_mcp(
            task.get("gps_lat"),
            task.get("gps_lng"),
            user_id,
        ),
        call_patient_history_mcp(user_id, task.get("trigger_at", "")),
        call_emotion_context_mcp(user_id),
    )

    # Resolve null emotion to default
    if emotion is None:
        emotion = {"emotion_label": "unknown"}

    return {
        "location_context": location.get("semantic_location", "unknown location"),
        "glucose_history_24h": history.get("glucose_history_24h", []),
        "upcoming_activity": history.get("upcoming_activity"),
        "exercise_history": history.get("exercise_history", []),
        "user_profile": history.get("user_profile"),
        "today_calories_burned": history.get("today_calories_burned", 0.0),
        "emotion_context": emotion,
        "glucose_daily_stats": history.get("glucose_daily_stats"),
        "glucose_weekly_profile": history.get("glucose_weekly_profile"),
    }


async def call_location_context_mcp(
    lat: float | None,
    lng: float | None,
    user_id: str,
) -> dict:
    """Call Location Context tool to resolve GPS to semantic location."""
    if lat is None or lng is None:
        return _LOCATION_FALLBACK

    try:
        data = await get_semantic_location(user_id, lat, lng)
        return data if data else _LOCATION_FALLBACK
    except Exception as e:
        logger.error("tool_error", service="location_context", error=str(e))
        return _LOCATION_FALLBACK


async def call_patient_history_mcp(
    user_id: str,
    reference_time: str,
) -> dict:
    """Call Patient History tool to fetch glucose history, profile, and stats."""
    try:
        data = await get_patient_context(user_id, reference_time)
        return data if data else _HISTORY_FALLBACK
    except Exception as e:
        logger.error("tool_error", service="patient_history", error=str(e))
        return _HISTORY_FALLBACK


async def call_emotion_context_mcp(user_id: str) -> dict | None:
    """Call Emotion Context tool to fetch most recent emotion within 2h window."""
    try:
        return await get_emotion_context(user_id)
    except Exception as e:
        logger.error("tool_error", service="emotion_context", error=str(e))
        return None
