"""Conservative fallback extraction from one project-matched source at a time."""

from __future__ import annotations

from hashlib import sha256
import re

from .collection import CollectedSource
from .identity import IdentificationStatus, identify_project
from .models import (
    CapacityKind, Claim, ClaimSubject, EvidenceRef, EvidenceStatus,
    ProjectIdentity, ProjectPhase,
)


NUMBER = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?"
POWER = re.compile(rf"\b(?P<number>{NUMBER})\s*[- ]?\s*(?P<unit>MW|GW|megawatts?|gigawatts?)\b", re.I)
WATER = re.compile(rf"\b(?P<number>{NUMBER})\s*(?P<million>million\s+)?gallons?\s*(?:per\s*day|a\s*day|daily|/\s*day)\b", re.I)
INVESTMENT = re.compile(r"\$\s*(?P<number>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>billion|million)\b", re.I)
JOBS = re.compile(rf"\b(?P<number>{NUMBER})\s+(?:permanent|full[- ]time|operational)\s+jobs\b", re.I)


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|[\r\n]+", text) if item.strip()]


def _claim(
    source: CollectedSource, sentence: str, field: str, subject: ClaimSubject,
    measure: str, value: float | str, unit: str | None,
    *, capacity_kind: CapacityKind | None = None,
) -> Claim:
    digest = sha256(f"{source.source.id}|{field}|{value}|{sentence}".encode()).hexdigest()[:14]
    return Claim(
        id=f"claim_{digest}", field=field, subject=subject, measure=measure,
        value=value, unit=unit, status=EvidenceStatus.REPORTED,
        capacity_kind=capacity_kind, phase=ProjectPhase.UNKNOWN,
        as_of=source.source.published_on,
        evidence=[EvidenceRef(source_id=source.source.id, excerpt=sentence)],
    )


def _power_classification(sentence: str, match: re.Match[str]) -> tuple[str, ClaimSubject, CapacityKind | None] | None:
    after = sentence[match.end():]
    next_power = POWER.search(after)
    next_boundary = next_power.start() if next_power else len(after)
    phrase = after[:next_boundary].casefold()
    before = sentence[max(0, match.start() - 50):match.start()].casefold()
    resources = [item for item in ("wind", "solar", "battery") if item in phrase]
    if len(resources) > 1:
        return "energy_plan.package_mw", ClaimSubject.OTHER, None
    if "wind" in phrase or (not phrase.strip() and "wind" in before):
        return "energy_plan.wind_capacity_mw", ClaimSubject.WIND_GENERATION, None
    if "solar" in phrase or (not phrase.strip() and "solar" in before):
        return "energy_plan.solar_capacity_mw", ClaimSubject.SOLAR_GENERATION, None
    if "battery" in phrase or "storage" in phrase:
        return "energy_plan.battery_power_mw", ClaimSubject.BATTERY_STORAGE, None
    if "data center" in phrase or "data centre" in phrase or "data center" in before:
        return "electricity.capacity_mw", ClaimSubject.DATA_CENTER, CapacityKind.UNKNOWN
    return None


def extract_deterministic(source: CollectedSource, project: ProjectIdentity) -> list[Claim]:
    """Return only explicit, locally contextualized figures; absence is not zero."""
    whole_identity = identify_project(source.text, project.location)
    if whole_identity.status != IdentificationStatus.SELECTED:
        return []
    if project.developer and project.developer.casefold() not in source.text.casefold():
        return []
    many_projects = len(whole_identity.candidates) > 1
    claims: list[Claim] = []
    for sentence in _sentences(source.text):
        if many_projects:
            local = identify_project(sentence, project.location)
            if local.status != IdentificationStatus.SELECTED:
                continue
        for match in POWER.finditer(sentence):
            classification = _power_classification(sentence, match)
            if classification is None:
                continue
            field, subject, kind = classification
            value = float(match.group("number").replace(",", ""))
            if match.group("unit").casefold().startswith(("gw", "gigawatt")):
                value *= 1000
            claims.append(_claim(source, sentence, field, subject, "power_capacity",
                                 value, "MW", capacity_kind=kind))
        if project.location.city and project.location.city.casefold() not in sentence.casefold():
            # Water, jobs, and investment need explicit same-sentence project
            # context; a source can also discuss regional or other-site data.
            continue
        for match in WATER.finditer(sentence):
            value = float(match.group("number").replace(",", ""))
            if match.group("million"):
                value *= 1_000_000
            claims.append(_claim(source, sentence, "water.daily_gallons",
                                 ClaimSubject.WATER_SYSTEM, "water_use", value, "gallons/day"))
        for match in INVESTMENT.finditer(sentence):
            value = float(match.group("number").replace(",", ""))
            value *= 1_000_000_000 if match.group("scale").lower() == "billion" else 1_000_000
            claims.append(_claim(source, sentence, "financial.investment_usd",
                                 ClaimSubject.FINANCIAL, "investment", value, "USD"))
        for match in JOBS.finditer(sentence):
            value = float(match.group("number").replace(",", ""))
            claims.append(_claim(source, sentence, "community.permanent_jobs",
                                 ClaimSubject.COMMUNITY, "jobs", value, "jobs"))
    return list({claim.id: claim for claim in claims}.values())
