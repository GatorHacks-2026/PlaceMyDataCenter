"""Every extracted figure must remain tied to its subject and source."""

from datetime import datetime, timezone
import json

import httpx

from scripts.ecocompute_research.collection import CollectedSource
from scripts.ecocompute_research.fact_extractor import extract_facts
from scripts.ecocompute_research.facts import extract_deterministic
from scripts.ecocompute_research.fixtures import pine_island_contract_fixture
from scripts.ecocompute_research.gemini import GeminiFactExtractor
from scripts.ecocompute_research.models import (
    ClaimSubject, Location, LocationPrecision, ProjectIdentity, SourceRecord, SourceType,
)
from scripts.ecocompute_research.reconciliation import reconcile_claims


PROJECT = pine_island_contract_fixture().project


def source(source_id: str, text: str) -> CollectedSource:
    return CollectedSource(
        source=SourceRecord(
            id=source_id, title="Pine Island project source", source_type=SourceType.NEWS,
            independent_origin=source_id, url=f"https://example.com/{source_id}",
            retrieved_at=datetime.now(timezone.utc),
        ),
        text=text, relevance_reason="Test fixture about the target project",
    )


def test_deterministic_power_subjects_and_comma_numbers():
    item = source("one", (
        "Google plans a 780-megawatt data center in Pine Island, Minnesota. "
        "The agreement includes 1,400 MW of wind, 200 MW of solar and 300 MW "
        "of battery storage."
    ))
    claims = extract_deterministic(item, PROJECT)
    by_subject = {claim.subject: claim for claim in claims}
    assert by_subject[ClaimSubject.DATA_CENTER].value == 780
    assert by_subject[ClaimSubject.WIND_GENERATION].value == 1400
    assert by_subject[ClaimSubject.SOLAR_GENERATION].value == 200
    assert by_subject[ClaimSubject.BATTERY_STORAGE].value == 300
    assert all(claim.evidence[0].source_id == "one" for claim in claims)


def test_deterministic_extracts_only_explicit_project_water_jobs_and_investment():
    item = source("two", (
        "Google proposed a data center in Pine Island, MN. "
        "The Pine Island, MN data center will use 500,000 gallons per day. "
        "Google expects $1.5 billion investment in Pine Island, MN and 50 permanent jobs. "
        "Other Minnesota facilities may use 2 million gallons per day."
    ))
    claims = extract_deterministic(item, PROJECT)
    by_field = {claim.field: claim.value for claim in claims}
    assert by_field["water.daily_gallons"] == 500_000
    assert by_field["financial.investment_usd"] == 1_500_000_000
    assert by_field["community.permanent_jobs"] == 50
    assert len([claim for claim in claims if claim.field == "water.daily_gallons"]) == 1


def test_multi_project_article_does_not_take_other_site_capacity():
    item = source("three", (
        "Google plans a 780-megawatt data center in Pine Island, MN. "
        "Google plans a 900-megawatt data center in Hermantown, MN."
    ))
    claims = extract_deterministic(item, PROJECT)
    assert [claim.value for claim in claims if claim.field == "electricity.capacity_mw"] == [780]


def test_gemini_output_must_quote_source_and_match_reported_number():
    item = source("four", (
        "Google plans a 780-megawatt data center in Pine Island, MN. "
        "The project includes 1,400 MW of wind."
    ))
    def raw_claim(value, excerpt):
        return {
            "field": "electricity.capacity_mw", "subject": "data_center",
            "measure": "power_capacity", "value": value, "unit": "MW",
            "capacity_kind": None, "excerpt": excerpt,
        }
    payload = {"claims": [
        raw_claim(780, "Google plans a 780-megawatt data center in Pine Island, MN."),
        raw_claim(900, "Google plans a 780-megawatt data center in Pine Island, MN."),
        raw_claim(780, "fabricated 780-megawatt data center"),
        raw_claim(1400, "1,400 MW of wind"),
    ]}
    def answer(_request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": json.dumps(payload)},
        ]}}]})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        gemini = GeminiFactExtractor(api_key="test-key", client=client)
        result = extract_facts([item], PROJECT, gemini=gemini)
    assert result.used_gemini is True
    assert len(result.claims) == 1
    assert result.claims[0].value == 780
    assert result.claims[0].evidence[0].source_id == "four"


def test_generic_capacity_examples_do_not_conflict_with_project_capacity():
    item = source("general", (
        "Google plans a 780-megawatt data center in Pine Island, Minnesota. "
        "An analyst asked why companies build 25-megawatt data centers. "
        "Why are they doing 1,000-megawatt data centers?"
    ))
    claims = extract_deterministic(item, PROJECT)
    assert [claim.value for claim in claims if claim.field == "electricity.capacity_mw"] == [780]


