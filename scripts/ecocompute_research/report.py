"""Neutral missing-information audit and deterministic cited summary."""

from __future__ import annotations

from .models import (
    Claim, ClaimConflict, EvidenceStatus, MissingField, ProjectIdentity,
    ResearchStatus, SourceRecord,
)


MISSING_TEMPLATES = {
    "electricity.capacity_mw": (
        "critical", "Facility power scale affects grid planning and impact estimates.",
        "What power capacity is requested, and is it IT, facility, or grid-connection capacity?",
    ),
    "water.peak_daily_gallons": (
        "critical", "Peak water demand can strain local supply and infrastructure.",
        "What is the expected peak daily water demand and its source?",
    ),
    "cooling.type": (
        "warning", "Cooling design affects direct water and electricity demand.",
        "What cooling design is planned for this facility?",
    ),
    "electricity.infrastructure_payer": (
        "critical", "Residents need to know who bears the cost of grid upgrades.",
        "Who will pay for substation, transmission, and other grid upgrades?",
    ),
    "environment.backup_generators": (
        "warning", "Generator permits can affect local air quality and noise.",
        "How many backup generators are planned and what permits cover them?",
    ),
    "electricity.tariff": (
        "warning", "Tariff terms determine how facility costs and risks are allocated.",
        "Which tariff and electric service agreement will apply?",
    ),
}


def find_missing_fields(claims: list[Claim], sources: list[SourceRecord]) -> list[MissingField]:
    documented = {claim.field for claim in claims
                  if claim.status in {EvidenceStatus.REPORTED, EvidenceStatus.VERIFIED}}
    checked = [source.id for source in sources]
    return [
        MissingField(field=field, severity=severity, why_it_matters=why,
                     checked_source_ids=checked, town_hall_question=question)
        for field, (severity, why, question) in MISSING_TEMPLATES.items()
        if field not in documented
    ]


def _format_claim(claim: Claim) -> str:
    value = f"{claim.value:g}" if isinstance(claim.value, (int, float)) else str(claim.value)
    unit = f" {claim.unit}" if claim.unit else ""
    kind = f" ({claim.capacity_kind.value} capacity)" if claim.capacity_kind else ""
    context = f"; phase: {claim.phase_label}" if claim.phase_label else ""
    citations = ", ".join(f"[{ref.source_id}]" for ref in claim.evidence)
    if claim.status == EvidenceStatus.ESTIMATED:
        citations = "; ".join(claim.assumptions)
    return f"- {claim.field}: {value}{unit}{kind} — {claim.status.value}{context}. {citations}".rstrip()


def build_summary(
    project: ProjectIdentity | None, sources: list[SourceRecord],
    claims: list[Claim], conflicts: list[ClaimConflict],
    missing: list[MissingField], status: ResearchStatus,
) -> str:
    lines = ["# Data center research summary", ""]
    if project:
        location = project.location
        place = ", ".join(part for part in [location.city or location.county, location.state] if part)
        lines.append(f"Project: {project.name or 'Unidentified'}; developer: {project.developer or 'not found'}; location: {place or 'not resolved'}.")
    else:
        lines.append("A specific project has not been identified.")
    lines.append(f"Research coverage: {status.value}; {len(sources)} reviewed source(s).")

    sections = {
        "Electricity and grid": ("electricity.", "energy_plan."),
        "Water": ("water.", "cooling."),
        "Environment": ("environment.",),
        "Financial and community": ("financial.", "community."),
        "Project details": ("project.",),
    }
    for heading, prefixes in sections.items():
        lines.extend(["", f"## {heading}", ""])
        matching = [claim for claim in claims if claim.field.startswith(prefixes)
                    and claim.status != EvidenceStatus.NOT_FOUND]
        lines.extend(_format_claim(claim) for claim in matching)
        if not matching:
            lines.append("No project-specific figure was found in the reviewed sources.")

    lines.extend(["", "## Conflicting or context-dependent claims", ""])
    if conflicts:
        lines.extend(f"- {item.field}: {item.explanation} Claims: {', '.join(item.claim_ids)}."
                     for item in conflicts)
    else:
        lines.append("No conflicts were identified among the extracted claims.")

    lines.extend(["", "## Information not found in reviewed sources", ""])
    if missing:
        lines.extend(f"- {item.field}: {item.why_it_matters} Question: {item.town_hall_question}"
                     for item in missing)
    else:
        lines.append("No fields from the current audit list remain unreported.")

    lines.extend(["", "## Sources", ""])
    if sources:
        lines.extend(f"- [{item.id}] {item.title}: {item.url or 'user-supplied text'}"
                     for item in sources)
    else:
        lines.append("No external sources were reviewed.")
    lines.extend(["", "## Overall findings", ""])
    lines.append("The listed figures are limited to the reviewed sources. Reported values, estimates, and unresolved differences remain separate; missing information is not treated as zero.")
    return "\n".join(lines)
