"""
db/models.py

SQLAlchemy 2.0 async ORM model definitions.
Maps to the tables defined in db/init.sql.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import settings

# Async engine with connection pool settings
engine = create_async_engine(
    f"mysql+aiomysql://{settings.mysql_user}:{settings.mysql_password}"
    f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class User(Base):
    """User profile with demographic information."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class UserTelemetryLog(Base):
    """Raw telemetry data received from user devices."""

    __tablename__ = "user_telemetry_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    glucose: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    gps_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    gps_lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)


class UserWeeklyPattern(Base):
    """Aggregated weekly behavior patterns for activity prediction."""

    __tablename__ = "user_weekly_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hour_of_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    probability: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    avg_glucose_drop: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class UserKnownPlace(Base):
    """Known locations for semantic location resolution."""

    __tablename__ = "user_known_places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    place_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    place_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gps_lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    gps_lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)


class InterventionLog(Base):
    """Records of triggered interventions and messages sent to users."""

    __tablename__ = "intervention_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    agent_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_sent: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_ack: Mapped[bool | None] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class ErrorLog(Base):
    """System error log for monitoring and debugging."""

    __tablename__ = "error_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)
