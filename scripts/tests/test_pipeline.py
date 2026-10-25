"""Offline end-to-end orchestration through the research services."""

from scripts.ecocompute_research.discovery import SearchHit
from scripts.ecocompute_research.gemini import GeminiFactExtractor
from scripts.ecocompute_research.html_text import ArticleLink
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
    assert str(result.search_leads[0].url) == "https://example.com/google-pine-island"


def test_city_only_search_fetches_one_candidate_before_extracting_claims():
    fetched = []
    def fetch(url):
        fetched.append(url)
        return FetchedDocument(url=url, media_type="text/plain", text=(
            "Google plans a 780-megawatt data center in Pine Island, Minnesota."
        ))

    result = run_research(
        IntakeRequest(mode="manual_location", location="Pine Island, MN"),
        provider=FakeProvider(), fetcher=fetch, gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert fetched == ["https://example.com/google-pine-island"]
    assert result.project and result.project.developer == "Google"
    assert len(result.sources) == 1
    assert any(claim.field == "electricity.capacity_mw" for claim in result.claims)


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


def test_el_paso_pipeline_keeps_gas_generation_out_of_facility_capacity():
    class Down:
        def search(self, query, *, count):
            from scripts.ecocompute_research.discovery import SearchError
            raise SearchError("provider_error", "Unavailable")

    result = run_research(
        IntakeRequest(mode="text", location="El Paso, TX", article_text=(
            "Meta plans a 1-gigawatt data center in El Paso, Texas. "
            "El Paso Electric proposed a 366-megawatt natural gas facility "
            "to power Meta's data center in El Paso."
        )),
        provider=Down(), gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.PARTIAL
    assert {(claim.field, claim.value) for claim in result.claims if claim.unit == "MW"} == {
        ("electricity.capacity_mw", 1000),
        ("energy_plan.gas_generation_capacity_mw", 366),
    }
    assert result.conflicts == []


def test_texas_with_el_paso_article_identifies_project_and_keeps_seed():
    class NoSearch:
        def search(self, query, *, count):
            return []

    result = run_research(
        IntakeRequest(mode="url", location="Texas",
                      article_url="https://example.com/el-paso-meta"),
        provider=NoSearch(), fetcher=lambda url: FetchedDocument(
            url=url, media_type="text/plain", text=(
                "While Texas officials paused permits, Meta's $10 billion, "
                "1-gigawatt data center in northeast El Paso moved ahead."
            )), gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.project.developer == "Meta"
    assert result.project.location.city == "El Paso"
    assert len(result.sources) == 1
    assert any(claim.field == "electricity.capacity_mw" and claim.value == 1000
               for claim in result.claims)


def test_location_only_without_search_provider_explains_next_step():
    class NoKey:
        def search(self, query, *, count):
            from scripts.ecocompute_research.discovery import SearchError
            raise SearchError("not_configured", "BRAVE_SEARCH_API_KEY is not configured")

    result = run_research(
        IntakeRequest(mode="manual_location", location="Texas"),
        provider=NoKey(), config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.FAILED
    assert "Add an article URL" in result.limitations[0]


def test_explicit_and_article_link_sources_work_without_search_key():
    class Down:
        def search(self, query, *, count):
            from scripts.ecocompute_research.discovery import SearchError
            raise SearchError("not_configured", "No search key")

    seed_url = "https://news.example/pine-island"
    city_url = "https://city.example.gov/project"
    utility_url = "https://utility.example.com/filing"
    fetched = []

    def fetch(url):
        fetched.append(url)
        if url == seed_url:
            return FetchedDocument(url=url, media_type="text/html", text=(
                "Google plans a 780 MW data center in Pine Island, Minnesota."
            ), links=(
                ArticleLink(city_url, "city project page",
                            "Pine Island city page about Google's data center."),
                ArticleLink(utility_url, "utility filing",
                            "Pine Island utility filing for Google's data center."),
            ))
        if url == city_url:
            text = "Google proposed a data center in Pine Island, MN. The city reviewed the site."
        else:
            text = "Google proposed a data center in Pine Island, MN. The utility reviewed service."
        return FetchedDocument(url=url, media_type="text/plain", text=text)

    result = run_research(
        IntakeRequest(mode="url", location="Pine Island, MN", article_url=seed_url,
                      additional_urls=[city_url]),
        provider=Down(), fetcher=fetch, gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert result.status == ResearchStatus.PARTIAL
    assert {str(source.url) for source in result.sources} == {seed_url, city_url, utility_url}
    assert fetched == [seed_url, city_url, utility_url]
    assert any("not_configured" in note for note in result.limitations)


def test_additional_url_redirecting_to_seed_is_not_a_second_source():
    class Down:
        def search(self, query, *, count):
            from scripts.ecocompute_research.discovery import SearchError
            raise SearchError("not_configured", "No search key")

    seed_url = "https://example.com/project"
    def fetch(url):
        return FetchedDocument(
            url=seed_url, media_type="text/plain",
            text="Google plans a 780 MW data center in Pine Island, Minnesota.",
        )

    result = run_research(
        IntakeRequest(mode="url", location="Pine Island, MN", article_url=seed_url,
                      additional_urls=["https://example.com/redirect-to-project"]),
        provider=Down(), fetcher=fetch, gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert len(result.sources) == 1
    assert any("Duplicate of the starting document" in note for note in result.limitations)


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


def test_gemini_search_is_explicit_opt_in(monkeypatch):
    from scripts.ecocompute_research import pipeline

    used = []
    class Grounded(FakeProvider):
        def search(self, query, *, count):
            used.append(query)
            return super().search(query, count=count)

    monkeypatch.setenv("RESEARCH_SEARCH_PROVIDER", "gemini")
    monkeypatch.setattr(pipeline, "GeminiGroundedSearchProvider", Grounded)
    result = run_research(
        IntakeRequest(mode="text", location="Pine Island, MN",
                      article_text="Google proposes a data center in Pine Island, MN."),
        fetcher=lambda url: FetchedDocument(
            url=url, media_type="text/plain",
            text="Google proposes a data center in Pine Island, MN. The utility filed a service plan."),
        gemini=GeminiFactExtractor(api_key=""),
        config=ResearchConfig(max_queries=1),
    )
    assert used
    assert len(result.sources) == 2
