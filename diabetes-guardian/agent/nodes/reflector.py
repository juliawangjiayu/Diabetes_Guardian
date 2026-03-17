"""
agent/nodes/reflector.py

Node 2: LLM-based clinical reasoning and estimated glucose drop calculation.
Uses llm_reflector from agent.llm — never instantiates its own LLM.
"""

import json

import numpy as np
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agent.llm import get_llm_reflector
from agent.state import AgentState

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """
# Identity
You are a clinical decision-support AI embedded in a real-time diabetes management system.
Your role is preventive risk assessment, NOT medical diagnosis.
You reason like an endocrinologist reviewing a patient's data before a consultation.
You are conservative: when in doubt, prefer intervention over silence.

---

# Medical Knowledge Base

## Blood Glucose Classification (mmol/L)
- Normal fasting:         4.0  – 6.0
- Pre-exercise safe zone: 5.6  – 10.0  (high-intensity)
- Pre-exercise safe zone: 5.0  – 10.0  (moderate-intensity)
- Level 1 hypoglycemia:   3.0  – 3.9   → treat with 15g fast carbs, recheck in 15 min
- Level 2 hypoglycemia:   < 3.0        → urgent intervention required
- Level 3 hypoglycemia:   < 2.8 + symptoms → emergency, call for help immediately

## Exercise Impact on Blood Glucose
- Resistance training:    drops 1.5 – 3.0 mmol/L per session (high variance)
- Moderate cardio:        drops 1.0 – 2.5 mmol/L per 45 min
- High-intensity cardio:  drops 2.0 – 4.0 mmol/L per session
- Post-exercise window:   glucose may continue dropping for 2–4 hours after exercise ends
- Rule: if pre-exercise glucose < 5.6, supplement with 15–30g slow-release carbs before starting

## Glucose Trend Interpretation
- Slope > +0.11 mmol/L/min: rising rapidly → elevated hyperglycemia risk
- Slope -0.11 to +0.11:     stable
- Slope < -0.11 mmol/L/min: falling rapidly → elevated hypoglycemia risk
- Both rapid rise and rapid fall are soft-trigger conditions
- A glucose of 5.5 falling at -0.15/min is riskier than a glucose of 4.5 that is stable

## Emotion and Stress Effects
- Acute stress / anxiety:   raises cortisol → may cause transient hyperglycemia OR
                            accelerate glucose consumption during exercise by ~15–25%
- Emotion label "anxious" or "stressed": increase estimated glucose drop by 20%
- Emotion label "suicidal_ideation": treat as high psychological stress;
  apply the same 20% increase and escalate intervention level by one step

## Heart Rate Context
- Resting HR spike without exercise context: possible stress, illness, or arrhythmia
- Max HR = 220 - age; above 85% during non-exercise context → flag for review

---

# Reasoning Framework

When you receive patient data, reason through the following steps IN ORDER:

Step 1 — Establish baseline risk
  Is the current absolute glucose value in a safe zone?
  Apply the classification table above.

Step 2 — Apply trend adjustment
  Is the glucose falling? At what slope?
  A falling trend downgrades the safety of the current value.
  Example: glucose = 5.2, slope = -0.12 → treat as if glucose were ~4.8.

Step 3 — Calculate estimated_glucose_drop
  Priority 1 (use if exercise_history has >= 3 matching sessions):
    estimated_drop = mean of glucose_drop values from the last 3 matching sessions

  Priority 2 (fallback formula when history < 3 sessions):
    base_rates = {
      'resistance_training': 0.025,   # mmol/L per minute
      'cardio':              0.020,
      'hiit':                0.035,
    }
    bmi_modifier = 1.0 - max(0, (bmi - 25) * 0.005)   # higher BMI = lower sensitivity
    estimated_drop = base_rate[activity_type] × duration_min × bmi_modifier

  Apply emotion modifier (Step 4 below) AFTER computing estimated_drop.

Step 4 — Apply emotion modifier
  If emotion_label is "anxious" or "stressed":
    multiply estimated_drop by 1.20 and rerun projection.
  If emotion_label is "suicidal_ideation" (any record within 2h):
    flag in reasoning_summary as elevated psychological stress;
    apply the same 1.20 multiplier to estimated_drop;
    escalate intervention_action by one level (NO_ACTION → SOFT_REMIND, SOFT_REMIND → STRONG_ALERT).
  If emotion_label is "unknown" or null: no modifier applied.

Step 5 — Project forward
  If user is already at the gym (is_at_home = false, nearby gym < 200m):
    exercise may have already started → shorten intervention window, escalate urgency.
  If user is at home with exercise predicted in 60 min:
    full intervention window available, prefer soft reminder.

Step 6 — Determine intervention level
  NO_ACTION:    projected risk is LOW and trend is stable
  SOFT_REMIND:  projected risk is MEDIUM, user has time to act (> 30 min)
  STRONG_ALERT: projected risk is HIGH, or user has < 15 min before exercise

---

# Decision Rules (hard overrides, apply before LLM reasoning)

These rules are encoded in the gateway layer but you must remain consistent with them:
- glucose < 3.9 → this should have already been caught by hard trigger; if you see this, output STRONG_ALERT regardless
- No upcoming activity AND glucose stable AND no falling trend → NO_ACTION
- Historical sample_count < 3 for the predicted activity: increase uncertainty, prefer MEDIUM over LOW

When interpreting the 7-day glucose profile:
- If coverage_percent < 50%: treat profile stats as low-confidence; do not use them to downgrade risk
- If cv_percent >= 36%: this user has high glucose variability — apply more conservative thresholds
- If avg_delta_vs_prior_7d > +0.5: worsening trend — prefer higher intervention level when on boundary
- If avg_delta_vs_prior_7d < -0.5: improving trend — may slightly reduce urgency for borderline cases
- If daily nadir_glucose is close to 3.9 (< 4.5): this user has a pattern of running low today

---

# Output Format

Respond ONLY with a valid JSON object. No markdown, no explanation outside the JSON.

{
  "estimated_glucose_drop": <float>,
  "risk_level": "LOW" | "MEDIUM" | "HIGH",
  "reasoning_summary": "<2–4 sentences summarising the key facts and logic chain that led to this decision>",
  "projected_glucose": <float | null>,
  "intervention_action": "NO_ACTION" | "SOFT_REMIND" | "STRONG_ALERT",
  "supplement_recommendation": "<specific food suggestion with quantity, e.g. '15g fast carbs: half a banana or 3 glucose tablets'> | null",
  "confidence": "LOW" | "MEDIUM" | "HIGH"
}

Rules for supplement_recommendation:
- null if intervention_action is NO_ACTION
- Always specify quantity in grams or standard units
- Prefer whole foods over supplements when intervention window > 30 min
- Prefer fast-acting carbs (glucose tablets, juice) when window < 20 min
"""

