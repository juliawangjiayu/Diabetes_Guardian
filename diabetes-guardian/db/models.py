"""
db/models.py

SQLAlchemy ORM models for all database tables.
BMI and age are computed as @property — never stored in the database.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Text,
    Time,
)
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase


import enum

class ExerciseType(str, enum.Enum):
    resistance_training = "resistance_training"
    cardio = "cardio"
    hiit = "hiit"

class ActivityType(str, enum.Enum):
    resistance_training = "resistance_training"
    cardio = "cardio"
    hiit = "hiit"

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True)
    name = Column(String(100))
    birth_year = Column(Integer)
    gender = Column(Enum("male", "female", "other", native_enum=False, length=10))
    waist_cm = Column(Numeric(5, 1))
    weight_kg = Column(Numeric(5, 1))
    height_cm = Column(Numeric(5, 1))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def bmi(self) -> float | None:
        """Compute BMI on the fly from weight and height."""
        if self.weight_kg and self.height_cm:
            return round(float(self.weight_kg) / (float(self.height_cm) / 100) ** 2, 1)
        return None

    @property
    def age(self) -> int | None:
        """Compute age from birth_year."""
        if self.birth_year:
            return datetime.now().year - self.birth_year
        return None


class UserCGMLog(Base):
    __tablename__ = "user_cgm_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    glucose = Column(Numeric(5, 2), nullable=False)


class UserHRLog(Base):
    __tablename__ = "user_hr_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    heart_rate = Column(Integer, nullable=False)
    gps_lat = Column(Numeric(10, 7))
    gps_lng = Column(Numeric(10, 7))


class UserExerciseLog(Base):
    __tablename__ = "user_exercise_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    exercise_type = Column(Enum(ExerciseType, native_enum=False, length=50), nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=False)
    avg_heart_rate = Column(Integer)
    calories_burned = Column(Numeric(7, 1))


class UserWeeklyPattern(Base):
    __tablename__ = "user_weekly_patterns"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    activity_type = Column(Enum(ActivityType, native_enum=False, length=50), nullable=False)


class UserKnownPlace(Base):
    __tablename__ = "user_known_places"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    place_name = Column(String(100))
    place_type = Column(String(50))
    gps_lat = Column(Numeric(10, 7))
    gps_lng = Column(Numeric(10, 7))


class UserEmotionLog(Base):
    __tablename__ = "user_emotion_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    user_input = Column(Text, nullable=False)
    emotion_label = Column(String(50), nullable=False)
    source = Column(String(50), default="meralion")


class UserEmotionSummary(Base):
    __tablename__ = "user_emotion_summary"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    summary_date = Column(Date, nullable=False)
    summary_text = Column(Text, nullable=False)
    primary_emotion = Column(String(50))


class UserFoodLog(Base):
    __tablename__ = "user_food_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    food_name = Column(String(100), nullable=False)
    meal_type = Column(String(10), nullable=False)
    gi_level = Column(String(10), nullable=False)
    total_calories = Column(Numeric(6, 1), nullable=False)


class DynamicTaskLog(Base):
    __tablename__ = "dynamic_task_log"

    task_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    task_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    task_status = Column(String(20), nullable=False, default="pending")
    target_lat = Column(Numeric(10, 7))
    target_lng = Column(Numeric(10, 7))
    completed_at = Column(DateTime)
    expired_at = Column(DateTime)
    reward_points = Column(Integer, default=0)


class DynamicTaskRule(Base):
    __tablename__ = "dynamic_task_rule"

    rule_id = Column(Integer, primary_key=True, autoincrement=True)
    base_calorie = Column(Integer, nullable=False, default=300)
    trigger_threshold = Column(Numeric(3, 2), nullable=False, default=0.60)
    is_active = Column(Integer, nullable=False, default=1)


class RoutineTaskLog(Base):
    __tablename__ = "routine_task_log"

    task_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    task_type = Column(String(50), nullable=False)
    period = Column(String(20), nullable=False)
    task_status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    expired_at = Column(DateTime)
    reward_points = Column(Integer, default=0)


class RewardLog(Base):
    __tablename__ = "reward_log"

    user_id = Column(String(36), primary_key=True)
    total_points = Column(Integer, nullable=False, default=0)
    accumulated_points = Column(Integer, nullable=False, default=0)
    consumed_points = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserEmergencyContact(Base):
    __tablename__ = "user_emergency_contacts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    contact_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=False)
    relationship = Column(String(50))
    notify_on = Column(JSON, nullable=False)


class InterventionLog(Base):
    __tablename__ = "intervention_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    triggered_at = Column(DateTime, nullable=False)
    trigger_type = Column(String(50))
    display_label = Column(String(50))
    agent_decision = Column(Text)
    message_sent = Column(Text)
    user_ack = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)


class ErrorLog(Base):
    __tablename__ = "error_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    service = Column(String(50))
    error_msg = Column(Text)
    payload = Column(Text)
    ts = Column(DateTime, default=datetime.now)


class UserGlucoseDailyStats(Base):
    __tablename__ = "user_glucose_daily_stats"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    stat_date = Column(Date, nullable=False)
    avg_glucose = Column(Numeric(5, 2))
    peak_glucose = Column(Numeric(5, 2))
    nadir_glucose = Column(Numeric(5, 2))
    glucose_sd = Column(Numeric(5, 2))
    tir_percent = Column(Numeric(5, 1))
    tbr_percent = Column(Numeric(5, 1))
    tar_percent = Column(Numeric(5, 1))
    data_points = Column(Integer)
    is_realtime = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class UserGlucoseWeeklyProfile(Base):
    __tablename__ = "user_glucose_weekly_profile"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False)
    profile_date = Column(Date, nullable=False)
    window_start = Column(Date, nullable=False)
    avg_glucose = Column(Numeric(5, 2))
    peak_glucose = Column(Numeric(5, 2))
    nadir_glucose = Column(Numeric(5, 2))
    glucose_sd = Column(Numeric(5, 2))
    cv_percent = Column(Numeric(5, 1))
    tir_percent = Column(Numeric(5, 1))
    tbr_percent = Column(Numeric(5, 1))
    tar_percent = Column(Numeric(5, 1))
    avg_delta_vs_prior_7d = Column(Numeric(5, 2))
    data_points = Column(Integer)
    coverage_percent = Column(Numeric(5, 1))
    created_at = Column(DateTime, default=datetime.now)
