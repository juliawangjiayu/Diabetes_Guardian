"""
agent/tools/location_context_tool.py

Location Context Tool.
Resolves GPS coordinates to semantic location using user_known_places.
Uses Haversine distance with 200m threshold.
"""

import math

import structlog
from sqlalchemy import select

from db.models import UserKnownPlace
from db.session import AsyncSessionLocal
from gateway.constants import KNOWN_PLACE_RADIUS_M

logger = structlog.get_logger(__name__)


async def get_semantic_location(user_id: str, lat: float, lng: float) -> dict:
    """Resolve GPS to semantic location using user's known places."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserKnownPlace).where(UserKnownPlace.user_id == user_id)
        )
        places = result.scalars().all()

    nearby: list[dict] = []
    is_at_home = False

    for place in places:
        if place.gps_lat is None or place.gps_lng is None:
            continue

        distance_m = _haversine_m(
            lat, lng,
            float(place.gps_lat), float(place.gps_lng),
        )

        if distance_m <= KNOWN_PLACE_RADIUS_M:
            nearby.append({
                "name": place.place_name,
                "distance_m": int(distance_m),
                "type": place.place_type,
            })
            if place.place_type == "home":
                is_at_home = True

    # Build semantic location string
    if not nearby:
        semantic = "unknown location"
    elif len(nearby) == 1:
        p = nearby[0]
        semantic = f"Near {p['name']} ({p['type']}, {p['distance_m']}m away)"
    else:
        names = ", ".join(p["name"] for p in nearby[:3])
        semantic = f"Near {names}"

    return {
        "semantic_location": semantic,
        "is_at_home": is_at_home,
        "nearby_known_places": nearby,
    }


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two GPS points in metres."""
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
