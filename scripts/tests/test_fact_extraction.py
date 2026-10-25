"""Every extracted figure must remain tied to its subject and source."""

from datetime import datetime, timezone
import json

import httpx

from scripts.ecocompute_research.collection import CollectedSource
from scripts.ecocompute_research.fact_extractor import extract_facts
from scripts.ecocompute_research.facts import extract_deterministic
from scripts.ecocompute_research.fixtures import pine_island_contract_fixture
from scripts.ecocompute_research.gemini import GeminiFactExtractor
from scripts.ecocompute_research.models import ClaimSubject, SourceRecord, SourceType


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
