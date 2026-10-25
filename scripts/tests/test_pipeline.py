"""Offline end-to-end orchestration through the research services."""

from scripts.ecocompute_research.discovery import SearchHit
from scripts.ecocompute_research.gemini import GeminiFactExtractor
from scripts.ecocompute_research.intake import IntakeRequest
from scripts.ecocompute_research.models import ResearchStatus
from scripts.ecocompute_research.pipeline import ResearchConfig, run_research
from scripts.ecocompute_research.url_fetch import FetchedDocument
from scripts.ecocompute_research.url_fetch import FetchError


class FakeProvider:
    def search(self, query, *, count):
        return [SearchHit(
            title="Google Pine Island data center announcement",
            url="https://example.com/google-pine-island",
            description="Google data center in Pine Island, MN; energy agreement",
        )]


def test_article_seed_adds_another_project_source_and_cited_facts():
    def fetch(url):
        if "cnbc" in url:
            text = "Google plans a 780-megawatt data center in Pine Island, Minnesota."
        else:
            text = (
                "Google plans a data center in Pine Island, Minnesota. "
                "The agreement includes 1,400 MW of wind, 200 MW of solar and "
                "300 MW of battery storage."
            )
        return FetchedDocument(url=url, media_type="text/plain", text=text)

    result = run_research(
        IntakeRequest(mode="url", location="Pine Island, MN",
                      article_url="https://cnbc.com/example-pine-island"),
        provider=FakeProvider(), fetcher=fetch,
        gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.PARTIAL  # limited deterministic extraction
    assert len(result.sources) == 2
    assert {claim.value for claim in result.claims if claim.unit == "MW"} == {780, 1400, 200, 300}
    assert "## Sources" in result.summary
    assert "not found in reviewed sources" in result.summary


def test_location_only_returns_candidate_leads_without_fabricated_research():
    result = run_research(
        IntakeRequest(mode="manual_location", location="Minnesota"),
        provider=FakeProvider(), config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.AMBIGUOUS
    assert result.project is None
    assert result.claims == []
    assert result.sources == []
    assert len(result.candidates) == 1


def test_unavailable_search_is_partial_even_when_article_has_a_fact():
    class Down:
        def search(self, query, *, count):
            from scripts.ecocompute_research.discovery import SearchError
            raise SearchError("provider_error", "Unavailable")

    result = run_research(
        IntakeRequest(mode="text", location="Pine Island, MN",
                      article_text="Google plans a 780-megawatt data center in Pine Island, MN."),
        provider=Down(), gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.PARTIAL
    assert len(result.sources) == 1
    assert any("provider_error" in note for note in result.limitations)


def test_second_state_project_keeps_unrelated_search_result_out():
    class MixedProvider:
        def search(self, query, *, count):
            return [
                SearchHit(title="Acme data center in Ashburn, Virginia",
                          url="https://example.com/ashburn",
                          description="Acme data center in Ashburn, VA"),
                SearchHit(title="Acme data center in Pine Island, Minnesota",
                          url="https://example.com/pine-island",
                          description="Acme data center in Pine Island, MN"),
            ]

    def fetch(url):
        if "ashburn" in url:
            return FetchedDocument(url=url, media_type="text/plain", text=(
                "Acme proposes a 250 MW data center in Ashburn, Virginia. "
                "The Ashburn data center has a planned 250 MW facility capacity."
            ))
        raise AssertionError("Unrelated location should not be fetched")

    result = run_research(
        IntakeRequest(mode="text", location="Ashburn, VA",
                      article_text="Acme proposes a 250 MW data center in Ashburn, Virginia."),
        provider=MixedProvider(), fetcher=fetch,
        gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.project.location.state == "VA"
    assert len(result.sources) == 2
    assert all("pine-island" not in str(source.url) for source in result.sources)
    assert all(claim.value != 780 for claim in result.claims)


def test_inaccessible_article_returns_honest_candidate_lead():
    def inaccessible(url):
        raise FetchError("access_denied", "The article could not be accessed")

    result = run_research(
        IntakeRequest(mode="url", location="Pine Island, MN",
                      article_url="https://example.com/blocked-article"),
        provider=FakeProvider(), fetcher=inaccessible,
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.AMBIGUOUS
    assert result.project is None
    assert result.sources == []
    assert result.claims == []
    assert len(result.candidates) == 1
    assert any("could not be accessed" in note for note in result.limitations)
