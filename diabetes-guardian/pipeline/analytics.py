"""
pipeline/analytics.py

Pure computation functions for glucose profile aggregation.
No scheduler, no side effects beyond DB writes.
Input:  user_cgm_log (read-only)
Output: user_glucose_daily_stats + user_glucose_weekly_profile (upsert)

This module must NOT import anything from gateway / agent / mcp_servers.
"""

import sys
from datetime import date, datetime, time, timedelta

import numpy as np
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ErrorLog,
    UserCGMLog,
    UserGlucoseDailyStats,
    UserGlucoseWeeklyProfile,
)

logger = structlog.get_logger(__name__)

# Expected readings per day at 10-min intervals
_READINGS_PER_DAY = 144
_READINGS_PER_WEEK = _READINGS_PER_DAY * 7  # 1008


async def build_daily_stats(
    session: AsyncSession,
    user_id: str,
    stat_date: date,
) -> None:
    """
    Compute rolling 1-day stats for a given user and date.
    Upserts one row into user_glucose_daily_stats.
    """
    day_start = datetime.combine(stat_date, time(0, 0))
    day_end = datetime.combine(stat_date + timedelta(days=1), time(0, 0))

    result = await session.execute(
        select(UserCGMLog.glucose).where(
            UserCGMLog.user_id == user_id,
            UserCGMLog.recorded_at >= day_start,
            UserCGMLog.recorded_at < day_end,
        )
    )
    values = [float(r[0]) for r in result.all()]

    if not values:
        return  # No data for this day

    arr = np.array(values)
    n = len(arr)

    row_data = {
        "user_id": user_id,
        "stat_date": stat_date,
        "avg_glucose": round(float(np.mean(arr)), 2),
        "peak_glucose": round(float(np.max(arr)), 2),
        "nadir_glucose": round(float(np.min(arr)), 2),
        "glucose_sd": round(float(np.std(arr)), 2),
        "tir_percent": round(float(np.sum((arr >= 3.9) & (arr <= 10.0)) / n * 100), 1),
        "tbr_percent": round(float(np.sum(arr < 3.9) / n * 100), 1),
        "tar_percent": round(float(np.sum(arr > 10.0) / n * 100), 1),
        "data_points": n,
        "is_realtime": False,
    }

    # PostgreSQL upsert (INSERT ... ON CONFLICT DO UPDATE)
    stmt = pg_insert(UserGlucoseDailyStats).values(**row_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "stat_date"],
        set_={k: v for k, v in row_data.items() if k not in ("user_id", "stat_date")},
    )
    await session.execute(stmt)
    await session.commit()


async def build_weekly_profile(
    session: AsyncSession,
    user_id: str,
    profile_date: date,
) -> None:
    """
    Compute 7-day sliding window profile ending on profile_date.
    Reads from user_glucose_daily_stats (7 rows), not raw CGM.
    """
    window_start = profile_date - timedelta(days=6)

    result = await session.execute(
        select(UserGlucoseDailyStats).where(
            UserGlucoseDailyStats.user_id == user_id,
            UserGlucoseDailyStats.stat_date >= window_start,
            UserGlucoseDailyStats.stat_date <= profile_date,
        )
    )
    rows = result.scalars().all()

    if not rows:
        return

    # Aggregate from daily rows
    all_avg = [float(r.avg_glucose) for r in rows if r.avg_glucose]
    all_peak = [float(r.peak_glucose) for r in rows if r.peak_glucose]
    all_nadir = [float(r.nadir_glucose) for r in rows if r.nadir_glucose]
    total_points = sum(r.data_points or 0 for r in rows)

    if not all_avg:
        return

    avg_glucose = round(np.mean(all_avg), 2)
    sd = round(float(np.std(all_avg)), 2)
    cv = round(sd / avg_glucose * 100, 1) if avg_glucose > 0 else 0.0

    # Weighted TIR/TBR/TAR from daily stats
    total_dp = sum(r.data_points or 0 for r in rows)
    if total_dp > 0:
        tir = round(sum((r.tir_percent or 0) * (r.data_points or 0) for r in rows) / total_dp, 1)
        tbr = round(sum((r.tbr_percent or 0) * (r.data_points or 0) for r in rows) / total_dp, 1)
        tar = round(sum((r.tar_percent or 0) * (r.data_points or 0) for r in rows) / total_dp, 1)
    else:
        tir = tbr = tar = 0.0

    # Calculate avg_delta_vs_prior_7d
    prior_start = window_start - timedelta(days=7)
    prior_end = window_start - timedelta(days=1)
    prior_result = await session.execute(
        select(func.avg(UserGlucoseDailyStats.avg_glucose)).where(
            UserGlucoseDailyStats.user_id == user_id,
            UserGlucoseDailyStats.stat_date >= prior_start,
            UserGlucoseDailyStats.stat_date <= prior_end,
        )
    )
    prior_avg = prior_result.scalar_one_or_none()
    avg_delta = round(avg_glucose - float(prior_avg), 2) if prior_avg else None

    coverage = round(total_points / _READINGS_PER_WEEK * 100, 1)

    row_data = {
        "user_id": user_id,
        "profile_date": profile_date,
        "window_start": window_start,
        "avg_glucose": avg_glucose,
        "peak_glucose": round(max(all_peak), 2) if all_peak else None,
        "nadir_glucose": round(min(all_nadir), 2) if all_nadir else None,
        "glucose_sd": sd,
        "cv_percent": cv,
        "tir_percent": tir,
        "tbr_percent": tbr,
        "tar_percent": tar,
        "avg_delta_vs_prior_7d": avg_delta,
        "data_points": total_points,
        "coverage_percent": coverage,
    }

    stmt = pg_insert(UserGlucoseWeeklyProfile).values(**row_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "profile_date"],
        set_={k: v for k, v in row_data.items() if k not in ("user_id", "profile_date")},
    )
    await session.execute(stmt)
    await session.commit()


