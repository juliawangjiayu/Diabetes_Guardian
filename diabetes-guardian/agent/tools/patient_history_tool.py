"""
agent/tools/patient_history_tool.py

Patient History Tool.
Provides patient context data to the Agent layer.
Reads from PostgreSQL: user profile, CGM history, exercise history,
upcoming activities, daily stats, and weekly profile.
"""

import asyncio
from datetime import date, datetime, time, timedelta
from typing import Optional

import numpy as np
import structlog
from sqlalchemy import func, select

from db.models import (
    User,
    UserCGMLog,
    UserExerciseLog,
    UserGlucoseDailyStats,
    UserGlucoseWeeklyProfile,
    UserWeeklyPattern,
)
from db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)


async def get_patient_context(user_id: str, reference_time: str | datetime = "") -> dict:
    """Return full patient context for Investigator node directly as a Python dict."""
    if isinstance(reference_time, str):
        ref_time = datetime.fromisoformat(reference_time) if reference_time else datetime.now()
    else:
        ref_time = reference_time

    # Fetch all data concurrently
    (
        profile,
        glucose_24h,
        upcoming,
        exercise_hist,
        today_kcal,
        daily_stats,
        weekly_profile,
    ) = await asyncio.gather(
        _get_user_profile(user_id),
        _get_glucose_history_24h(user_id, ref_time),
        _get_upcoming_activity(user_id, ref_time),
        _get_exercise_history(user_id, ref_time),
        _get_today_calories(user_id, ref_time),
        _get_daily_stats(user_id, ref_time),
        _get_weekly_profile(user_id),
    )

    return {
        "user_profile": profile,
        "glucose_history_24h": glucose_24h,
        "upcoming_activity": upcoming,
        "exercise_history": exercise_hist,
        "today_calories_burned": today_kcal,
        "glucose_daily_stats": daily_stats,
        "glucose_weekly_profile": weekly_profile,
    }



async def _get_user_profile(user_id: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
    if user is None:
        return None
    return {
        "age": user.age,
        "bmi": user.bmi,
        "gender": user.gender,
        "waist_cm": float(user.waist_cm) if user.waist_cm else None,
    }


async def _get_glucose_history_24h(user_id: str, ref_time: datetime) -> list[dict]:
    cutoff = ref_time - timedelta(hours=24)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserCGMLog)
            .where(UserCGMLog.user_id == user_id, UserCGMLog.recorded_at >= cutoff)
            .order_by(UserCGMLog.recorded_at.asc())
        )
        rows = result.scalars().all()
    return [
        {"time": r.recorded_at.isoformat(), "glucose": float(r.glucose)}
        for r in rows
    ]


async def _get_upcoming_activity(
    user_id: str, ref_time: datetime
) -> dict | None:
    day_of_week = ref_time.weekday()
    current_time = ref_time.time()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserWeeklyPattern)
            .where(
                UserWeeklyPattern.user_id == user_id,
                UserWeeklyPattern.day_of_week == day_of_week,
                UserWeeklyPattern.start_time >= current_time,
            )
            .order_by(UserWeeklyPattern.start_time.asc())
            .limit(1)
        )
        pattern = result.scalar_one_or_none()
    if pattern is None:
        return None

    start_dt = datetime.combine(ref_time.date(), pattern.start_time)
    end_dt = datetime.combine(ref_time.date(), pattern.end_time)
    duration_min = int((end_dt - start_dt).total_seconds() / 60)

    return {
        "type": pattern.activity_type,
        "start_time": pattern.start_time.strftime("%H:%M"),
        "end_time": pattern.end_time.strftime("%H:%M"),
        "duration_min": duration_min,
    }


async def _get_exercise_history(
    user_id: str, ref_time: datetime
) -> list[dict]:
    """
    Get last 3 exercise sessions matching the upcoming activity type.
    For each session, compute glucose_drop = CGM at start minus min CGM in [start, end+2h].
    """
    # First find upcoming activity type
    upcoming = await _get_upcoming_activity(user_id, ref_time)
    if upcoming is None:
        return []

    activity_type = upcoming["type"]

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserExerciseLog)
            .where(
                UserExerciseLog.user_id == user_id,
                UserExerciseLog.exercise_type == activity_type,
                UserExerciseLog.started_at < ref_time,
            )
            .order_by(UserExerciseLog.started_at.desc())
            .limit(3)
        )
        sessions = result.scalars().all()

    history = []
    for ex in sessions:
        # Compute glucose drop for this session
        glucose_drop = await _compute_glucose_drop(
            user_id, ex.started_at, ex.ended_at
        )
        history.append({
            "started_at": ex.started_at.isoformat(),
            "ended_at": ex.ended_at.isoformat(),
            "glucose_drop": glucose_drop,
        })
    return history


