"""Resolve a US ZIP to search context without inventing a facility address."""

from __future__ import annotations

import httpx

from .location import state_code
from .models import Location, LocationPrecision


class ZipLookupError(ValueError):
    """The public ZIP lookup could not supply usable city/state context."""


def resolve_us_zip(zip_code: str, *, client: httpx.Client | None = None) -> Location:
    owned = client is None
    client = client or httpx.Client(timeout=5.0, trust_env=False)
    try:
        try:
            response = client.get(f"https://api.zippopotam.us/us/{zip_code}")
        except httpx.RequestError as exc:
            raise ZipLookupError("ZIP lookup could not be reached") from exc
        if response.status_code == 404:
            raise ZipLookupError(f"No US location was found for ZIP {zip_code}")
        if response.status_code != 200:
            raise ZipLookupError(f"ZIP lookup returned HTTP {response.status_code}")
        try:
            place = response.json()["places"][0]
            city = place["place name"].strip()
            state = state_code(place["state abbreviation"])
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ZipLookupError("ZIP lookup returned unusable location data") from exc
        if not city or state is None:
            raise ZipLookupError("ZIP lookup returned unusable location data")
        return Location(city=city, state=state, zip_code=zip_code,
                        precision=LocationPrecision.ZIP_AREA)
    finally:
        if owned:
            client.close()
