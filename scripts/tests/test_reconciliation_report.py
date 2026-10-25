"""Agreement, disagreement, proxy, and transparency regression cases."""

from scripts.ecocompute_research.estimates import assess_scale
from scripts.ecocompute_research.fixtures import pine_island_contract_fixture
from scripts.ecocompute_research.models import (
    Claim, ClaimSubject, EvidenceRef, EvidenceStatus, SourceRecord, SourceType,
    ResearchResult, ResearchStatus,
)
from scripts.ecocompute_research.reconciliation import reconcile_claims
from scripts.ecocompute_research.report import build_summary, find_missing_fields


def _source(source_id: str, origin: str) -> SourceRecord:
    return SourceRecord(id=source_id, title=f"Source {source_id}", source_type=SourceType.NEWS,
                        independent_origin=origin, url=f"https://example.com/{source_id}")


def _load(claim_id: str, value: int, source_id: str, **updates) -> Claim:
    return Claim(
        id=claim_id, field="electricity.capacity_mw", subject=ClaimSubject.DATA_CENTER,
        measure="power_capacity", value=value, unit="MW", capacity_kind="unknown",
        status=EvidenceStatus.REPORTED,
        evidence=[EvidenceRef(source_id=source_id, excerpt=f"{value} MW data center")],
        **updates,
    )


def test_independent_matching_reports_merge_into_verified_claim():
    sources = [_source("one", "original_a"), _source("two", "original_b")]
    reconciled = reconcile_claims([_load("a", 780, "one"), _load("b", 780, "two")], sources)
    assert len(reconciled.claims) == 1
    assert reconciled.claims[0].status == EvidenceStatus.VERIFIED
    assert {ref.source_id for ref in reconciled.claims[0].evidence} == {"one", "two"}
    assert reconciled.conflicts == []
    ResearchResult(status=ResearchStatus.PARTIAL, sources=sources,
                   claims=reconciled.claims)


def test_syndicated_copies_do_not_count_as_independent_verification():
    sources = [_source("one", "same_reporting"), _source("mirror", "same_reporting")]
    result = reconcile_claims([_load("a", 780, "one"), _load("b", 780, "mirror")], sources)
    assert result.claims[0].status == EvidenceStatus.REPORTED


def test_unexplained_capacity_disagreement_stays_conflicting():
    sources = [_source("one", "a"), _source("two", "b")]
    result = reconcile_claims([_load("a", 780, "one"), _load("b", 900, "two")], sources)
    assert {claim.value for claim in result.claims} == {780, 900}
    assert all(claim.status == EvidenceStatus.CONFLICTING for claim in result.claims)
    assert len(result.conflicts) == 1
    assert result.conflicts[0].resolved is False


def test_explicit_phase_difference_is_preserved_and_explained():
    sources = [_source("one", "a"), _source("two", "b")]
    result = reconcile_claims([
        _load("phase_one", 150, "one", phase_label="phase 1"),
        _load("buildout", 500, "two", phase_label="full buildout"),
    ], sources)
    assert {claim.value for claim in result.claims} == {150, 500}
    assert len(result.conflicts) == 1
    assert result.conflicts[0].resolved is True


def test_proxy_does_not_fill_undisclosed_capacity_or_baseline():
    building = Claim(
        id="building", field="project.building_sqft", subject=ClaimSubject.DATA_CENTER,
        measure="building_area", value=600_000, unit="sqft", status=EvidenceStatus.REPORTED,
        evidence=[EvidenceRef(source_id="one", excerpt="600,000 square feet")],
    )
    assessed = assess_scale([building], workload_type="ai_training")
    assert assessed.reported_capacity_mw is None
    assert assessed.proxy_claim.value == 210
    assert assessed.proxy_claim.status == EvidenceStatus.ESTIMATED
    assert assessed.proxy_claim.field == "electricity.proxy_capacity_mw"
    assert "electricity.capacity_mw" in {item.field for item in find_missing_fields(
        [building, assessed.proxy_claim], [_source("one", "a")])}

    baseline = assess_scale([])
    assert baseline.proxy_claim is None
    assert baseline.scenario_baseline_mw == 100


def test_report_is_cited_and_uses_neutral_missing_language():
    fixture = pine_island_contract_fixture()
    missing = find_missing_fields(fixture.claims, fixture.sources)
    summary = build_summary(fixture.project, fixture.sources, fixture.claims,
                            [], missing, ResearchStatus.PARTIAL)
    assert "780 MW" in summary
    assert "[cnbc_2026_10_19]" not in summary  # fixture uses accessible secondary report
    assert "[blandin_2026_10_19]" in summary
    assert "not found in reviewed sources" in summary
    assert "withheld" not in summary.lower()