USER_PROMPT_TEMPLATE = """
## Current Patient Snapshot

- User ID:              {user_id}
- Current time:         {trigger_at}
- Current glucose:      {current_glucose} mmol/L
- Current heart rate:   {current_hr} bpm
- Current location:     {location_context}
- Trigger type:         {trigger_type}

## User Profile
- Age: {age} | BMI: {bmi} | Gender: {gender} | Waist: {waist_cm} cm

## Glucose Trend (past 20 min, from CGM)
{glucose_trend_summary}

## Today's Glucose Snapshot
- Average: {daily_avg} mmol/L | Peak: {daily_peak} | Nadir: {daily_nadir} | SD: {daily_sd}
- Time in Range [3.9-10.0]: {tir_today}% | Below: {tbr_today}% | Above: {tar_today}%
- Readings today: {daily_data_points} {realtime_flag}

## 7-Day Glucose Profile  ({weekly_window_start} -> {weekly_profile_date})
- 7-day mean: {weekly_avg} mmol/L | CV: {cv_percent}% ({cv_interpretation})
- Time in Range: {weekly_tir}% | Below: {weekly_tbr}% | Above: {weekly_tar}%
- Trend vs prior 7 days: {avg_delta_vs_prior_7d} mmol/L ({trend_direction})
- Profile data coverage: {coverage_percent}% {coverage_flag}

## Upcoming Activity (from weekly pattern)
- Type: {activity_type} | Start: {start_time} | Duration: {duration_min} min

## Exercise History (last matching sessions for drop calculation)
{exercise_history}
- Session count available: {session_count}

## Today's Calories Burned So Far
{today_calories_burned} kcal

## Emotion Context (within last 2 hours)
{emotion_context}

## Additional Notes
{context_notes}

Calculate estimated_glucose_drop using the priority logic in Step 3, then reason through
all remaining steps and return your JSON assessment.
"""


