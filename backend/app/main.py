"""Deterministic estimate API. Values remain modeled/demo assumptions."""

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from app.investigation import router as investigation_router

HOURS_PER_YEAR = 8760
logger = logging.getLogger("uvicorn.error")
COOLING_PRESETS = {
    "Evaporative": (1.2, 1.8),
    "Hybrid": (1.35, 0.9),
    "Dry": (1.5, 0.12),
}


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state: str = Field(min_length=1)
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)
    gridFactorKgPerMWh: float = Field(ge=0)
    droughtRisk: Literal["Low", "Moderate", "High", "Unknown"]
    source: Literal["preset", "search"] | None = None


class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    location: Location
    capacityMW: float = Field(ge=10, le=300)
    utilization: float = Field(ge=0.3, le=1.0)
    cooling: Literal["Evaporative", "Hybrid", "Dry"]


class Metrics(BaseModel):
    facilityEnergyMWhYear: float
    itEnergyMWhYear: float
    waterLitersYear: float
    carbonTonnesYear: float
    droughtRisk: Literal["Low", "Moderate", "High", "Unknown"]


class Assumptions(BaseModel):
    pue: float
    wueLPerKwh: float
    utilization: float
    gridFactorKgPerMWh: float


class EstimateResponse(BaseModel):
    metrics: Metrics
    assumptions: Assumptions


app = FastAPI(title="EcoCompute API")
app.include_router(investigation_router)


@app.post("/api/estimate", response_model=EstimateResponse)
def estimate(request: EstimateRequest) -> EstimateResponse:
    started = perf_counter()
    pue, wue = COOLING_PRESETS[request.cooling]
    it_energy = request.capacityMW * HOURS_PER_YEAR * request.utilization
    facility_energy = it_energy * pue
    result = EstimateResponse(
        metrics=Metrics(
            facilityEnergyMWhYear=facility_energy,
            itEnergyMWhYear=it_energy,
            waterLitersYear=it_energy * 1000 * wue,
            carbonTonnesYear=facility_energy * request.location.gridFactorKgPerMWh / 1000,
            droughtRisk=request.location.droughtRisk,
        ),
        assumptions=Assumptions(
            pue=pue,
            wueLPerKwh=wue,
            utilization=request.utilization,
            gridFactorKgPerMWh=request.location.gridFactorKgPerMWh,
        ),
    )
    # Log only the estimate payload. Future auth headers and tokens stay out of logs.
    logger.info(
        "estimate at=%s status=200 duration_ms=%.2f request=%s response=%s",
        datetime.now(timezone.utc).isoformat(),
        (perf_counter() - started) * 1000,
        request.model_dump_json(exclude_none=True),
        result.model_dump_json(),
    )
    return result
