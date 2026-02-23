"""
agent/nodes/reflector.py

Node 2: Reflector.
Performs LLM-based clinical risk assessment using Gemini.
Falls back to rule-based assessment if LLM is unavailable.
"""

import json

import structlog
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import AgentState
from config import settings

logger = structlog.get_logger(__name__)

# System prompt injected into the reflector node for clinical reasoning
SYSTEM_PROMPT = """
你是一名专业的糖尿病管理 AI 助手，严格遵循以下指南：
1. 低血糖分级：Level 1 (3.0–3.9), Level 2 (<3.0), Level 3 (<2.8 且有症状)
2. 运动前血糖安全区间：5.6–10.0 mmol/L（高强度运动）
3. 你的职责是预防，而非诊断
4. 仅输出以下 JSON，不附加任何其他文字：
   {
     "risk_level": "LOW" | "MEDIUM" | "HIGH",
     "reasoning_summary": "...",
     "intervention_action": "NO_ACTION" | "SOFT_REMIND" | "STRONG_ALERT"
   }
"""

# Rule-based fallback per agent.md Section 3.3
_FALLBACK_RESPONSE: dict = {
    "risk_level": "MEDIUM",
    "reasoning_summary": "LLM 不可用，执行规则兜底",
    "intervention_action": "SOFT_REMIND",
}

# Max tokens per agent.md Section 6.3
_REFLECTOR_MAX_TOKENS: int = 512


def _build_user_prompt(state: AgentState) -> str:
    """Construct the user prompt containing all investigator data."""
    task = state["task"]
    parts = [
        f"Current glucose: {task.get('current_glucose', 'N/A')} mmol/L",
        f"Current heart rate: {task.get('current_hr', 'N/A')} bpm",
        f"Trigger type: {task.get('trigger_type', 'N/A')}",
        f"Location: {state.get('location_context', 'N/A')}",
    ]

    history = state.get("glucose_history_24h")
    if history:
        parts.append(f"24h glucose history (recent {len(history)} records): {history}")

    upcoming = state.get("upcoming_activity")
    if upcoming:
        parts.append(
            f"Upcoming activity: {upcoming.get('type', 'unknown')}, "
            f"probability={upcoming.get('probability', 'N/A')}, "
            f"avg glucose drop={upcoming.get('avg_drop', 'N/A')} mmol/L"
        )

    drops = state.get("recent_exercise_glucose_drops")
    if drops:
        parts.append(f"Recent exercise glucose drops: {drops}")

    return "\n".join(parts)


async def reflector_node(state: AgentState) -> dict:
    """
    Assess clinical risk using Gemini LLM with rule-based fallback.

    Returns only the fields this node is responsible for (partial state update).
    """
    user_prompt = _build_user_prompt(state)

    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            google_api_key=settings.google_api_key,
            max_output_tokens=_REFLECTOR_MAX_TOKENS,
            temperature=0.1,
        )

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_prompt),
        ]

        response = await llm.ainvoke(messages)
        raw_content = response.content.strip()

        # Parse JSON response from LLM
        parsed = json.loads(raw_content)

        logger.info(
            "reflector_complete",
            user_id=state["user_id"],
            risk_level=parsed.get("risk_level"),
            intervention_action=parsed.get("intervention_action"),
        )

        return {
            "risk_level": parsed["risk_level"],
            "reasoning_summary": parsed["reasoning_summary"],
            "intervention_action": parsed["intervention_action"],
        }

    except json.JSONDecodeError as exc:
        logger.error(
            "llm_parse_failed",
            user_id=state["user_id"],
            raw_response=raw_content if "raw_content" in dir() else "N/A",
            error=str(exc),
            fallback="rule_based",
        )
        return dict(_FALLBACK_RESPONSE)

    except Exception as exc:
        logger.error(
            "llm_call_failed",
            user_id=state["user_id"],
            error=str(exc),
            fallback="rule_based",
        )
        return dict(_FALLBACK_RESPONSE)
