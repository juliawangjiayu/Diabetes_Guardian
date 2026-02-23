"""
agent/nodes/communicator.py

Node 3: Communicator.
Generates a personalized push notification message and delivers it to the user.
Logs the intervention to the database.
"""

import json
from datetime import datetime

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import AgentState
from config import settings
from db.models import AsyncSessionLocal, InterventionLog
from gateway.services.notification import send_push

logger = structlog.get_logger(__name__)

# Communicator prompt for generating user-facing messages
COMMUNICATOR_PROMPT = """
你是用户的健康伴侣。根据以下医学分析，生成一条推送通知。
要求：
- 语气温暖友好，risk_level=HIGH 时才可使用"注意"等词
- 给出 1 个具体可执行的建议（如：吃什么、吃多少克）
- 字数控制在 80 字以内
- 必须提及当前血糖数值
"""

# Max tokens per agent.md Section 6.3
_COMMUNICATOR_MAX_TOKENS: int = 256


def _build_communicator_prompt(state: AgentState) -> str:
    """Build the input prompt for message generation from reflector outputs."""
    task = state["task"]
    parts = [
        f"Risk level: {state.get('risk_level', 'UNKNOWN')}",
        f"Clinical reasoning: {state.get('reasoning_summary', 'N/A')}",
        f"Intervention type: {state.get('intervention_action', 'N/A')}",
        f"Current glucose: {task.get('current_glucose', 'N/A')} mmol/L",
        f"Location: {state.get('location_context', 'N/A')}",
    ]

    upcoming = state.get("upcoming_activity")
    if upcoming:
        parts.append(f"Upcoming activity: {upcoming}")

    return "\n".join(parts)


async def _log_intervention(state: AgentState, message: str) -> None:
    """Persist the intervention record to the database."""
    try:
        async with AsyncSessionLocal() as session:
            log_entry = InterventionLog(
                user_id=state["user_id"],
                triggered_at=datetime.fromisoformat(
                    state["task"].get("trigger_at", datetime.utcnow().isoformat())
                ),
                trigger_type=state["task"].get("trigger_type"),
                agent_decision=json.dumps(
                    {
                        "risk_level": state.get("risk_level"),
                        "reasoning_summary": state.get("reasoning_summary"),
                        "intervention_action": state.get("intervention_action"),
                    },
                    ensure_ascii=False,
                ),
                message_sent=message,
            )
            session.add(log_entry)
            await session.commit()
            logger.info(
                "intervention_logged",
                user_id=state["user_id"],
                trigger_type=state["task"].get("trigger_type"),
            )
    except Exception as exc:
        logger.error(
            "intervention_log_failed",
            user_id=state["user_id"],
            error=str(exc),
        )


async def communicator_node(state: AgentState) -> dict:
    """
    Generate a personalized notification and send it to the user.

    Returns only the fields this node is responsible for (partial state update).
    """
    user_prompt = _build_communicator_prompt(state)

    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            max_output_tokens=_COMMUNICATOR_MAX_TOKENS,
            temperature=0.7,
        )

        messages = [
            ("system", COMMUNICATOR_PROMPT),
            ("human", user_prompt),
        ]

        response = await llm.ainvoke(messages)
        message = response.content.strip()

    except Exception as exc:
        logger.error(
            "communicator_llm_failed",
            user_id=state["user_id"],
            error=str(exc),
            fallback="template_message",
        )
        # Fallback template message
        glucose = state["task"].get("current_glucose", "N/A")
        message = f"您当前血糖 {glucose} mmol/L，建议适当补充碳水化合物。"

    # Send push notification
    await send_push(state["user_id"], message)

    # Log the intervention
    await _log_intervention(state, message)

    logger.info(
        "communicator_complete",
        user_id=state["user_id"],
        message_length=len(message),
    )

    return {
        "message_to_user": message,
        "notification_sent": True,
    }
