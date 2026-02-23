"""
mcp_servers/patient_history_mcp.py

Patient History MCP Server (port 8001).
Provides tools for querying patient telemetry history and generating NL2SQL queries.
This is an independent FastAPI process; it must not import gateway/ or agent/ modules.
"""

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings

logger = structlog.get_logger(__name__)

# Database connection for this MCP server
_engine = create_async_engine(
    f"mysql+aiomysql://{settings.mysql_user}:{settings.mysql_password}"
    f"@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}",
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
_async_session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

app = FastAPI(
    title="Patient History MCP Server",
    description="Provides patient telemetry history and NL2SQL tools",
    version="1.0.0",
)

# ── Forbidden SQL keywords per agent.md Section 7.2 ─────────
FORBIDDEN_KEYWORDS: set[str] = {
    "drop", "delete", "update", "insert", "alter", "truncate", "create",
}
SQL_MAX_LENGTH: int = 2000


# ── Request / Response models ────────────────────────────────

class PatientContextRequest(BaseModel):
    """Request body for get_patient_context tool."""

    user_id: str
    reference_time: str


class GlucoseRecord(BaseModel):
    """Single glucose reading with timestamp."""

    time: str
    glucose: float


class UpcomingActivity(BaseModel):
    """Predicted upcoming activity from weekly patterns."""

    type: str
    probability: float
    expected_start_hour: int
    avg_glucose_drop: float


class PatientContextResponse(BaseModel):
    """Response body for get_patient_context tool."""

    glucose_history_24h: list[GlucoseRecord]
    upcoming_activity: Optional[UpcomingActivity]
    recent_exercise_drops: list[float]


class NL2SQLRequest(BaseModel):
    """Request body for nl2sql_query tool."""

    user_id: str
    natural_language_query: str


class NL2SQLResponse(BaseModel):
    """Response body for nl2sql_query tool."""

    result: list
    sql_executed: str


# ── SQL validation ───────────────────────────────────────────

def validate_sql(sql: str) -> None:
    """
    Validate generated SQL for safety constraints.

    Raises ValueError if SQL contains forbidden keywords or exceeds length limit.
    """
    lower = sql.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw in lower:
            raise ValueError(f"Forbidden SQL operation: {kw}")
    if len(sql) > SQL_MAX_LENGTH:
        raise ValueError("SQL exceeds maximum length limit")


# ── Tool endpoints ───────────────────────────────────────────

@app.post("/tools/get_patient_context", response_model=PatientContextResponse)
async def get_patient_context(
    request: PatientContextRequest,
) -> PatientContextResponse:
    """
    Retrieve patient context including 24h glucose history,
    upcoming predicted activities, and recent exercise glucose drops.
    """
    try:
        ref_time = datetime.fromisoformat(request.reference_time)
    except ValueError:
        ref_time = datetime.utcnow()

    cutoff_24h = ref_time - timedelta(hours=24)

    async with _async_session() as session:
        # Fetch 24h glucose history
        result = await session.execute(
            text(
                "SELECT recorded_at, glucose FROM user_telemetry_log "
                "WHERE user_id = :uid AND recorded_at >= :cutoff "
                "ORDER BY recorded_at DESC LIMIT 1000"
            ),
            {"uid": request.user_id, "cutoff": cutoff_24h},
        )
        rows = result.fetchall()
        glucose_history = [
            GlucoseRecord(time=str(row[0]), glucose=float(row[1]))
            for row in rows
            if row[1] is not None
        ]

        # Fetch upcoming activity predictions
        current_dow = ref_time.weekday()
        current_hour = ref_time.hour
        activity_result = await session.execute(
            text(
                "SELECT activity_type, probability, hour_of_day, avg_glucose_drop "
                "FROM user_weekly_patterns "
                "WHERE user_id = :uid AND day_of_week = :dow "
                "AND hour_of_day BETWEEN :h_start AND :h_end "
                "AND probability >= 0.5 "
                "ORDER BY probability DESC LIMIT 1"
            ),
            {
                "uid": request.user_id,
                "dow": current_dow,
                "h_start": current_hour,
                "h_end": min(current_hour + 2, 23),
            },
        )
        activity_row = activity_result.fetchone()
        upcoming_activity = None
        if activity_row:
            upcoming_activity = UpcomingActivity(
                type=activity_row[0],
                probability=float(activity_row[1]),
                expected_start_hour=int(activity_row[2]),
                avg_glucose_drop=float(activity_row[3] or 0),
            )

        # Fetch recent exercise glucose drops (last 7 days)
        week_ago = ref_time - timedelta(days=7)
        drops_result = await session.execute(
            text(
                "SELECT avg_glucose_drop FROM user_weekly_patterns "
                "WHERE user_id = :uid AND avg_glucose_drop IS NOT NULL "
                "ORDER BY id DESC LIMIT 5"
            ),
            {"uid": request.user_id},
        )
        drops_rows = drops_result.fetchall()
        recent_drops = [float(row[0]) for row in drops_rows]

    logger.info(
        "patient_context_served",
        user_id=request.user_id,
        history_count=len(glucose_history),
        has_upcoming_activity=upcoming_activity is not None,
    )

    return PatientContextResponse(
        glucose_history_24h=glucose_history,
        upcoming_activity=upcoming_activity,
        recent_exercise_drops=recent_drops,
    )


@app.post("/tools/nl2sql_query", response_model=NL2SQLResponse)
async def nl2sql_query(request: NL2SQLRequest) -> NL2SQLResponse:
    """
    Execute a natural language query translated to SQL.

    Safety: only SELECT statements are allowed; writes are rejected with 400.
    """
    # TODO: Integrate LLM-based NL2SQL translation
    # For now, this is a stub that returns an error
    raise HTTPException(
        status_code=501,
        detail="NL2SQL feature not yet implemented",
    )
