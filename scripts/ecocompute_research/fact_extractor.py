"""Run the optional model extractor and deterministic fallback over sources."""

from __future__ import annotations

from pydantic import Field

from .collection import CollectedSource
from .facts import extract_deterministic
from .gemini import GeminiError, GeminiFactExtractor
from .models import Claim, ProjectIdentity, StrictModel


class FactExtractionResult(StrictModel):
    claims: list[Claim] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    used_gemini: bool = False


def extract_facts(
    sources: list[CollectedSource], project: ProjectIdentity,
    *, gemini: GeminiFactExtractor | None = None,
) -> FactExtractionResult:
    """Never mark fallback values verified or manufacture absent figures."""
    claims: dict[str, Claim] = {}
    warnings: list[str] = []
    used_gemini = False
    for item in sources:
        extracted: list[Claim] = []
        if gemini is not None and gemini.api_key:
            try:
                extracted, source_warnings = gemini.extract(item, project)
                warnings.extend(f"{item.source.id}: {warning}" for warning in source_warnings)
                used_gemini = True
            except GeminiError as exc:
                warnings.append(f"{item.source.id}: Gemini unavailable ({exc}); used deterministic extraction")
        if not extracted:
            extracted = extract_deterministic(item, project)
        claims.update((claim.id, claim) for claim in extracted)
    return FactExtractionResult(claims=list(claims.values()), warnings=warnings,
                                used_gemini=used_gemini)
