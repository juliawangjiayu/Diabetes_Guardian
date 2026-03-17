"""
agent/nodes/communicator.py

Node 3: Generate personalised push notification using LLM and send via NotificationService.
Uses llm_communicator from agent.llm — never instantiates its own LLM.
"""

import json
from datetime import datetime

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.exc import SQLAlchemyError

from agent.llm import get_llm_communicator
from agent.state import AgentState
from db.models import InterventionLog
from db.session import AsyncSessionLocal
from gateway.services.notification import NotificationService

logger = structlog.get_logger(__name__)

COMMUNICATOR_PROMPT = """
You are the user's personal health companion. Write a single mobile push notification
in warm, natural English based on the clinical analysis provided.

You will receive:
- Current blood glucose value
- Risk level (LOW / MEDIUM / HIGH)
- Clinical reasoning summary (from Reflector — use as context, do NOT copy verbatim)
- Projected mid-exercise glucose (if available)
- Supplement recommendation with quantity (if available)

Writing rules:
1. Tone: friendly and conversational, like a message from a knowledgeable friend —
   not a clinical warning system
2. For risk_level HIGH: be more direct but remain calm; you may use "heads up" or "important"
3. Always mention the current glucose value
4. If supplement_recommendation is present, weave it naturally into the sentence —
   do not list it as a bullet point
5. If projected_glucose is present, use phrasing like
   "if you head to the gym now, your glucose could drop to X"
6. Keep the message under 60 words
7. End with one short encouraging phrase (under 8 words)
"""


async def communicator_node(state: AgentState) -> dict:
    """Generate personalised push notification and send to user."""
    task = state["task"]
    user_id = state["user_id"]

    # Silent logging for NO_ACTION decisions
    if state.get("intervention_action") == "NO_ACTION":
        logger.info("communicator_silent_log", user_id=user_id, decision="NO_ACTION")
        await _log_intervention(user_id, state, message="No notification needed due to safe projections.")
        return {
            "message_to_user": None,
            "notification_sent": False,
        }

    user_prompt = (
        f"current_glucose:           {task.get('current_glucose')}\n"
        f"risk_level:                {state.get('risk_level')}\n"
        f"reasoning_summary:         {state.get('reasoning_summary')}\n"
        f"projected_glucose:         {state.get('projected_glucose')}\n"
        f"supplement_recommendation: {state.get('supplement_recommendation')}\n"
        f"upcoming_activity:         {state.get('upcoming_activity')}\n"
    )

    messages = [
        SystemMessage(content=COMMUNICATOR_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        llm = get_llm_communicator()
        response = await llm.ainvoke(messages)
        message = response.content.strip()
    except Exception as e:
        logger.error("communicator_llm_failed", user_id=user_id, error=str(e))
        message = (
            f"Your glucose is at {task.get('current_glucose')} mmol/L. "
            "Please consider having a snack before your next activity. Stay safe!"
        )

    # Send push notification
    await NotificationService.send_push(user_id, message, state)

    # Write to intervention_log
    await _log_intervention(user_id, state, message)

    logger.info("communicator_sent", user_id=user_id, message_length=len(message))

    return {
        "message_to_user": message,
        "notification_sent": True,
    }


async def _log_intervention(
    user_id: str,
    state: AgentState,
    message: str,
) -> None:
    """Write soft trigger intervention to intervention_log."""
    task = state["task"]

    # Build agent_decision JSON from Reflector output
    agent_decision = json.dumps({
        "estimated_glucose_drop": state.get("estimated_glucose_drop"),
        "risk_level": state.get("risk_level"),
        "reasoning_summary": state.get("reasoning_summary"),
        "projected_glucose": state.get("projected_glucose"),
        "intervention_action": state.get("intervention_action"),
        "supplement_recommendation": state.get("supplement_recommendation"),
        "confidence": state.get("reflector_confidence"),
    })

    try:
        async with AsyncSessionLocal() as session:
            record = InterventionLog(
                user_id=user_id,
                triggered_at=datetime.now(),
                trigger_type=task.get("trigger_type"),
                display_label=None,  # soft triggers have no display_label
                agent_decision=agent_decision,
                message_sent=message,
            )
            session.add(record)
            await session.commit()
    except SQLAlchemyError as e:
        logger.error("intervention_log_failed", user_id=user_id, error=str(e))