async def _compute_glucose_drop(
    user_id: str,
    started_at: datetime,
    ended_at: datetime,
) -> float | None:
    """CGM value at started_at minus min CGM in [started_at, ended_at + 2h]."""
    window_end = ended_at + timedelta(hours=2)
    async with AsyncSessionLocal() as session:
        # Get CGM closest to start
        result_start = await session.execute(
            select(UserCGMLog.glucose)
            .where(
                UserCGMLog.user_id == user_id,
                UserCGMLog.recorded_at >= started_at - timedelta(minutes=10),
                UserCGMLog.recorded_at <= started_at + timedelta(minutes=10),
            )
            .order_by(func.abs(
                func.extract('epoch', UserCGMLog.recorded_at - started_at)
            ))
            .limit(1)
        )
        start_glucose_row = result_start.scalar_one_or_none()

        # Get min CGM during session + 2h
        result_min = await session.execute(
            select(func.min(UserCGMLog.glucose)).where(
                UserCGMLog.user_id == user_id,
                UserCGMLog.recorded_at >= started_at,
                UserCGMLog.recorded_at <= window_end,
            )
        )
        min_glucose = result_min.scalar_one_or_none()

    if start_glucose_row is None or min_glucose is None:
        return None

    return round(float(start_glucose_row) - float(min_glucose), 2)


async def _get_today_calories(user_id: str, ref_time: datetime) -> float:
    today_start = datetime.combine(ref_time.date(), time(0, 0))
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.coalesce(func.sum(UserExerciseLog.calories_burned), 0)).where(
                UserExerciseLog.user_id == user_id,
                UserExerciseLog.started_at >= today_start,
            )
        )
        return float(result.scalar_one())


async def _get_daily_stats(user_id: str, ref_time: datetime) -> dict | None:
    """
    Get today's daily stats. If pipeline hasn't run yet, compute on-the-fly.
    """
    today = ref_time.date()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserGlucoseDailyStats).where(
                UserGlucoseDailyStats.user_id == user_id,
                UserGlucoseDailyStats.stat_date == today,
            )
        )
        row = result.scalar_one_or_none()

    if row is not None:
        return _daily_stats_to_dict(row)

    # Fallback: compute on-the-fly with 2s timeout
    try:
        return await asyncio.wait_for(
            _compute_realtime_daily_stats(user_id, today),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        logger.warning("realtime_daily_stats_timeout", user_id=user_id)
        return None


async def _compute_realtime_daily_stats(user_id: str, stat_date: date) -> dict | None:
    """Compute daily stats on the fly from raw CGM data."""
    day_start = datetime.combine(stat_date, time(0, 0))
    day_end = datetime.combine(stat_date + timedelta(days=1), time(0, 0))

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserCGMLog.glucose).where(
                UserCGMLog.user_id == user_id,
                UserCGMLog.recorded_at >= day_start,
                UserCGMLog.recorded_at < day_end,
            )
        )
        values = [float(r[0]) for r in result.all()]

    if not values:
        return None

    arr = np.array(values)
    return {
        "stat_date": str(stat_date),
        "avg_glucose": round(float(np.mean(arr)), 2),
        "peak_glucose": round(float(np.max(arr)), 2),
        "nadir_glucose": round(float(np.min(arr)), 2),
        "glucose_sd": round(float(np.std(arr)), 2),
        "tir_percent": round(float(np.sum((arr >= 3.9) & (arr <= 10.0)) / len(arr) * 100), 1),
        "tbr_percent": round(float(np.sum(arr < 3.9) / len(arr) * 100), 1),
        "tar_percent": round(float(np.sum(arr > 10.0) / len(arr) * 100), 1),
        "data_points": len(values),
        "is_realtime": True,
    }


async def _get_weekly_profile(user_id: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserGlucoseWeeklyProfile)
            .where(UserGlucoseWeeklyProfile.user_id == user_id)
            .order_by(UserGlucoseWeeklyProfile.profile_date.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()

    if row is None:
        return None

    return {
        "profile_date": str(row.profile_date),
        "window_start": str(row.window_start),
        "avg_glucose": float(row.avg_glucose) if row.avg_glucose else None,
        "peak_glucose": float(row.peak_glucose) if row.peak_glucose else None,
        "nadir_glucose": float(row.nadir_glucose) if row.nadir_glucose else None,
        "glucose_sd": float(row.glucose_sd) if row.glucose_sd else None,
        "cv_percent": float(row.cv_percent) if row.cv_percent else None,
        "tir_percent": float(row.tir_percent) if row.tir_percent else None,
        "tbr_percent": float(row.tbr_percent) if row.tbr_percent else None,
        "tar_percent": float(row.tar_percent) if row.tar_percent else None,
        "avg_delta_vs_prior_7d": float(row.avg_delta_vs_prior_7d) if row.avg_delta_vs_prior_7d else None,
        "data_points": row.data_points,
        "coverage_percent": float(row.coverage_percent) if row.coverage_percent else None,
    }


def _daily_stats_to_dict(row) -> dict:
    return {
        "stat_date": str(row.stat_date),
        "avg_glucose": float(row.avg_glucose) if row.avg_glucose else None,
        "peak_glucose": float(row.peak_glucose) if row.peak_glucose else None,
        "nadir_glucose": float(row.nadir_glucose) if row.nadir_glucose else None,
        "glucose_sd": float(row.glucose_sd) if row.glucose_sd else None,
        "tir_percent": float(row.tir_percent) if row.tir_percent else None,
        "tbr_percent": float(row.tbr_percent) if row.tbr_percent else None,
        "tar_percent": float(row.tar_percent) if row.tar_percent else None,
        "data_points": row.data_points,
        "is_realtime": row.is_realtime,
    }
