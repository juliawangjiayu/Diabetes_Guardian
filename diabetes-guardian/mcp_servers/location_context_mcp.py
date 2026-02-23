"""
mcp_servers/location_context_mcp.py

Location Context MCP Server (port 8002).
Resolves GPS coordinates to semantic locations using user-defined known places.
This is an independent FastAPI process; it must not import gateway/ or agent/ modules.
"""

import math
from typing import Optional

import structlog
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from config import settings

logger = structlog.get_logger(__name__)

# Known place radius threshold in meters (duplicated here to avoid cross-layer import)
KNOWN_PLACE_RADIUS_M: int = 200

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
    title="Location Context MCP Server",
    description="Resolves GPS coordinates to semantic locations",
    version="1.0.0",
)

# Earth radius in meters for Haversine calculation
_EARTH_RADIUS_M: int = 6_371_000


# ── Request / Response models ────────────────────────────────

class SemanticLocationRequest(BaseModel):
    """Request body for get_semantic_location tool."""

    user_id: str
    lat: float
    lng: float


class NearbyPlace(BaseModel):
    """A known place near the user's current location."""

    name: str
    distance_m: int
    type: str


class SemanticLocationResponse(BaseModel):
    """Response body for get_semantic_location tool."""

    semantic_location: str
    is_at_home: bool
    nearby_known_places: list[NearbyPlace]


# ── Haversine distance calculation per agent.md Section 7.3 ──

def haversine_distance(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> int:
    """
    Calculate the great-circle distance between two points in meters.

    Uses the Haversine formula with Earth radius = 6,371,000 meters.
    Returns distance as an integer (meters).
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return int(2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a)))


# ── Tool endpoint ────────────────────────────────────────────

@app.post("/tools/get_semantic_location", response_model=SemanticLocationResponse)
async def get_semantic_location(
    request: SemanticLocationRequest,
) -> SemanticLocationResponse:
    """
    Resolve GPS coordinates to a semantic location description.

    Queries user_known_places, calculates distances via Haversine,
    and determines if the user is at a known location (within KNOWN_PLACE_RADIUS_M).
    """
    nearby_places: list[NearbyPlace] = []
    is_at_home: bool = False
    semantic_location: str = "未知位置"

    async with _async_session() as session:
        result = await session.execute(
            text(
                "SELECT place_name, place_type, gps_lat, gps_lng "
                "FROM user_known_places "
                "WHERE user_id = :uid"
            ),
            {"uid": request.user_id},
        )
        rows = result.fetchall()

        for row in rows:
            place_name, place_type, place_lat, place_lng = row
            if place_lat is None or place_lng is None:
                continue

            distance = haversine_distance(
                request.lat, request.lng,
                float(place_lat), float(place_lng),
            )

            nearby_places.append(
                NearbyPlace(
                    name=place_name or "unnamed",
                    distance_m=distance,
                    type=place_type or "unknown",
                )
            )

            # Check if user is at this known place
            if distance <= KNOWN_PLACE_RADIUS_M:
                semantic_location = f"在{place_name}中"
                if place_type == "home":
                    is_at_home = True

    # Sort by distance, keep closest first
    nearby_places.sort(key=lambda p: p.distance_m)

    # If not at any known place, describe nearest one
    if semantic_location == "未知位置" and nearby_places:
        nearest = nearby_places[0]
        semantic_location = f"距离{nearest.name} {nearest.distance_m} 米"

    logger.info(
        "semantic_location_resolved",
        user_id=request.user_id,
        semantic_location=semantic_location,
        nearby_count=len(nearby_places),
        is_at_home=is_at_home,
    )

    return SemanticLocationResponse(
        semantic_location=semantic_location,
        is_at_home=is_at_home,
        nearby_known_places=nearby_places[:5],  # Limit to 5 nearest
    )
