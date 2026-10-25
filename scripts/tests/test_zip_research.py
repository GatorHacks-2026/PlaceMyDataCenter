"""ZIPs provide search context without becoming a claimed facility address."""

import httpx

from scripts.ecocompute_research.discovery import SearchHit
from scripts.ecocompute_research.gemini import GeminiFactExtractor
from scripts.ecocompute_research.intake import IntakeError, IntakeRequest, read_input
from scripts.ecocompute_research.models import Location, LocationPrecision, ResearchStatus
from scripts.ecocompute_research.pipeline import ResearchConfig, run_research
from scripts.ecocompute_research.zip_lookup import ZipLookupError, resolve_us_zip


def test_public_zip_lookup_keeps_zip_area_precision():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "places": [{"place name": "Pine Island", "state abbreviation": "MN"}],
    }))
    with httpx.Client(transport=transport) as client:
        location = resolve_us_zip("55963", client=client)
    assert location.city == "Pine Island"
    assert location.state == "MN"
    assert location.zip_code == "55963"
    assert location.precision == LocationPrecision.ZIP_AREA


def test_unknown_zip_is_reported():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(404),
    )) as client:
        try:
            resolve_us_zip("00000", client=client)
        except ZipLookupError as exc:
            assert "00000" in str(exc)
        else:
            raise AssertionError("Unknown ZIP was accepted")


def test_zip_with_wrong_state_is_rejected():
    try:
        read_input(
            IntakeRequest(mode="manual_location", location="55963, FL"),
            zip_resolver=lambda zip_code: Location(
                city="Pine Island", state="MN", zip_code=zip_code,
                precision=LocationPrecision.ZIP_AREA,
            ),
        )
    except IntakeError as exc:
        assert exc.code == "zip_state_mismatch"
    else:
        raise AssertionError("Mismatched ZIP and state were accepted")


def test_zip_and_text_identify_project_and_generate_place_queries():
    queries = []

    class Provider:
        def search(self, query, *, count):
            queries.append(query)
            return []

    result = run_research(
        IntakeRequest(mode="text", location="55963", article_text=(
            "Google plans a 780-megawatt data center in Pine Island, Minnesota."
        )),
        provider=Provider(),
        zip_resolver=lambda zip_code: Location(
            city="Pine Island", state="MN", zip_code=zip_code,
            precision=LocationPrecision.ZIP_AREA,
        ),
        gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.PARTIAL  # no independent sources
    assert result.project is not None
    assert result.project.location.city == "Pine Island"
    assert result.project.location.zip_code is None  # not a verified facility ZIP
    assert result.location_input == "55963"
    assert result.location_hint.zip_code == "55963"
    assert result.location_source == "zippopotam"
    assert queries and "Pine Island" in queries[0]


def test_location_only_zip_returns_candidates_not_claims():
    class Provider:
        def search(self, query, *, count):
            return [SearchHit(
                title="Google data center in Pine Island, Minnesota",
                url="https://example.com/pine-island",
                description="Google plans a data center in Pine Island, MN",
            )]

    result = run_research(
        IntakeRequest(mode="manual_location", location="55963"),
        provider=Provider(),
        zip_resolver=lambda zip_code: Location(
            city="Pine Island", state="MN", zip_code=zip_code,
            precision=LocationPrecision.ZIP_AREA,
        ),
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.AMBIGUOUS
    assert result.candidates
    assert result.sources == []
    assert result.claims == []
