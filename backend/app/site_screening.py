"""Site screening adapter around the team's standalone calculation prototype.

Research claims are never changed here. The response identifies every assumed
input and keeps unavailable live layers separate from modeled results.
"""

from concurrent.futures import Future, ThreadPoolExecutor
from functools import lru_cache
import importlib.util
import logging
import math
import os
from pathlib import Path
import sys
from threading import Lock
from time import monotonic
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.area_boundary import state_at_point
from scripts.ecocompute_research.location import STATE_CODES


router = APIRouter()
logger = logging.getLogger("uvicorn.error")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="site-screening")
jobs: dict[str, tuple[float, Future[dict]]] = {}
jobs_lock = Lock()
JOB_TTL = 1800


@lru_cache(maxsize=1)
def engine():
    path = Path(__file__).resolve().parents[2] / "Data_Center_backend.py"
    spec = importlib.util.spec_from_file_location("data_center_calculator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Site calculator file is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SiteScreeningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    facility: Point
    home: Point | None = None
    state_hint: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    it_capacity_mw: float = Field(gt=0, le=10000)
    capacity_basis: Literal["reported_it", "hypothetical"]
    capacity_claim_id: str | None = None
    pue: float | None = Field(default=None, ge=1, le=3)
    load_factor: float | None = Field(default=None, gt=0, le=1)
    wue_l_per_kwh: float | None = Field(default=None, ge=0, le=20)
    radius_miles: float = Field(default=25, ge=1, le=100)


def _metric(value: float | int | None, digits: int = 2) -> float | None:
    return round(float(value), digits) if value is not None and math.isfinite(float(value)) else None


def _layer(status: str, values: dict, source: str, limitations: list[str], evidence: dict | None = None) -> dict:
    if status == "UNKNOWN" and ": " in source:
        source = source.split(": ", 1)[1]
    return {"status": status.lower() if status != "UNKNOWN" else "not_checked",
            "values": values, "source": source, "limitations": limitations,
            "evidence": evidence or {}}


def calculate(request: SiteScreeningRequest) -> dict:
    calculator = engine()
    state_source = "Census point lookup"
    try:
        state = state_at_point(request.facility.lat, request.facility.lng)
    except (httpx.HTTPError, ValueError):
        state = None
    if state is None:
        if request.state_hint not in STATE_CODES:
            raise ValueError("Could not determine a US state for the facility pin")
        state = request.state_hint
        state_source = "research state hint; pin state not independently verified"
    if state not in STATE_CODES:
        raise ValueError("Facility pin is outside a supported US state")
    warnings = []
    if request.state_hint and state != request.state_hint:
        warnings.append(f"The pin is in {state}, outside the researched state {request.state_hint}.")
    if state_source != "Census point lookup":
        warnings.append("The state containing the pin could not be verified; check the pin before relying on local factors.")

    cfg = {"STATE": state, "LAT": request.facility.lat, "LON": request.facility.lng,
           "IT_MW": request.it_capacity_mw, "RADIUS_MILES": request.radius_miles}
    for name, value in (("PUE", request.pue), ("LOAD_FACTOR", request.load_factor),
                        ("WUE", request.wue_l_per_kwh)):
        if value is not None:
            cfg[name] = value
    distance_m = None
    if request.home:
        distance_m = calculator.miles(request.facility.lat, request.facility.lng,
                                      request.home.lat, request.home.lng) * calculator.MI
        cfg["HOUSE_DIST_M"] = max(1.0, distance_m)

    key = os.environ.get("EIA_API_KEY", "")
    def power_fetch(c):
        if not key:
            raise RuntimeError("EIA_API_KEY is not configured")
        return calculator.fetch_power(c, key)

    result = calculator.run(cfg, power_fetch=power_fetch,
                            river_fetch=lambda c: calculator.fetch_river(c, os.environ.get("API_USGS_PAT", "")))
    facility, power, water, carbon, model_noise = (result[name] for name in
                                             ("facility", "power", "water", "carbon", "noise"))
    noise = model_noise
    if distance_m is None:
        noise = {"status": "UNKNOWN", "error": "Place a home pin to estimate sound at that point"}
    water_gauges = []
    if water["status"] != "UNKNOWN":
        selected_gauge = str(water["big_row"].get("site", ""))
        for row in water["table"].to_dict("records"):
            lat, lng = _metric(row.get("lat"), 6), _metric(row.get("lng"), 6)
            if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180):
                continue
            water_gauges.append({
                "id": str(row["site"]), "name": str(row.get("name") or row["site"]),
                "lat": lat, "lng": lng, "distance_miles": _metric(row.get("miles")),
                "dry_flow_mgd": _metric(row.get("p10")),
                "selected_for_comparison": str(row["site"]) == selected_gauge,
            })
    noise_radius = (_metric(model_noise.get("safe_distance_night_m") / calculator.MI, 3)
                    if model_noise["status"] != "UNKNOWN" else None)
    assumptions = {name.lower(): result["cfg"][name] for name in
                   ("PUE", "LOAD_FACTOR", "WUE", "GEN_HOURS", "TAKE_PCT", "LOSS_PCT", "BARRIER_DB")}
    assumed_names = [name.lower() for name in ("PUE", "LOAD_FACTOR", "WUE", "GEN_HOURS", "TAKE_PCT", "LOSS_PCT", "BARRIER_DB")
                     if name not in cfg]
    layers = {
        "power": _layer(power["status"], {} if power["status"] == "UNKNOWN" else {
            "monthly_proxy_mw": _metric(power["worst_kw"] / 1000),
            "average_facility_demand_mw": _metric(power["need_kw"] / 1000),
            "weakest_month": str(power["worst_month"]),
        }, "EIA monthly state generation and retail sales" if power["status"] != "UNKNOWN" else power["error"],
            ["State generation minus retail sales, area-scaled, is an energy proxy, not available grid connection capacity."],
            {} if power["status"] == "UNKNOWN" else {
                "source_url": "https://www.eia.gov/opendata/", "sample_period": f"{power['evidence'].get('first', '?')} to {power['evidence'].get('last', '?')}",
                "retrieved_at": power["evidence"].get("fetched_at"),
            }),
        "water": _layer(water["status"], {} if water["status"] == "UNKNOWN" else {
            "river": water["river"], "dry_flow_mgd": _metric(water["p10_mgd"]),
            "peak_facility_need_mgd": _metric(water["need_mgd"], 3),
            "assumed_usable_flow_mgd": _metric(water["assumed_take_mgd"], 3),
        }, "USGS nearby discharge gauges" if water["status"] != "UNKNOWN" else water["error"],
            ["A nearby river is not a verified water source or water right; usable flow uses an assumed percentage."],
            {} if water["status"] == "UNKNOWN" else {
                "source_url": "https://api.waterdata.usgs.gov/ogcapi/v1",
                "gauge_id": water["big_row"].get("site"),
                "gauge_distance_miles": _metric(water["big_row"].get("miles")),
                "sample_period": f"{water['evidence'].get('first', '?')} to {water['evidence'].get('last', '?')}",
                "retrieved_at": water["evidence"].get("fetched_at"),
            }),
        "carbon": _layer(carbon["status"], {} if carbon["status"] == "UNKNOWN" else {
            "annual_tco2e": _metric(carbon["total_location_t"], 0),
            "grid_kg_per_mwh": _metric(carbon["factor_kg_mwh"], 1),
            "diesel_tco2e": _metric(carbon["scope1_t"], 0),
        }, carbon.get("factor_src", carbon.get("error", "EPA eGRID 2023")),
            ["Uses a fixed eGRID 2023 factor; generator size and hours are assumed."],
            {"source_url": "https://www.epa.gov/egrid"} if carbon["status"] != "UNKNOWN" else {}),
        "noise": _layer(noise["status"], {} if noise["status"] == "UNKNOWN" else {
            "at_home_dba": _metric(noise["level_dba"], 1),
            "distance_m": _metric(distance_m, 0),
            "assumed_night_limit_dba": result["cfg"]["LIMIT_NIGHT"],
        }, "Distance model with assumed equipment" if noise["status"] != "UNKNOWN" else noise["error"],
            ["Equipment counts, sound levels, barriers, and the comparison limit are assumptions, not measured local impacts."]),
    }
    return {
        "status": "partial" if any(layer["status"] == "not_checked" for layer in layers.values()) else "screened",
        "site": {"state": state, "state_source": state_source,
                 "lat": request.facility.lat, "lng": request.facility.lng},
        "input": {"it_capacity_mw": request.it_capacity_mw, "capacity_basis": request.capacity_basis,
                  "capacity_claim_id": request.capacity_claim_id, "home_distance_m": _metric(distance_m, 0),
                  "radius_miles": request.radius_miles},
        "facility": {"peak_mw": _metric(facility["fac_peak_mw"]),
                     "average_mw": _metric(facility["fac_avg_mw"]),
                     "annual_mwh": _metric(facility["annual_mwh"], 0),
                     "peak_water_mgd": _metric(facility["water_need_mgd"], 3)},
        "assumptions": assumptions, "defaulted_assumptions": assumed_names,
        "layers": layers, "warnings": warnings,
        "map_overlays": {
            "usgs_search_radius_miles": request.radius_miles,
            "water_gauges": water_gauges,
            "noise_threshold": ({"radius_miles": noise_radius,
                                 "threshold_dba": result["cfg"]["LIMIT_NIGHT"]}
                                if noise_radius is not None and noise_radius > 0 else None),
        },
    }


@router.post("/api/site-screening/jobs", status_code=202)
def submit(request: SiteScreeningRequest) -> dict:
    with jobs_lock:
        now = monotonic()
        for key, (created, future) in list(jobs.items()):
            if future.done() and now - created > JOB_TTL:
                del jobs[key]
        if sum(not future.done() for _, future in jobs.values()) >= 4:
            raise HTTPException(429, "Site screening queue is full; retry shortly")
        job_id = uuid4().hex
        jobs[job_id] = (now, executor.submit(calculate, request))
    return {"job_id": job_id, "status": "queued"}


@router.get("/api/site-screening/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with jobs_lock:
        entry = jobs.get(job_id)
    if entry is None:
        raise HTTPException(404, "Site screening job was not found or has expired")
    future = entry[1]
    if not future.done():
        return {"job_id": job_id, "status": "running" if future.running() else "queued"}
    try:
        result = future.result()
    except ValueError as exc:
        return {"job_id": job_id, "status": "failed", "error": str(exc)}
    except Exception:
        logger.exception("site screening failed job_id=%s", job_id)
        return {"job_id": job_id, "status": "failed", "error": "Site screening failed; check backend logs"}
    return {"job_id": job_id, "status": "complete", "result": result}
