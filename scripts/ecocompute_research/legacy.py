"""Conservative projection for the prototype's flat activeSite fields."""

from typing import Literal

from pydantic import Field

from .models import (
    CapacityKind,
    ClaimSubject,
    EvidenceStatus,
    LocationPrecision,
    ResearchResult,
    StrictModel,
)


class ActiveSiteCompatibility(StrictModel):
    """Nullable flat fields for consumers migrating from ActiveSiteContract.

    Downstream calculations must inspect capacity_kind. A reported connection
    or unknown-kind MW figure is not automatically an IT capacity input.
    """

    input_mode: Literal["url", "text", "pdf", "manual_location"]
    zip_code: str | None = None
    city: str | None = None
    county: str | None = None
    state: str | None = None
    lat: float | None = None
    lon: float | None = None
    is_statewide_mode: bool = False
    egrid_lb_mwh: float | None = None
    stated_mw: float | None = None
    capacity_kind: CapacityKind | None = None
    estimated_mw: float | None = None
    scale_source: str | None = None
    building_sqft: float | None = None
    capex_millions: float | None = None
    acreage: float | None = None
    cooling_type: str | None = None
    claimed_water_gpd: float | None = None
    missing_fields: list[str] = Field(default_factory=list)


def to_active_site(
    result: ResearchResult,
    *,
    input_mode: Literal["url", "text", "pdf", "manual_location"],
) -> ActiveSiteCompatibility:
    """Expose only unambiguous reported facility fields, never demo defaults."""
    location = result.project.location if result.project else None
    unresolved_capacity = any(
        not conflict.resolved and conflict.field == "electricity.capacity_mw"
        for conflict in result.conflicts
    )
    reported_capacity = [
        claim for claim in result.claims
        if claim.field == "electricity.capacity_mw"
        and claim.subject == ClaimSubject.DATA_CENTER
        and claim.measure == "power_capacity"
        and claim.status in {EvidenceStatus.REPORTED, EvidenceStatus.VERIFIED}
    ]
    selected = reported_capacity[0] if len(reported_capacity) == 1 and not unresolved_capacity else None

    return ActiveSiteCompatibility(
        input_mode=input_mode,
        zip_code=location.zip_code if location else None,
        city=location.city if location else None,
        county=location.county if location else None,
        state=location.state if location else None,
        lat=location.latitude if location else None,
        lon=location.longitude if location else None,
        is_statewide_mode=bool(location and location.precision == LocationPrecision.STATE),
        stated_mw=float(selected.value) if selected else None,
        capacity_kind=selected.capacity_kind if selected else None,
        scale_source=(
            ", ".join(ref.source_id for ref in selected.evidence) if selected else None
        ),
        missing_fields=[missing.field for missing in result.missing_fields],
    )
