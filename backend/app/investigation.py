"""Location and pasted-document intake; extraction is integrated separately."""

import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

router = APIRouter()

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}
STATE_CODES = set(STATE_NAMES.values())


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=2, max_length=120)
    document_text: str = Field(min_length=20, max_length=20_000)

    @field_validator("location", "document_text", mode="before")
    @classmethod
    def strip_nonempty(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("This field cannot be blank.")
        return value


class ResolvedLocation(BaseModel):
    input: str
    kind: Literal["zip", "city_state", "state"]
    display: str
    precision: Literal["zip_area", "city", "state"]


class DocumentPreview(BaseModel):
    text: str
    character_count: int
    word_count: int


class SectionStatus(BaseModel):
    status: Literal["awaiting_integration"] = "awaiting_integration"
    message: str


class InvestigationPreview(BaseModel):
    location: ResolvedLocation
    document: DocumentPreview
    extraction: SectionStatus
    environmental_context: SectionStatus


def state_code(value: str) -> str | None:
    normalized = " ".join(value.strip().lower().split())
    if normalized.upper() in STATE_CODES:
        return normalized.upper()
    return STATE_NAMES.get(normalized)


def resolve_location(raw: str) -> ResolvedLocation:
    value = " ".join(raw.strip().split())
    if re.fullmatch(r"\d{5}", value):
        return ResolvedLocation(input=raw, kind="zip", display=f"ZIP {value}", precision="zip_area")

    code = state_code(value)
    if code:
        return ResolvedLocation(input=raw, kind="state", display=code, precision="state")

    if "," in value:
        city, state = (part.strip() for part in value.rsplit(",", 1))
        code = state_code(state)
        if city and re.fullmatch(r"[\w .'-]+", city) and code:
            return ResolvedLocation(
                input=raw, kind="city_state", display=f"{city}, {code}", precision="city"
            )

    raise HTTPException(
        status_code=422,
        detail="Enter a 5-digit US ZIP, a city and state (for example, Gainesville, FL), or a state.",
    )


@router.post("/api/investigations/preview", response_model=InvestigationPreview)
def preview_investigation(request: InvestigationRequest) -> InvestigationPreview:
    location = resolve_location(request.location)
    return InvestigationPreview(
        location=location,
        document=DocumentPreview(
            text=request.document_text,
            character_count=len(request.document_text),
            word_count=len(request.document_text.split()),
        ),
        extraction=SectionStatus(message="Document extraction will appear here after the team integration."),
        environmental_context=SectionStatus(
            message="Environmental factors will appear here after the team integration."
        ),
    )
