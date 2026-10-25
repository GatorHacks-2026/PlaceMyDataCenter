"""Versioned, source-linked contracts for data center research.

These models describe evidence. They do not fetch pages, extract facts, or
turn a reported facility capacity into an IT-power assumption.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from math import isfinite
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def finite_number(value: float) -> float:
    if not isfinite(value):
        raise ValueError("Numbers must be finite")
    return value


Number = Annotated[float, AfterValidator(finite_number)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EvidenceStatus(str, Enum):
    REPORTED = "reported"
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    CONFLICTING = "conflicting"
    NOT_FOUND = "not_found"


class ResearchStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"


class SourceType(str, Enum):
    NEWS = "news"
    COMPANY = "company"
    UTILITY = "utility"
    GOVERNMENT = "government"
    FILING = "filing"
    USER_SUPPLIED = "user_supplied"
    OTHER = "other"


class LocationPrecision(str, Enum):
    UNKNOWN = "unknown"
    STATE = "state"
    COUNTY = "county"
    CITY = "city"
    ZIP_AREA = "zip_area"
    ADDRESS = "address"
    PARCEL = "parcel"


class ClaimSubject(str, Enum):
    DATA_CENTER = "data_center"
    WIND_GENERATION = "wind_generation"
    SOLAR_GENERATION = "solar_generation"
    BATTERY_STORAGE = "battery_storage"
    GRID_CONNECTION = "grid_connection"
    GRID_SYSTEM = "grid_system"
    WATER_SYSTEM = "water_system"
    ENVIRONMENT = "environment"
    FINANCIAL = "financial"
    COMMUNITY = "community"
    OTHER = "other"


class CapacityKind(str, Enum):
    IT = "it"
    FACILITY = "facility"
    CONNECTION = "connection"
    UNKNOWN = "unknown"


class ProjectPhase(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    CONSTRUCTION = "construction"
    OPERATIONAL = "operational"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class Location(StrictModel):
    state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    county: str | None = None
    city: str | None = None
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    address: str | None = None
    latitude: Number | None = Field(default=None, ge=-90, le=90)
    longitude: Number | None = Field(default=None, ge=-180, le=180)
    precision: LocationPrecision = LocationPrecision.UNKNOWN

    @model_validator(mode="after")
    def coordinate_pair(self) -> Location:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must both be present or both absent")
        return self


class ProjectIdentity(StrictModel):
    name: str | None = None
    name_is_reported: bool = False
    developer: str | None = None
    operator: str | None = None
    aliases: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    phase: ProjectPhase = ProjectPhase.UNKNOWN
    announced_on: date | None = None


class SourceRecord(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: SourceType
    # Syndicated copies of one report share this origin, so they do not count
    # as independent verification merely because their URLs differ.
    independent_origin: str = Field(min_length=1)
    url: AnyHttpUrl | None = None
    published_on: date | None = None
    retrieved_at: datetime | None = None

    @model_validator(mode="after")
    def source_address(self) -> SourceRecord:
        if self.url is None and self.source_type != SourceType.USER_SUPPLIED:
            raise ValueError("A discovered source needs a URL")
        if self.retrieved_at is not None and self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        return self


class EvidenceRef(StrictModel):
    source_id: str = Field(min_length=1)
    excerpt: str = Field(min_length=1)
    locator: str | None = None


class Claim(StrictModel):
    id: str = Field(min_length=1)
    field: str = Field(min_length=1, description="Stable field key, e.g. electricity.capacity_mw")
    subject: ClaimSubject
    measure: str = Field(min_length=1, description="What was measured, e.g. power_capacity")
    value: Number | str | None = None
    unit: str | None = None
    status: EvidenceStatus
    capacity_kind: CapacityKind | None = None
    phase: ProjectPhase = ProjectPhase.UNKNOWN
    phase_label: str | None = None
    basis: str | None = None
    as_of: date | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent_claim(self) -> Claim:
        field_subjects = {
            "electricity.capacity_mw": ClaimSubject.DATA_CENTER,
            "energy_plan.wind_capacity_mw": ClaimSubject.WIND_GENERATION,
            "energy_plan.solar_capacity_mw": ClaimSubject.SOLAR_GENERATION,
            "energy_plan.battery_power_mw": ClaimSubject.BATTERY_STORAGE,
        }
        expected_subject = field_subjects.get(self.field)
        if expected_subject is not None and self.subject != expected_subject:
            raise ValueError(f"{self.field} requires subject {expected_subject.value}")
        if self.measure == "power_capacity":
            if self.unit != "MW":
                raise ValueError("Power capacity uses MW")
            if self.status != EvidenceStatus.NOT_FOUND and (
                not isinstance(self.value, float) or self.value <= 0
            ):
                raise ValueError("Found power capacity requires a positive MW number")
            if self.subject == ClaimSubject.DATA_CENTER and self.capacity_kind is None:
                raise ValueError("Data center MW requires an explicit capacity kind, including unknown")
            if self.subject != ClaimSubject.DATA_CENTER and self.capacity_kind is not None:
                raise ValueError("Capacity kind applies only to data center MW")
        elif self.capacity_kind is not None:
            raise ValueError("Capacity kind applies only to data center power capacity")

        if self.status == EvidenceStatus.NOT_FOUND:
            if self.value is not None or self.evidence:
                raise ValueError("Not-found claims cannot carry a value or evidence")
        elif self.status == EvidenceStatus.ESTIMATED:
            if self.value is None or not self.assumptions:
                raise ValueError("Estimated claims require a value and documented assumptions")
        elif self.value is None or not self.evidence:
            raise ValueError("Reported, verified, and conflicting claims need a value and evidence")
        return self


class ClaimConflict(StrictModel):
    id: str = Field(min_length=1)
    field: str = Field(min_length=1)
    claim_ids: list[str] = Field(min_length=2)
    explanation: str = Field(min_length=1)
    resolved: bool = False


class MissingField(StrictModel):
    field: str = Field(min_length=1)
    severity: str = Field(pattern=r"^(critical|warning|informational)$")
    why_it_matters: str = Field(min_length=1)
    checked_source_ids: list[str] = Field(default_factory=list)
    town_hall_question: str | None = None


class ResearchResult(StrictModel):
    schema_version: str = Field(default="1.0", pattern=r"^1\.\d+$")
    status: ResearchStatus
    location_input: str | None = None
    location_hint: Location | None = None
    location_source: Literal["user_input", "zippopotam"] | None = None
    project: ProjectIdentity | None = None
    candidates: list[ProjectIdentity] = Field(default_factory=list)
    sources: list[SourceRecord] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    conflicts: list[ClaimConflict] = Field(default_factory=list)
    missing_fields: list[MissingField] = Field(default_factory=list)
    summary: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_references(self) -> ResearchResult:
        source_by_id = {source.id: source for source in self.sources}
        claim_by_id = {claim.id: claim for claim in self.claims}
        if len(source_by_id) != len(self.sources):
            raise ValueError("Source IDs must be unique")
        if len(claim_by_id) != len(self.claims):
            raise ValueError("Claim IDs must be unique")

        for claim in self.claims:
            referenced = [ref.source_id for ref in claim.evidence]
            if any(source_id not in source_by_id for source_id in referenced):
                raise ValueError(f"Claim {claim.id} references an unknown source")
            if claim.status == EvidenceStatus.VERIFIED:
                origins = {source_by_id[source_id].independent_origin for source_id in referenced}
                if len(origins) < 2:
                    raise ValueError(f"Verified claim {claim.id} needs two independent origins")

        for conflict in self.conflicts:
            if len(set(conflict.claim_ids)) != len(conflict.claim_ids):
                raise ValueError(f"Conflict {conflict.id} repeats a claim")
            if any(claim_id not in claim_by_id for claim_id in conflict.claim_ids):
                raise ValueError(f"Conflict {conflict.id} references an unknown claim")
        for missing in self.missing_fields:
            if any(source_id not in source_by_id for source_id in missing.checked_source_ids):
                raise ValueError(f"Missing field {missing.field} references an unknown source")
        return self
