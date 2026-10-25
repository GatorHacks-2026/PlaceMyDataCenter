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
from .location import STATE_NAMES


NUMBER = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?"
POWER = re.compile(rf"\b(?P<number>{NUMBER})\s*[- ]?\s*(?P<unit>MW|GW|megawatts?|gigawatts?)\b", re.I)
WATER = re.compile(rf"\b(?P<number>{NUMBER})\s*(?P<million>million\s+)?gallons?\s*(?:per\s*day|a\s*day|daily|/\s*day)\b", re.I)
INVESTMENT = re.compile(r"\$\s*(?P<number>\d+(?:,\d{3})*(?:\.\d+)?)\s*(?P<scale>billion|million)\b", re.I)
JOBS = re.compile(rf"\b(?P<number>{NUMBER})\s+(?:permanent|full[- ]time|operational)\s+jobs\b", re.I)
GPD_AMOUNT = r"\d+(?:,\d{3})*(?:\.\d+)?(?:\s+million)?"
TIER_PAIR = re.compile(
    rf"For Tiers?\s+(?P<first>I|II|III)\s+and\s+(?P<second>I|II|III),?\s+the maximum gallons per day\s*\(GPD\)\s+is\s+"
    rf"(?P<max_first>{GPD_AMOUNT})\s+and\s+(?P<max_second>{GPD_AMOUNT})\s+GPD,?\s+respectively,?\s+and\s+"
    rf"(?P<avg_first>{GPD_AMOUNT})\s+and\s+(?P<avg_second>{GPD_AMOUNT})\s+average GPD",
    re.I,
)
TIER_SINGLE = re.compile(
    rf"total maximum allocation for Tier\s+(?P<tier>I|II|III)\s+is\s+(?P<maximum>{GPD_AMOUNT})\s+GPD,?\s+"
    rf"with an average GPD of\s+(?P<average>{GPD_AMOUNT})",
    re.I,
)


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+|[\r\n]+", text) if item.strip()]


def _claim(
    source: CollectedSource, sentence: str, field: str, subject: ClaimSubject,
    measure: str, value: float | str, unit: str | None,
    *, capacity_kind: CapacityKind | None = None,
    phase_label: str | None = None, basis: str | None = None,
) -> Claim:
    digest = sha256(f"{source.source.id}|{field}|{value}|{phase_label}|{basis}|{sentence}".encode()).hexdigest()[:14]
    return Claim(
        id=f"claim_{digest}", field=field, subject=subject, measure=measure,
        value=value, unit=unit, status=EvidenceStatus.REPORTED,
        capacity_kind=capacity_kind, phase=ProjectPhase.UNKNOWN,
        phase_label=phase_label, basis=basis,
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
    gas_generation = r"\b(?:natural[\s-]+gas|gas[\s-]*fired|gas[\s-]+(?:plant|facility|generation|generators?))\b"
    gas_match = re.search(gas_generation, phrase)
    data_center_match = re.search(r"\bdata cent(?:er|re)s?\b", phrase)
    if ((gas_match and (not data_center_match or gas_match.start() < data_center_match.start())) or
            (re.search(gas_generation, before) and
             re.search(r"\b(?:plant|facility|generation|generators?)\b", phrase) and
             not data_center_match)):
        return "energy_plan.gas_generation_capacity_mw", ClaimSubject.GAS_GENERATION, None
    if data_center_match or "data center" in before or "data centre" in before:
        return "electricity.capacity_mw", ClaimSubject.DATA_CENTER, CapacityKind.UNKNOWN
    return None


def _local_project_context(sentence: str, project: ProjectIdentity) -> bool:
    city = project.location.city
    if city and re.search(rf"\b{re.escape(city)}\b", sentence, re.I):
        return True
    state = project.location.state
    state_name = next((name for name, code in STATE_NAMES.items() if code == state), None)
    has_state = bool(state and any(
        re.search(rf"\b{re.escape(token)}\b", sentence, re.I)
        for token in (state, state_name) if token
    ))
    return bool(has_state and project.developer and
                re.search(rf"\b{re.escape(project.developer)}\b", sentence, re.I))


def _gpd_number(raw: str) -> float:
    return float(raw.lower().replace("million", "").replace(",", "").strip()) * (
        1_000_000 if "million" in raw.lower() else 1
    )


def _tier_water_allocations(source: CollectedSource, project: ProjectIdentity) -> list[Claim]:
    """Only parse the project-specific tier section, never a general water FAQ."""
    if not project.developer:
        return []
    heading = re.search(rf"FAQs? For\s+{re.escape(project.developer)}\s+Data Center", source.text, re.I)
    if not heading:
        return []
    paragraphs = source.text[heading.end():].split("\n\n")
    question = next((index for index, paragraph in enumerate(paragraphs)
                     if re.search(r"How much water will this facility use\?", paragraph, re.I)), None)
    if question is None or question + 1 >= len(paragraphs):
        return []
    water_text = paragraphs[question + 1]
    claims: list[Claim] = []
    for sentence in _sentences(water_text):
        pair = TIER_PAIR.search(sentence)
        if pair:
            for suffix, tier in (("first", pair.group("first")), ("second", pair.group("second"))):
                for measure, group in (("maximum", f"max_{suffix}"), ("average", f"avg_{suffix}")):
                    claims.append(_claim(
                        source, sentence, f"water.{measure}_allocation_gpd",
                        ClaimSubject.WATER_SYSTEM, "water_allocation",
                        _gpd_number(pair.group(group)), "gallons/day",
                        phase_label=f"Tier {tier}", basis=f"{measure} allocation",
                    ))
        single = TIER_SINGLE.search(sentence)
        if single:
            for measure, group in (("maximum", "maximum"), ("average", "average")):
                claims.append(_claim(
                    source, sentence, f"water.{measure}_allocation_gpd",
                    ClaimSubject.WATER_SYSTEM, "water_allocation",
                    _gpd_number(single.group(group)), "gallons/day",
                    phase_label=f"Tier {single.group('tier')}", basis=f"{measure} allocation",
                ))
    return claims


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
            if subject == ClaimSubject.DATA_CENTER and not _local_project_context(sentence, project):
                continue
            value = float(match.group("number").replace(",", ""))
            if match.group("unit").casefold().startswith(("gw", "gigawatt")):
                value *= 1000
            claims.append(_claim(source, sentence, field, subject, "power_capacity",
                                 value, "MW", capacity_kind=kind))
        project_context = (_local_project_context(sentence, project) or
                           bool(project.developer and "data center" in sentence.casefold() and
                                re.search(rf"\b{re.escape(project.developer)}\b", sentence, re.I)))
        if not project_context:
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
            context = sentence.casefold()
            if "infrastructure development" in context:
                field, basis = "financial.infrastructure_development_usd", "infrastructure development"
            elif "data center" in context and "investment" not in context:
                field, basis = "financial.project_value_usd", "reported project value"
            else:
                field, basis = "financial.investment_usd", "reported investment"
            claims.append(_claim(source, sentence, field, ClaimSubject.FINANCIAL,
                                 "investment", value, "USD", basis=basis))
        for match in JOBS.finditer(sentence):
            value = float(match.group("number").replace(",", ""))
            claims.append(_claim(source, sentence, "community.permanent_jobs",
                                 ClaimSubject.COMMUNITY, "jobs", value, "jobs"))
    claims.extend(_tier_water_allocations(source, project))
    return list({claim.id: claim for claim in claims}.values())
