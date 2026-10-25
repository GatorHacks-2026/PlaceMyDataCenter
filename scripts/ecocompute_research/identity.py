"""Conservative, deterministic project identification from seed text.

This is a first-pass identity gate, not a general named-entity model. It
returns ambiguity rather than guessing when multiple project mentions fit.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
import re

from pydantic import Field

from .location import STATE_NAMES, parse_location
from .models import Location, LocationPrecision, ProjectIdentity, ProjectPhase, StrictModel


PROJECT_WORDS = re.compile(r"\b(?:data\s+cent(?:er|re)|server\s+farm|compute\s+campus)\b", re.I)
STATE_PATTERN = "|".join(
    re.escape(item) for item in sorted({*STATE_NAMES.keys(), *STATE_NAMES.values()}, key=len, reverse=True)
)
PLACE_PATTERN = re.compile(
    rf"\b(?:in|near|at|outside|around)\s+(?P<place>[A-Z][A-Za-z .'-]{{1,45}}?),\s*(?P<state>{STATE_PATTERN})\b",
    re.I,
)
PROJECT_NAME_PATTERN = re.compile(r"\bProject\s+([A-Z][A-Za-z0-9-]{2,35})\b")
ALIAS_PATTERN = re.compile(r"\balso\s+known\s+as\s+([A-Z][A-Za-z0-9 .'-]{2,50}?)(?:,|\s+is\b|\s+will\b|\.)", re.I)
OPERATOR_PATTERN = re.compile(r"\boperated\s+by\s+([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,4})\b")
DEVELOPER_PATTERNS = (
    re.compile(r"\b([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,4})['’]s\s+(?:planned|proposed|new|existing|\d[\d,]*[- ](?:MW|megawatt))?\s*(?:data\s+cent(?:er|re)|campus)", re.I),
    re.compile(r"^\s*([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,4})\s+(?:also\s+)?(?:has\s+)?(?:says|said|announced|planned|proposed|plans|proposes|will\s+build|is\s+building)\b"),
    re.compile(r"\b(?:developed|owned|proposed)\s+by\s+([A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){0,4})\b"),
)
DATE_PATTERN = re.compile(
    r"\bannounced\s+on\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b",
    re.I,
)


class IdentificationStatus(StrEnum):
    SELECTED = "selected"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


class ProjectCandidate(StrictModel):
    project: ProjectIdentity
    evidence_excerpt: str = Field(min_length=1)
    match_score: int = Field(ge=0)


class IdentificationResult(StrictModel):
    status: IdentificationStatus
    selected: ProjectIdentity | None = None
    candidates: list[ProjectCandidate] = Field(default_factory=list)
    explanation: str


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", text) if part.strip()]


def _developer(sentence: str) -> str | None:
    for pattern in DEVELOPER_PATTERNS:
        match = pattern.search(sentence)
        if match:
            value = match.group(1).strip(" ,.")
            if value.lower() not in {"the", "a", "an", "this", "that"}:
                return value
    return None


def _announcement_date(sentence: str):
    match = DATE_PATTERN.search(sentence)
    if not match:
        return None
    try:
        date_text = re.sub(r"^announced\s+on\s+", "", match.group(0), flags=re.I)
        return datetime.strptime(date_text.replace(",", ""),
                                 "%B %d %Y").date()
    except ValueError:
        return None


def _match_score(found: Location, hint: Location) -> int:
    if hint.state and found.state != hint.state:
        return 0
    if hint.city:
        return 100 if found.city and found.city.casefold() == hint.city.casefold() else 0
    if hint.county:
        return 90 if found.county and found.county.casefold() == hint.county.casefold() else 0
    if hint.zip_code:
        return 110 if found.zip_code == hint.zip_code else 0
    if hint.state:
        return 30 if found.state == hint.state else 0
    return 0


def identify_project(text: str | None, location_hint: Location) -> IdentificationResult:
    """Return a project only when the supplied place singles out a candidate."""
    if not text:
        return IdentificationResult(
            status=IdentificationStatus.NOT_FOUND,
            explanation="No article text is available to identify a project; discovery is required.",
        )

    found: dict[tuple[str, str, str], ProjectCandidate] = {}
    for sentence in _sentences(text):
        if not PROJECT_WORDS.search(sentence):
            continue
        for match in PLACE_PATTERN.finditer(sentence):
            try:
                location = parse_location(f"{match.group('place')}, {match.group('state')}")
            except ValueError:
                continue
            developer = _developer(sentence)
            project_name = PROJECT_NAME_PATTERN.search(sentence)
            operator_match = OPERATOR_PATTERN.search(sentence)
            alias_match = ALIAS_PATTERN.search(sentence)
            name = (f"Project {project_name.group(1)}" if project_name else
                    f"{developer} {location.city or location.county} data center"
                    if developer else f"Data center near {location.city or location.county}")
            project = ProjectIdentity(
                name=name,
                name_is_reported=project_name is not None,
                developer=developer,
                operator=operator_match.group(1) if operator_match else None,
                aliases=[alias_match.group(1).strip()] if alias_match else [],
                location=location,
                phase=ProjectPhase.PROPOSED if re.search(r"\b(?:proposed|planned|will build)\b", sentence, re.I)
                else ProjectPhase.UNKNOWN,
                announced_on=_announcement_date(sentence),
            )
            key = ((location.city or location.county or "").casefold(),
                   location.state or "", (developer or "").casefold())
            candidate = ProjectCandidate(
                project=project,
                evidence_excerpt=sentence[:500],
                match_score=_match_score(location, location_hint),
            )
            old = found.get(key)
            if old is None or candidate.match_score > old.match_score:
                found[key] = candidate

    candidates = sorted(found.values(), key=lambda item: item.match_score, reverse=True)
    matches = [item for item in candidates if item.match_score > 0]
    if len(matches) == 1:
        return IdentificationResult(
            status=IdentificationStatus.SELECTED,
            selected=matches[0].project,
            candidates=candidates,
            explanation="One project mention matches the supplied location.",
        )
    if len(matches) > 1:
        return IdentificationResult(
            status=IdentificationStatus.AMBIGUOUS,
            candidates=candidates,
            explanation="Multiple project mentions match the supplied location.",
        )
    return IdentificationResult(
        status=IdentificationStatus.NOT_FOUND,
        candidates=candidates,
        explanation="No project mention matched the supplied location.",
    )
