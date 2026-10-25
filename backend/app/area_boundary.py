"""Approximate research-area outlines and state lookup from Census TIGERweb."""

from functools import lru_cache

import httpx
from fastapi import APIRouter, HTTPException, Query

from scripts.ecocompute_research.location import STATE_CODES


router = APIRouter()
TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_TAB2020"
ZCTA_LAYER = f"{TIGER}/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/3/query"
STATE_LAYER = f"{TIGER}/State_County/MapServer/7/query"


def _query(url: str, **params: str) -> dict:
    response = httpx.get(url, params={"f": "geojson", "outFields": "*", "outSR": "4326",
                                      "returnGeometry": "true", **params}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Census did not return GeoJSON")
    return payload


@lru_cache(maxsize=256)
def zcta_boundary(zip_code: str) -> dict | None:
    features = _query(ZCTA_LAYER, where=f"GEOID='{zip_code}'").get("features", [])
    return features[0] if features else None


@lru_cache(maxsize=64)
def state_boundary(state: str) -> dict | None:
    features = _query(STATE_LAYER, where=f"STUSAB='{state}'").get("features", [])
    return features[0] if features else None


def state_at_point(lat: float, lon: float) -> str | None:
    features = _query(STATE_LAYER, geometry=f"{lon},{lat}", geometryType="esriGeometryPoint",
                      inSR="4326", spatialRel="esriSpatialRelIntersects").get("features", [])
    if not features:
        return None
    state = features[0].get("properties", {}).get("STUSAB")
    return state if state in STATE_CODES else None


@router.get("/api/areas/zip/{zip_code}")
def get_zcta(zip_code: str) -> dict:
    if len(zip_code) != 5 or not zip_code.isdigit():
        raise HTTPException(422, "Use a five-digit ZIP code")
    try:
        feature = zcta_boundary(zip_code)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Area outline is temporarily unavailable") from exc
    if feature is None:
        raise HTTPException(404, "No Census ZCTA outline exists for this ZIP")
    return {"feature": feature, "precision": "approximate_zcta", "source": "US Census TIGERweb 2020 ZCTA"}


@router.get("/api/areas/state/{state}")
def get_state(state: str) -> dict:
    state = state.upper()
    if state not in STATE_CODES:
        raise HTTPException(422, "Use a valid two-letter state code")
    try:
        feature = state_boundary(state)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Area outline is temporarily unavailable") from exc
    if feature is None:
        raise HTTPException(404, "State outline was not found")
    return {"feature": feature, "precision": "state", "source": "US Census TIGERweb 2020 states"}
