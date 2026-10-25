"""Parse a user-supplied US place without guessing its coordinates."""

from __future__ import annotations

import re

from .models import Location, LocationPrecision


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
STATE_CODES = frozenset(STATE_NAMES.values())
PLACE = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
ADDRESS_START = re.compile(r"^\d+[A-Za-z]?\s+\S+")


class LocationInputError(ValueError):
    """The place cannot be parsed without guessing."""


def state_code(value: str) -> str | None:
    normalized = " ".join(value.strip().lower().split())
    if normalized.upper() in STATE_CODES:
        return normalized.upper()
    return STATE_NAMES.get(normalized)


def parse_location(raw: str) -> Location:
    """Parse syntax only; no external geocoding or geographic verification.

    ZIPs stay ZIP areas, cities stay cities, and address text stays an address.
    County, ZIP, and coordinates are never inferred from a city or state.
    """
    value = " ".join(raw.strip().split())
    if not value or len(value) > 160:
        raise LocationInputError("Enter a US state, ZIP, city/state, county/state, or address/state")
    if re.fullmatch(r"\d{5}", value):
        return Location(zip_code=value, precision=LocationPrecision.ZIP_AREA)

    state = state_code(value)
    if state:
        return Location(state=state, precision=LocationPrecision.STATE)

    parts = [part.strip() for part in value.split(",")]
    if len(parts) < 2 or len(parts) > 3 or any(not part for part in parts):
        raise LocationInputError("Include the state with a city, county, or address")
    state = state_code(parts[-1])
    if state is None:
        raise LocationInputError("Use a valid US state name or two-letter code")

    if len(parts) == 2 and re.fullmatch(r"\d{5}", parts[0]):
        return Location(state=state, zip_code=parts[0], precision=LocationPrecision.ZIP_AREA)
    if len(parts) == 3 and ADDRESS_START.match(parts[0]) and PLACE.fullmatch(parts[1]):
        return Location(address=parts[0], city=parts[1], state=state,
                        precision=LocationPrecision.ADDRESS)
    if len(parts) == 2 and ADDRESS_START.match(parts[0]):
        return Location(address=parts[0], state=state, precision=LocationPrecision.ADDRESS)
    if len(parts) == 2 and PLACE.fullmatch(parts[0]):
        if parts[0].lower().endswith(" county"):
            return Location(county=parts[0], state=state, precision=LocationPrecision.COUNTY)
        return Location(city=parts[0], state=state, precision=LocationPrecision.CITY)
    raise LocationInputError("Enter a valid city, county, ZIP, or address with its state")
