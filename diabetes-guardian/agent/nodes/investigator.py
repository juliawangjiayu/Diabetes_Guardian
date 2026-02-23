"""
agent/nodes/investigator.py

Node 1: Investigator.
Concurrently calls Patient History MCP and Location Context MCP servers
to gather contextual data for the Reflector node.
"""

import asyncio

import httpx
import structlog

from agent.state import AgentState
from config import settings

logger = structlog.get_logger(__name__)

# Fallback values per agent.md Section 3.3
_LOCATION_FALLBACK: dict = {
    "semantic_location": "未知位置",
    "is_at_home": False,
    "nearby_known_places": [],
}

_HISTORY_FALLBACK: dict = {
    "glucose_history_24h": [],
    "upcoming_activity": None,
    "recent_exercise_drops": [],
}


async def call_location_context_mcp(
    lat: float,
    lng: float,
    user_id: str,
) -> dict:
    """Call the Location Context MCP server to resolve semantic location."""
    url = f"{settings.location_context_mcp_url}/tools/get_semantic_location"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json={"user_id": user_id, "lat": lat, "lng": lng},
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.warning(
            "mcp_timeout",
            service="location_context",
            url=url,
            user_id=user_id,
        )
        return _LOCATION_FALLBACK
    except httpx.HTTPStatusError as exc:
        logger.error(
            "mcp_http_error",
            service="location_context",
            status=exc.response.status_code,
            user_id=user_id,
        )
        return _LOCATION_FALLBACK
    except Exception as exc:
        logger.error(
            "mcp_unexpected_error",
            service="location_context",
            error=str(exc),
            user_id=user_id,
        )
        return _LOCATION_FALLBACK


async def call_patient_history_mcp(
    user_id: str,
    reference_time: str,
) -> dict:
    """Call the Patient History MCP server to retrieve patient context."""
    url = f"{settings.patient_history_mcp_url}/tools/get_patient_context"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                url,
                json={"user_id": user_id, "reference_time": reference_time},
            )
            response.raise_for_status()
            return response.json()
    except httpx.TimeoutException:
        logger.warning(
            "mcp_timeout",
            service="patient_history",
            url=url,
            user_id=user_id,
        )
        return _HISTORY_FALLBACK
    except httpx.HTTPStatusError as exc:
        logger.error(
            "mcp_http_error",
            service="patient_history",
            status=exc.response.status_code,
            user_id=user_id,
        )
        return _HISTORY_FALLBACK
    except Exception as exc:
        logger.error(
            "mcp_unexpected_error",
            service="patient_history",
            error=str(exc),
            user_id=user_id,
        )
        return _HISTORY_FALLBACK


async def investigator_node(state: AgentState) -> dict:
    """
    Gather contextual data by concurrently querying MCP servers.

    Returns only the fields this node is responsible for (partial state update).
    """
    task = state["task"]

    # Concurrent MCP calls per agent.md Section 3.2
    location_result, history_result = await asyncio.gather(
        call_location_context_mcp(
            task["gps_lat"], task["gps_lng"], task["user_id"]
        ),
        call_patient_history_mcp(task["user_id"], task["trigger_at"]),
    )

    logger.info(
        "investigator_complete",
        user_id=state["user_id"],
        location=location_result.get("semantic_location"),
        history_records=len(history_result.get("glucose_history_24h", [])),
    )

    return {
        "location_context": location_result["semantic_location"],
        "glucose_history_24h": history_result["glucose_history_24h"],
        "upcoming_activity": history_result.get("upcoming_activity"),
        "recent_exercise_glucose_drops": history_result.get(
            "recent_exercise_drops", []
        ),
    }
