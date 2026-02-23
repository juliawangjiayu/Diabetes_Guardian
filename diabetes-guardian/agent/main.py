"""
agent/main.py

Celery Worker entry point.
Defines the Celery app and the investigation task that drives the LangGraph agent.
"""

import asyncio
import json

import structlog
from celery import Celery

from config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)


async def _run_graph(task_json: str) -> None:
    """Async entrypoint that builds and invokes the LangGraph workflow."""
    from agent.graph import build_graph

    task_data = json.loads(task_json)
    user_id = task_data["user_id"]

    logger.info("agent_graph_starting", user_id=user_id, trigger_type=task_data.get("trigger_type"))

    initial_state = {
        "task": task_data,
        "user_id": user_id,
        "location_context": None,
        "glucose_history_24h": None,
        "upcoming_activity": None,
        "recent_exercise_glucose_drops": None,
        "risk_level": None,
        "reasoning_summary": None,
        "intervention_action": None,
        "message_to_user": None,
        "notification_sent": False,
    }

    graph = build_graph()
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "agent_graph_complete",
        user_id=user_id,
        risk_level=final_state.get("risk_level"),
        intervention_action=final_state.get("intervention_action"),
        notification_sent=final_state.get("notification_sent"),
    )


@celery_app.task(name="agent.tasks.run_investigation")
def run_investigation(task_json: str) -> None:
    """
    Celery task that drives the LangGraph agent workflow.

    Uses asyncio.run() to bridge Celery's sync interface with async graph execution,
    per agent.md Section 3.2.
    """
    asyncio.run(_run_graph(task_json))