async def run_nightly(session: AsyncSession | None = None) -> None:
    """
    Nightly entry point called by scheduler.
    1. Fetch all distinct user_ids active in the past 7 days
    2. For each user: build_daily_stats(yesterday) → build_weekly_profile(today)
    3. Errors logged, one user failure doesn't block others
    """
    from db.session import AsyncSessionLocal

    should_close = session is None
    if session is None:
        session = AsyncSessionLocal()

    try:
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        week_ago = today - timedelta(days=7)

        # Get active users
        result = await session.execute(
            select(UserCGMLog.user_id.distinct()).where(
                UserCGMLog.recorded_at >= datetime.combine(week_ago, time(0, 0))
            )
        )
        user_ids = [r[0] for r in result.all()]

        logger.info("nightly_pipeline_started", user_count=len(user_ids))

        for uid in user_ids:
            try:
                await build_daily_stats(session, uid, yesterday)
                await build_weekly_profile(session, uid, today)
                logger.info("nightly_user_done", user_id=uid)
            except Exception as e:
                logger.error("nightly_user_failed", user_id=uid, error=str(e))
                error = ErrorLog(
                    service="pipeline",
                    error_msg=str(e),
                    payload=f"user_id={uid}",
                )
                session.add(error)
                await session.commit()

        logger.info("nightly_pipeline_completed", user_count=len(user_ids))
    finally:
        if should_close:
            await session.close()


async def run_backfill(user_id: str) -> None:
    """
    Backfill daily stats and weekly profile for all available dates.
    Used after seed_demo.py to generate historical profile data.
    """
    from db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # Find date range for this user
        result = await session.execute(
            select(
                func.min(UserCGMLog.recorded_at),
                func.max(UserCGMLog.recorded_at),
            ).where(UserCGMLog.user_id == user_id)
        )
        row = result.one()
        if row[0] is None:
            logger.warning("backfill_no_data", user_id=user_id)
            return

        start_date = row[0].date()
        end_date = row[1].date()

        logger.info("backfill_started", user_id=user_id, start=str(start_date), end=str(end_date))

        # Build daily stats for each day
        current = start_date
        while current <= end_date:
            try:
                await build_daily_stats(session, user_id, current)
            except Exception as e:
                logger.error("backfill_daily_failed", user_id=user_id, date=str(current), error=str(e))
            current += timedelta(days=1)

        # Build weekly profiles
        current = start_date + timedelta(days=6)
        while current <= end_date:
            try:
                await build_weekly_profile(session, user_id, current)
            except Exception as e:
                logger.error("backfill_weekly_failed", user_id=user_id, date=str(current), error=str(e))
            current += timedelta(days=1)

        logger.info("backfill_completed", user_id=user_id)