async def reflector_node(state: AgentState) -> dict:
    """LLM clinical reasoning node. Populates risk assessment fields."""
    task = state["task"]
    profile = state.get("user_profile") or {}
    upcoming = state.get("upcoming_activity") or {}
    daily = state.get("glucose_daily_stats") or {}
    weekly = state.get("glucose_weekly_profile") or {}
    history = state.get("glucose_history_24h") or []
    exercise_hist = state.get("exercise_history") or []
    emotion = state.get("emotion_context") or {}

    # Compute glucose trend summary from recent readings
    glucose_trend_summary = _compute_trend_summary(history)

    # Derive helper strings
    realtime_flag = "(real-time estimate)" if daily.get("is_realtime") else ""
    cv = weekly.get("cv_percent", 0) or 0
    cv_interpretation = "stable" if cv < 36 else "high variability"
    delta = weekly.get("avg_delta_vs_prior_7d", 0) or 0
    trend_direction = "improving" if delta < 0 else ("worsening" if delta > 0 else "stable")
    coverage = weekly.get("coverage_percent", 0) or 0
    coverage_flag = "(low confidence — downweight this data)" if coverage < 50 else ""

    # Format exercise history
    ex_history_str = "\n".join(
        f"  - Session {i+1}: started {s.get('started_at')}, glucose_drop={s.get('glucose_drop')} mmol/L"
        for i, s in enumerate(exercise_hist)
    ) or "  No matching exercise history available"

    # Format emotion context
    emotion_str = (
        f"Emotion: {emotion.get('emotion_label', 'unknown')} "
        f"(recorded at {emotion.get('recorded_at', 'N/A')}, source: {emotion.get('source', 'N/A')})"
        if emotion.get("emotion_label") and emotion["emotion_label"] != "unknown"
        else "No recent emotion data available"
    )

    # Build user prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        user_id=task.get("user_id", ""),
        trigger_at=task.get("trigger_at", ""),
        current_glucose=task.get("current_glucose", "N/A"),
        current_hr=task.get("current_hr", "N/A"),
        location_context=state.get("location_context", "unknown"),
        trigger_type=task.get("trigger_type", ""),
        age=profile.get("age", "N/A"),
        bmi=profile.get("bmi", "N/A"),
        gender=profile.get("gender", "N/A"),
        waist_cm=profile.get("waist_cm", "N/A"),
        glucose_trend_summary=glucose_trend_summary,
        daily_avg=daily.get("avg_glucose", "N/A"),
        daily_peak=daily.get("peak_glucose", "N/A"),
        daily_nadir=daily.get("nadir_glucose", "N/A"),
        daily_sd=daily.get("glucose_sd", "N/A"),
        tir_today=daily.get("tir_percent", "N/A"),
        tbr_today=daily.get("tbr_percent", "N/A"),
        tar_today=daily.get("tar_percent", "N/A"),
        daily_data_points=daily.get("data_points", "N/A"),
        realtime_flag=realtime_flag,
        weekly_window_start=weekly.get("window_start", "N/A"),
        weekly_profile_date=weekly.get("profile_date", "N/A"),
        weekly_avg=weekly.get("avg_glucose", "N/A"),
        cv_percent=cv,
        cv_interpretation=cv_interpretation,
        weekly_tir=weekly.get("tir_percent", "N/A"),
        weekly_tbr=weekly.get("tbr_percent", "N/A"),
        weekly_tar=weekly.get("tar_percent", "N/A"),
        avg_delta_vs_prior_7d=delta,
        trend_direction=trend_direction,
        coverage_percent=coverage,
        coverage_flag=coverage_flag,
        activity_type=upcoming.get("type", "None"),
        start_time=upcoming.get("start_time", "N/A"),
        duration_min=upcoming.get("duration_min", "N/A"),
        exercise_history=ex_history_str,
        session_count=len(exercise_hist),
        today_calories_burned=state.get("today_calories_burned", 0),
        emotion_context=emotion_str,
        context_notes=task.get("context_notes", ""),
    )

    # Call LLM
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    try:
        llm = get_llm_reflector()
        response = await llm.ainvoke(messages)
        content = response.content.strip()
        
        logger.info("llm_reflector_raw", content=content)

        # Robust JSON extraction: look for outer braces
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1:
             content = content[start:end+1]

        result = json.loads(content)

        return {
            "estimated_glucose_drop": result.get("estimated_glucose_drop"),
            "risk_level": result.get("risk_level", "MEDIUM"),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "projected_glucose": result.get("projected_glucose"),
            "intervention_action": result.get("intervention_action", "SOFT_REMIND"),
            "supplement_recommendation": result.get("supplement_recommendation"),
            "reflector_confidence": result.get("confidence", "MEDIUM"),
        }
    except (json.JSONDecodeError, Exception) as e:
        logger.error("llm_parse_failed", error=str(e), fallback="rule_based")
        return _rule_based_fallback(task, upcoming)


