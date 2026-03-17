"""
gateway/routers/crud.py

REST endpoints for the Test Dashboard (spec §14).
Provides CRUD for user profile, weekly patterns, known places,
emergency contacts, emotion log, and read-only log views.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from db.models import (
    User,
    UserCGMLog,
    UserEmergencyContact,
    UserEmotionLog,
    UserExerciseLog,
    UserGlucoseDailyStats,
    UserGlucoseWeeklyProfile,
    UserHRLog,
    UserKnownPlace,
    UserWeeklyPattern,
    InterventionLog,
)
from db.session import AsyncSessionLocal

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["crud"])


# ── Pydantic schemas for CRUD ──────────────────────────────────

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    birth_year: Optional[int] = None
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    waist_cm: Optional[float] = None


class WeeklyPatternCreate(BaseModel):
    day_of_week: int
    start_time: str  # "HH:MM:SS"
    end_time: str
    activity_type: str


class KnownPlaceCreate(BaseModel):
    place_name: str
    place_type: str
    gps_lat: float
    gps_lng: float


class EmergencyContactCreate(BaseModel):
    contact_name: str
    phone_number: str
    relationship: Optional[str] = None
    notify_on: list[str]  # ["hard_low_glucose", "hard_high_hr", "data_gap"]


class EmergencyContactUpdate(BaseModel):
    contact_name: Optional[str] = None
    phone_number: Optional[str] = None
    relationship: Optional[str] = None
    notify_on: Optional[list[str]] = None


# ── User Profile ───────────────────────────────────────────────

@router.put("/users/{user_id}")
async def upsert_user(user_id: str, body: UserProfileUpdate) -> dict:
    """Create or overwrite user profile."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(user_id=user_id)
            session.add(user)

        for field, value in body.model_dump(exclude_none=True).items():
            setattr(user, field, value)

        await session.commit()
        await session.refresh(user)

        return {
            "user_id": user.user_id,
            "name": user.name,
            "birth_year": user.birth_year,
            "gender": user.gender,
            "weight_kg": float(user.weight_kg) if user.weight_kg else None,
            "height_cm": float(user.height_cm) if user.height_cm else None,
            "waist_cm": float(user.waist_cm) if user.waist_cm else None,
            "bmi": user.bmi,
            "age": user.age,
        }


