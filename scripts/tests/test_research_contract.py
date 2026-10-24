"""Offline regression checks for point 1 of the research plan."""

import pytest
from pydantic import ValidationError

from scripts.ecocompute_research.fixtures import pine_island_contract_fixture
from scripts.ecocompute_research.legacy import to_active_site
from scripts.ecocompute_research.models import (
    CapacityKind,
    Claim,
    ClaimConflict,
    ClaimSubject,
    EvidenceRef,
    EvidenceStatus,
    ResearchResult,
    SourceRecord,
    SourceType,
)


def test_pine_island_separates_facility_and_energy_plan_capacity():
    result = pine_island_contract_fixture()
    by_subject = {claim.subject: claim for claim in result.claims}

    assert len(result.claims) == 4
    assert by_subject[ClaimSubject.DATA_CENTER].value == 780
    assert by_subject[ClaimSubject.DATA_CENTER].capacity_kind == CapacityKind.UNKNOWN
    assert by_subject[ClaimSubject.WIND_GENERATION].value == 1400
    assert by_subject[ClaimSubject.SOLAR_GENERATION].value == 200
    assert by_subject[ClaimSubject.BATTERY_STORAGE].value == 300
    assert all(claim.status == EvidenceStatus.REPORTED for claim in result.claims)

    restored = ResearchResult.model_validate_json(result.model_dump_json())
    assert restored == result


def test_active_site_projection_has_no_invented_location_or_estimates():
    site = to_active_site(pine_island_contract_fixture(), input_mode="url")

    assert (site.city, site.state) == ("Pine Island", "MN")
    assert (site.county, site.zip_code, site.lat, site.lon) == (None, None, None, None)
    assert site.stated_mw == 780
    assert site.capacity_kind == CapacityKind.UNKNOWN
    assert site.estimated_mw is None
    assert site.egrid_lb_mwh is None
    assert site.claimed_water_gpd is None
    assert "water.peak_daily_gallons" in site.missing_fields


def test_solar_capacity_cannot_masquerade_as_facility_capacity():
    solar = pine_island_contract_fixture().claims[2]
    with pytest.raises(ValidationError, match="requires subject data_center"):
        Claim.model_validate({**solar.model_dump(), "field": "electricity.capacity_mw"})


def test_conflicted_facility_capacity_is_not_projected_as_one_number():
    result = pine_island_contract_fixture()
    result.claims.append(result.claims[0].model_copy(update={"id": "facility_900_mw", "value": 900.0}))
    result.conflicts.append(ClaimConflict(
        id="capacity_disagreement",
        field="electricity.capacity_mw",
        claim_ids=["facility_780_mw", "facility_900_mw"],
        explanation="Two unresolved reported capacity figures",
    ))
    validated = ResearchResult.model_validate(result.model_dump())

    site = to_active_site(validated, input_mode="url")
    assert site.stated_mw is None
    assert site.capacity_kind is None


def test_verified_requires_independent_origins_and_valid_source_references():
    result = pine_island_contract_fixture()
    reported = result.claims[0]
    result.sources.append(SourceRecord(
        id="cnbc_syndication",
        title="Republished CNBC story",
        source_type=SourceType.NEWS,
        independent_origin="cnbc_2026_10_19_reporting",
        url="https://example.com/republished-cnbc",
    ))
    result.claims[0] = reported.model_copy(update={
        "status": EvidenceStatus.VERIFIED,
        "evidence": [*reported.evidence, EvidenceRef(
            source_id="cnbc_syndication",
            excerpt="planned 780-megawatt data center",
        )],
    })
    with pytest.raises(ValidationError, match="two independent origins"):
        ResearchResult.model_validate(result.model_dump())

    result.claims[0] = reported.model_copy(update={
        "evidence": [EvidenceRef(source_id="nonexistent", excerpt="780 MW")],
    })
    with pytest.raises(ValidationError, match="unknown source"):
        ResearchResult.model_validate(result.model_dump())


def test_not_found_capacity_does_not_become_zero():
    unknown = Claim(
        id="missing_load",
        field="electricity.capacity_mw",
        subject=ClaimSubject.DATA_CENTER,
        measure="power_capacity",
        value=None,
        unit="MW",
        capacity_kind=CapacityKind.UNKNOWN,
        status=EvidenceStatus.NOT_FOUND,
    )
    assert unknown.value is None
    with pytest.raises(ValidationError, match="Not-found claims cannot carry a value"):
        Claim.model_validate({**unknown.model_dump(), "value": 0})