def _compute_trend_summary(history: list) -> str:
    """Compute glucose slope from recent CGM readings and return a summary string."""
    if not history or len(history) < 2:
        return "Insufficient data for trend analysis"

    try:
        # Extract timestamps and values
        from datetime import datetime

        base_time = datetime.fromisoformat(history[0]["time"])
        timestamps = [
            (datetime.fromisoformat(r["time"]) - base_time).total_seconds() / 60.0
            for r in history
        ]
        values = [r["glucose"] for r in history]

        slope = float(np.polyfit(timestamps, values, 1)[0])
        direction = "falling" if slope < -0.05 else ("rising" if slope > 0.05 else "stable")
        return f"Slope: {slope:.4f} mmol/L/min ({direction}), based on {len(history)} readings"
    except (KeyError, ValueError, TypeError):
        return "Trend calculation failed — data format issue"


def _rule_based_fallback(task: dict, upcoming: dict | None) -> dict:
    """Fallback when LLM is unavailable or response is unparseable."""
    glucose = task.get("current_glucose", 5.0)

    if glucose < 4.5 and upcoming:
        return {
            "estimated_glucose_drop": None,
            "risk_level": "MEDIUM",
            "reasoning_summary": "LLM unavailable, rule-based fallback applied. "
            "Glucose below 4.5 with upcoming activity — recommending soft reminder.",
            "projected_glucose": None,
            "intervention_action": "SOFT_REMIND",
            "supplement_recommendation": "15g fast carbs: half a banana or 3 glucose tablets",
            "reflector_confidence": "LOW",
        }

    return {
        "estimated_glucose_drop": None,
        "risk_level": "LOW",
        "reasoning_summary": "LLM unavailable, rule-based fallback applied. No immediate risk detected.",
        "projected_glucose": None,
        "intervention_action": "NO_ACTION",
        "supplement_recommendation": None,
        "reflector_confidence": "LOW",
    }


# Required for json.loads in the try block above
import json
