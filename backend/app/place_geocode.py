"""User-triggered, cached city lookup for approximate research map placement."""

from threading import Lock
from time import monotonic, sleep

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from scripts.ecocompute_research.location import STATE_NAMES


router = APIRouter()
_lock = Lock()
_cache: dict[tuple[str, str], "CityPoint"] = {}
_last_request = 0.0


class AreaPoint(BaseModel):
    city: str | None
    state: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precision: str
    boundary: dict | None = None
    attribution: str = "© OpenStreetMap contributors"


@router.get("/api/research/geocode", response_model=AreaPoint)
def geocode_city(city: str | None = Query(default=None, min_length=2, max_length=80),
                 state: str = Query(pattern=r"^[A-Z]{2}$")) -> AreaPoint:
    global _last_request
    state_name = next((name for name, abbreviation in STATE_NAMES.items()
                       if abbreviation == state), None)
    if not state_name:
        raise HTTPException(422, "Unknown US state")
    city = city.strip() if city else None
    key = ((city or "").casefold(), state)
    with _lock:
        if key in _cache:
            return _cache[key]
        pause = 1.05 - (monotonic() - _last_request)
        if pause > 0:
            sleep(pause)
        _last_request = monotonic()
        try:
            response = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={**({"city": city} if city else {}), "state": state_name, "country": "United States",
                        "countrycodes": "us", "format": "jsonv2", "addressdetails": 1,
                        "limit": 3, "polygon_geojson": 1, "polygon_threshold": 0.001},
                headers={"User-Agent": "EcoComputeAI/0.1 (local research map; contact: github.com/PlaceMyDataCenter)",
                         "Accept-Language": "en"}, timeout=10,
            )
            response.raise_for_status()
            places = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "City lookup is temporarily unavailable") from exc
        for place in places:
            address = place.get("address") or {}
            name = address.get("city") or address.get("town") or address.get("village")
            city_matches = bool(city and name and name.casefold() == city.casefold())
            state_matches = bool(not city and address.get("state", "").casefold() == state_name.casefold())
            if address.get("country_code") == "us" and (city_matches or state_matches):
                geometry = place.get("geojson")
                boundary = geometry if isinstance(geometry, dict) and geometry.get("type") in {"Polygon", "MultiPolygon"} else None
                point = AreaPoint(city=city, state=state, boundary=boundary,
                                  latitude=float(place["lat"]), longitude=float(place["lon"]),
                                  precision="city" if city else "state")
                _cache[key] = point
                return point
    raise HTTPException(404, "No matching city was found")