@router.get("/users/{user_id}")
async def get_user(user_id: str) -> dict:
    """Fetch user profile."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user.user_id,
        "name": user.name,
        "birth_year": user.birth_year,
        "gender": user.gender,
        "weight_kg": float(user.weight_kg) if user.weight_kg else None,
        "height_cm": float(user.height_cm) if user.height_cm else None,
        "waist_cm": float(user.waist_cm) if user.waist_cm else None,
        "bmi": user.bmi,
        "age": user.age,
    }


# ── Weekly Patterns ────────────────────────────────────────────

@router.get("/users/{user_id}/weekly-patterns")
async def list_weekly_patterns(user_id: str) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserWeeklyPattern).where(UserWeeklyPattern.user_id == user_id)
        )
        patterns = result.scalars().all()
    return [
        {
            "id": p.id,
            "day_of_week": p.day_of_week,
            "start_time": str(p.start_time),
            "end_time": str(p.end_time),
            "activity_type": p.activity_type,
        }
        for p in patterns
    ]


@router.post("/users/{user_id}/weekly-patterns")
async def create_weekly_pattern(user_id: str, body: WeeklyPatternCreate) -> dict:
    from datetime import time as dt_time

    async with AsyncSessionLocal() as session:
        parts_start = body.start_time.split(":")
        parts_end = body.end_time.split(":")
        record = UserWeeklyPattern(
            user_id=user_id,
            day_of_week=body.day_of_week,
            start_time=dt_time(int(parts_start[0]), int(parts_start[1])),
            end_time=dt_time(int(parts_end[0]), int(parts_end[1])),
            activity_type=body.activity_type,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return {"id": record.id, "status": "created"}


@router.delete("/users/{user_id}/weekly-patterns/{pattern_id}")
async def delete_weekly_pattern(user_id: str, pattern_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(UserWeeklyPattern).where(
                UserWeeklyPattern.id == pattern_id,
                UserWeeklyPattern.user_id == user_id,
            )
        )
        await session.commit()
    return {"status": "deleted"}


# ── Known Places ───────────────────────────────────────────────

@router.get("/users/{user_id}/known-places")
async def list_known_places(user_id: str) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserKnownPlace).where(UserKnownPlace.user_id == user_id)
        )
        places = result.scalars().all()
    return [
        {
            "id": p.id,
            "place_name": p.place_name,
            "place_type": p.place_type,
            "gps_lat": float(p.gps_lat) if p.gps_lat else None,
            "gps_lng": float(p.gps_lng) if p.gps_lng else None,
        }
        for p in places
    ]


@router.post("/users/{user_id}/known-places")
async def create_known_place(user_id: str, body: KnownPlaceCreate) -> dict:
    async with AsyncSessionLocal() as session:
        record = UserKnownPlace(
            user_id=user_id,
            place_name=body.place_name,
            place_type=body.place_type,
            gps_lat=body.gps_lat,
            gps_lng=body.gps_lng,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return {"id": record.id, "status": "created"}


@router.delete("/users/{user_id}/known-places/{place_id}")
async def delete_known_place(user_id: str, place_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(UserKnownPlace).where(
                UserKnownPlace.id == place_id,
                UserKnownPlace.user_id == user_id,
            )
        )
        await session.commit()
    return {"status": "deleted"}


# ── Emergency Contacts ─────────────────────────────────────────

@router.get("/users/{user_id}/emergency-contacts")
async def list_emergency_contacts(user_id: str) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserEmergencyContact).where(
                UserEmergencyContact.user_id == user_id
            )
        )
        contacts = result.scalars().all()
    return [
        {
            "id": c.id,
            "contact_name": c.contact_name,
            "phone_number": c.phone_number,
            "relationship": c.relationship,
            "notify_on": c.notify_on,
        }
        for c in contacts
    ]


@router.post("/users/{user_id}/emergency-contacts")
async def create_emergency_contact(user_id: str, body: EmergencyContactCreate) -> dict:
    async with AsyncSessionLocal() as session:
        record = UserEmergencyContact(
            user_id=user_id,
            contact_name=body.contact_name,
            phone_number=body.phone_number,
            relationship=body.relationship,
            notify_on=body.notify_on,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return {"id": record.id, "status": "created"}


@router.delete("/users/{user_id}/emergency-contacts/{contact_id}")
async def delete_emergency_contact(user_id: str, contact_id: int) -> dict:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(UserEmergencyContact).where(
                UserEmergencyContact.id == contact_id,
                UserEmergencyContact.user_id == user_id,
            )
        )
        await session.commit()
    return {"status": "deleted"}


@router.put("/users/{user_id}/emergency-contacts/{contact_id}")
async def update_emergency_contact(user_id: str, contact_id: int, body: EmergencyContactUpdate) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserEmergencyContact).where(
                UserEmergencyContact.id == contact_id,
                UserEmergencyContact.user_id == user_id,
            )
        )
        contact = result.scalar_one_or_none()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        for field, value in body.model_dump(exclude_none=True).items():
            setattr(contact, field, value)

        await session.commit()
    return {"status": "updated"}


# ── Emotion Log ────────────────────────────────────────────────

@router.get("/users/{user_id}/emotion-log")
async def list_emotion_log(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserEmotionLog)
            .where(UserEmotionLog.user_id == user_id)
            .order_by(UserEmotionLog.recorded_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "recorded_at": l.recorded_at.isoformat(),
            "emotion_label": l.emotion_label,
            "source": l.source,
        }
        for l in logs
    ]


# ── Read-only Log Views ───────────────────────────────────────

@router.get("/users/{user_id}/cgm-log")
async def list_cgm_log(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserCGMLog)
            .where(UserCGMLog.user_id == user_id)
            .order_by(UserCGMLog.recorded_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "recorded_at": l.recorded_at.isoformat(),
            "glucose": float(l.glucose),
        }
        for l in logs
    ]


@router.get("/users/{user_id}/hr-log")
async def list_hr_log(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserHRLog)
            .where(UserHRLog.user_id == user_id)
            .order_by(UserHRLog.recorded_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "recorded_at": l.recorded_at.isoformat(),
            "heart_rate": l.heart_rate,
            "gps_lat": float(l.gps_lat) if l.gps_lat else None,
            "gps_lng": float(l.gps_lng) if l.gps_lng else None,
        }
        for l in logs
    ]


@router.get("/users/{user_id}/exercise-log")
async def list_exercise_log(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserExerciseLog)
            .where(UserExerciseLog.user_id == user_id)
            .order_by(UserExerciseLog.started_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "exercise_type": l.exercise_type,
            "started_at": l.started_at.isoformat(),
            "ended_at": l.ended_at.isoformat(),
            "avg_heart_rate": l.avg_heart_rate,
            "calories_burned": float(l.calories_burned) if l.calories_burned else None,
        }
        for l in logs
    ]


@router.get("/users/{user_id}/intervention-log")
async def list_intervention_log(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(InterventionLog)
            .where(InterventionLog.user_id == user_id)
            .order_by(InterventionLog.triggered_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "triggered_at": l.triggered_at.isoformat(),
            "trigger_type": l.trigger_type,
            "display_label": l.display_label,
            "agent_decision": l.agent_decision,
            "message_sent": l.message_sent,
            "user_ack": l.user_ack,
        }
        for l in logs
    ]


@router.get("/users/{user_id}/glucose-daily-stats")
async def list_glucose_daily_stats(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserGlucoseDailyStats)
            .where(UserGlucoseDailyStats.user_id == user_id)
            .order_by(UserGlucoseDailyStats.stat_date.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "stat_date": str(r.stat_date),
            "avg_glucose": float(r.avg_glucose) if r.avg_glucose else None,
            "peak_glucose": float(r.peak_glucose) if r.peak_glucose else None,
            "nadir_glucose": float(r.nadir_glucose) if r.nadir_glucose else None,
            "glucose_sd": float(r.glucose_sd) if r.glucose_sd else None,
            "tir_percent": float(r.tir_percent) if r.tir_percent else None,
            "tbr_percent": float(r.tbr_percent) if r.tbr_percent else None,
            "tar_percent": float(r.tar_percent) if r.tar_percent else None,
            "data_points": r.data_points,
            "is_realtime": r.is_realtime,
        }
        for r in rows
    ]


@router.get("/users/{user_id}/glucose-weekly-profile")
async def list_glucose_weekly_profile(user_id: str, limit: int = Query(20, ge=1, le=200)) -> list[dict]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserGlucoseWeeklyProfile)
            .where(UserGlucoseWeeklyProfile.user_id == user_id)
            .order_by(UserGlucoseWeeklyProfile.profile_date.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "profile_date": str(r.profile_date),
            "window_start": str(r.window_start),
            "avg_glucose": float(r.avg_glucose) if r.avg_glucose else None,
            "peak_glucose": float(r.peak_glucose) if r.peak_glucose else None,
            "nadir_glucose": float(r.nadir_glucose) if r.nadir_glucose else None,
            "glucose_sd": float(r.glucose_sd) if r.glucose_sd else None,
            "cv_percent": float(r.cv_percent) if r.cv_percent else None,
            "tir_percent": float(r.tir_percent) if r.tir_percent else None,
            "tbr_percent": float(r.tbr_percent) if r.tbr_percent else None,
            "tar_percent": float(r.tar_percent) if r.tar_percent else None,
            "avg_delta_vs_prior_7d": float(r.avg_delta_vs_prior_7d) if r.avg_delta_vs_prior_7d else None,
            "data_points": r.data_points,
            "coverage_percent": float(r.coverage_percent) if r.coverage_percent else None,
        }
        for r in rows
    ]