def test_el_paso_gas_plant_is_not_data_center_capacity():
    project = ProjectIdentity(
        developer="Meta",
        location=Location(city="El Paso", state="TX", precision=LocationPrecision.CITY),
    )
    item = source("el_paso", (
        "Meta plans a 1-gigawatt data center in El Paso, Texas. "
        "El Paso Electric proposed a 366-megawatt natural gas facility "
        "to power the Meta data center in El Paso."
    ))
    claims = extract_deterministic(item, project)
    assert {(claim.field, claim.value, claim.subject) for claim in claims} == {
        ("electricity.capacity_mw", 1000, ClaimSubject.DATA_CENTER),
        ("energy_plan.gas_generation_capacity_mw", 366, ClaimSubject.GAS_GENERATION),
    }
    assert not reconcile_claims(claims, [item.source]).conflicts


def test_el_paso_city_tiers_and_infrastructure_scope():
    project = ProjectIdentity(developer="Meta", location=Location(
        city="El Paso", state="TX", precision=LocationPrecision.CITY))
    item = source("city", (
        "The META data center project in El Paso, Texas is a $1.5 billion "
        "infrastructure development.\n\nFAQs For META Data Center\n\n"
        "How much water will this facility use?\n\n"
        "The project is structured in tiers or phases. For Tiers I and II, "
        "the maximum gallons per day (GPD) is 300,000 and 1 million GPD, "
        "respectively, and 100,000 and 750,000 average GPD. "
        "The total maximum allocation for Tier III is 2.5 million GPD, "
        "with an average GPD of 1.5 million."
    ))
    claims = extract_deterministic(item, project)
    water = {(claim.phase_label, claim.field): claim.value for claim in claims
             if claim.measure == "water_allocation"}
    assert water == {
        ("Tier I", "water.maximum_allocation_gpd"): 300_000,
        ("Tier I", "water.average_allocation_gpd"): 100_000,
        ("Tier II", "water.maximum_allocation_gpd"): 1_000_000,
        ("Tier II", "water.average_allocation_gpd"): 750_000,
        ("Tier III", "water.maximum_allocation_gpd"): 2_500_000,
        ("Tier III", "water.average_allocation_gpd"): 1_500_000,
    }
    assert [(claim.field, claim.value) for claim in claims if claim.subject == ClaimSubject.FINANCIAL] == [
        ("financial.infrastructure_development_usd", 1_500_000_000),
    ]


def test_data_center_capacity_stays_separate_when_gas_plant_appears_later():
    project = ProjectIdentity(
        developer="Meta",
        location=Location(city="El Paso", state="TX", precision=LocationPrecision.CITY),
    )
    item = source("el_paso_order", (
        "Meta plans a 1-gigawatt data center in El Paso, Texas, "
        "served by a natural gas plant."
    ))
    claims = extract_deterministic(item, project)
    assert [(claim.field, claim.value) for claim in claims] == [
        ("electricity.capacity_mw", 1000),
    ]


def test_gemini_cannot_label_gas_plant_as_data_center_capacity():
    project = ProjectIdentity(
        developer="Meta",
        location=Location(city="El Paso", state="TX", precision=LocationPrecision.CITY),
    )
    excerpt = "El Paso Electric proposed a 366 MW natural gas plant to power Meta's El Paso data center."
    item = source("el_paso_model", f"Meta plans a data center in El Paso, Texas. {excerpt}")
    payload = {"claims": [{
        "field": "electricity.capacity_mw", "subject": "data_center",
        "measure": "power_capacity", "value": 366, "unit": "MW",
        "capacity_kind": None, "excerpt": excerpt,
    }]}

    def answer(_request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": json.dumps(payload)},
        ]}}]})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        result = extract_facts([item], project,
                               gemini=GeminiFactExtractor(api_key="test-key", client=client))
    assert [claim for claim in result.claims if claim.subject == ClaimSubject.DATA_CENTER] == []
    assert [(claim.field, claim.value) for claim in result.claims] == [
        ("energy_plan.gas_generation_capacity_mw", 366),
    ]


def test_gemini_failure_falls_back_without_inventing_missing_values():
    item = source("five", "Google plans a 780-megawatt data center in Pine Island, MN.")
    with httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(500, json={"error": "down"}),
    )) as client:
        result = extract_facts([item], PROJECT,
                               gemini=GeminiFactExtractor(api_key="test-key", client=client))
    assert result.used_gemini is False
    assert result.claims[0].value == 780
    assert result.warnings
