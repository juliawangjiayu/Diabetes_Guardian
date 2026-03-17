"""
agent/main.py

Celery Worker entry point for the agent layer.
Receives investigation tasks from Redis queue and runs the LangGraph workflow.

Start with: celery -A agent.main worker --loglevel=info
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import json

import structlog
from celery import Celery

from config import settings

logger = structlog.get_logger(__name__)

celery_app = Celery("diabetes_guardian", broker=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
)


@celery_app.task(name="agent.tasks.run_investigation")
def run_investigation(task_json: str) -> None:
    """Celery task that drives the async LangGraph workflow."""
    asyncio.run(_run_graph(task_json))


async def _run_graph(task_json: str) -> None:
    """Parse InvestigationTask and invoke the compiled LangGraph."""
    from agent.graph import build_graph
    from db.session import engine

    # Dispose inherited engine pool to bind to the current event loop
    await engine.dispose()

    try:
        task = json.loads(task_json)
        graph = build_graph()

        initial_state = {
            "task": task,
            "user_id": task["user_id"],
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

        logger.info("graph_started", user_id=task["user_id"], trigger_type=task["trigger_type"])

        result = await graph.ainvoke(initial_state)

        logger.info(
            "graph_completed",
            user_id=task["user_id"],
            intervention_action=result.get("intervention_action"),
            notification_sent=result.get("notification_sent"),
        )
    finally:
        # Dispose again before loop closes to prevent RuntimeError: Event loop is closed
        await engine.dispose()
