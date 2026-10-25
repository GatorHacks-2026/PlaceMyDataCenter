"""Merge repeated claims and retain disagreements without averaging values."""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256

from pydantic import Field

from .models import Claim, ClaimConflict, EvidenceStatus, SourceRecord, StrictModel


class ReconciliationResult(StrictModel):
    claims: list[Claim] = Field(default_factory=list)
    conflicts: list[ClaimConflict] = Field(default_factory=list)


def _context(claim: Claim) -> tuple:
    return (claim.field, claim.subject, claim.unit, claim.capacity_kind,
            claim.phase_label, claim.basis)


def _same_value(first: Claim, second: Claim) -> bool:
    return first.value == second.value


def _conflict(field: str, claims: list[Claim], explanation: str, resolved: bool) -> ClaimConflict:
    ids = sorted(claim.id for claim in claims)
    digest = sha256(f"{field}|{'|'.join(ids)}".encode()).hexdigest()[:12]
    return ClaimConflict(id=f"conflict_{digest}", field=field, claim_ids=ids,
                         explanation=explanation, resolved=resolved)


def reconcile_claims(claims: list[Claim], sources: list[SourceRecord]) -> ReconciliationResult:
    by_source = {source.id: source for source in sources}
    grouped: dict[tuple, list[Claim]] = defaultdict(list)
    carry: list[Claim] = []
    for claim in claims:
        if claim.status in {EvidenceStatus.NOT_FOUND, EvidenceStatus.ESTIMATED}:
            carry.append(claim)
            continue
        grouped[_context(claim)].append(claim)

    merged: list[Claim] = []
    conflicts: list[ClaimConflict] = []
    for context, context_claims in grouped.items():
        value_groups: list[list[Claim]] = []
        for claim in context_claims:
            for group in value_groups:
                if _same_value(claim, group[0]):
                    group.append(claim)
                    break
            else:
                value_groups.append([claim])
        consolidated: list[Claim] = []
        for group in value_groups:
            evidence = list({(ref.source_id, ref.excerpt): ref
                             for item in group for ref in item.evidence}.values())
            origins = {by_source[ref.source_id].independent_origin
                       for ref in evidence if ref.source_id in by_source}
            status = EvidenceStatus.VERIFIED if len(origins) >= 2 else EvidenceStatus.REPORTED
            consolidated.append(group[0].model_copy(update={"evidence": evidence, "status": status}))
        if len(consolidated) > 1:
            consolidated = [item.model_copy(update={"status": EvidenceStatus.CONFLICTING})
                            for item in consolidated]
            conflicts.append(_conflict(context[0], consolidated,
                                       "Sources report different values for the same field and context.",
                                       resolved=False))
        merged.extend(consolidated)

    # Explicitly different phases or bases may account for different figures.
    # Unknown context is never treated as an explanation.
    by_field: dict[str, list[Claim]] = defaultdict(list)
    for claim in merged:
        by_field[claim.field].append(claim)
    for field, field_claims in by_field.items():
        for index, first in enumerate(field_claims):
            for second in field_claims[index + 1:]:
                if _context(first) == _context(second) or _same_value(first, second):
                    continue
                phase_differs = bool(first.phase_label and second.phase_label and
                                     first.phase_label != second.phase_label)
                basis_differs = bool(first.basis and second.basis and first.basis != second.basis)
                explained = phase_differs or basis_differs
                explanation = (
                    "Figures describe explicitly different project phases or measurement bases."
                    if explained else
                    "Figures differ and their context does not establish why."
                )
                conflicts.append(_conflict(field, [first, second], explanation, resolved=explained))
                if not explained:
                    merged = [item.model_copy(update={"status": EvidenceStatus.CONFLICTING})
                              if item.id in {first.id, second.id} else item for item in merged]
    unique_conflicts = list({item.id: item for item in conflicts}.values())
    return ReconciliationResult(claims=merged + carry, conflicts=unique_conflicts)
