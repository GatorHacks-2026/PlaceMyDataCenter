"""Explicit scenario math for a researched project; no demo regional inputs."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field


router = APIRouter()
HOURS_PER_YEAR = 8760


class ScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    it_capacity_mw: float = Field(gt=0, le=10000)
    utilization: float = Field(gt=0, le=1)
    pue: float = Field(ge=1, le=3)
    wue_l_per_kwh: float = Field(ge=0, le=20)
    grid_factor_kg_per_mwh: float | None = Field(default=None, ge=0, le=2000)


class ScenarioResponse(BaseModel):
    status: str = "modeled_scenario"
    it_energy_mwh_year: float
    facility_energy_mwh_year: float
    water_liters_year: float
    carbon_tonnes_year: float | None
    assumptions: ScenarioRequest


@router.post("/api/research/scenario", response_model=ScenarioResponse)
def calculate_scenario(request: ScenarioRequest) -> ScenarioResponse:
    it_energy = request.it_capacity_mw * HOURS_PER_YEAR * request.utilization
    facility_energy = it_energy * request.pue
    return ScenarioResponse(
        it_energy_mwh_year=it_energy,
        facility_energy_mwh_year=facility_energy,
        water_liters_year=it_energy * 1000 * request.wue_l_per_kwh,
        carbon_tonnes_year=(facility_energy * request.grid_factor_kg_per_mwh / 1000
                            if request.grid_factor_kg_per_mwh is not None else None),
        assumptions=request,
    )
