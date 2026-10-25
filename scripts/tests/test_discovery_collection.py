"""Search and collection stay project-specific and bounded without network calls."""

import httpx

from scripts.ecocompute_research.collection import CollectionStatus, collect_sources
from scripts.ecocompute_research.discovery import (
    BraveSearchProvider, DiscoveryStatus, SearchError, SearchHit,
    discover_sources, make_queries,
)
from scripts.ecocompute_research.fixtures import pine_island_contract_fixture
from scripts.ecocompute_research.url_fetch import FetchError, FetchedDocument


PROJECT = pine_island_contract_fixture().project


def test_queries_use_project_company_place_and_topics():
    queries = make_queries(PROJECT)
    assert len(queries) == 8
    assert all("Google" in query and "Pine Island" in query for query in queries)
    assert any("water cooling" in query for query in queries)
    assert any("tariff" in query for query in queries)


def test_brave_adapter_uses_documented_endpoint_and_parses_results():
    def answer(request: httpx.Request):
        assert request.url.path == "/res/v1/web/search"
        assert request.headers["x-subscription-token"] == "test-key"
        assert request.url.params["q"] == "Google Pine Island data center"
        assert request.url.params["count"] == "2"
        return httpx.Response(200, json={"web": {"results": [
            {"title": "Pine Island filing", "url": "https://example.com/pine",
             "description": "Google data center in Pine Island, MN", "page_age": "2026-10-19"},
        ]}})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        provider = BraveSearchProvider(api_key="test-key", client=client)
        hits = provider.search("Google Pine Island data center", count=2)
    assert len(hits) == 1
    assert hits[0].page_date.isoformat() == "2026-10-19"


def test_search_without_key_reports_partial_not_fake_hits():
    provider = BraveSearchProvider(api_key="")
    provider.api_key = None
    result = discover_sources(PROJECT, provider)
    assert result.status == DiscoveryStatus.PARTIAL
    assert result.hits == []
    assert "not_configured" in result.warnings[0]


def test_discovery_deduplicates_urls_and_rejects_other_facility():
    class FakeProvider:
        def search(self, query, *, count):
            return [
                SearchHit(title="Google Pine Island data center", url="https://example.com/pine?utm_source=x",
                          description="Google project in Pine Island, MN"),
                SearchHit(title="Google Pine Island data center", url="https://example.com/pine",
                          description="Google project in Pine Island, MN"),
                SearchHit(title="Google Hermantown data center", url="https://example.com/hermantown",
                          description="Google project in Hermantown, MN"),
            ]

    result = discover_sources(PROJECT, FakeProvider(), max_queries=2)
    assert result.status == DiscoveryStatus.COMPLETE
    assert len(result.hits) == 1
    assert "pine" in result.hits[0].url


def test_collection_keeps_matching_source_and_rejects_unrelated_text():
    hits = [
        SearchHit(title="Pine Island proposal", url="https://example.com/pine"),
        SearchHit(title="Pine Island headline with wrong body", url="https://example.com/wrong"),
        SearchHit(title="Duplicate Pine Island proposal", url="https://example.org/copy"),
    ]
    text = "Google proposed a data center in Pine Island, Minnesota."
    def fetch(url):
        return FetchedDocument(
            url=url, media_type="text/html",
            text="Google proposed a data center in Hermantown, Minnesota." if "wrong" in url else text,
        )

    result = collect_sources(hits, PROJECT, fetcher=fetch, min_interval_seconds=0,
                             sleeper=lambda _: None)
    assert len(result.sources) == 1
    assert str(result.sources[0].source.url) == "https://example.com/pine"
    assert result.sources[0].source.retrieved_at.tzinfo is not None
    assert len(result.skipped) == 2
    assert result.status == CollectionStatus.PARTIAL


def test_collection_retries_transient_error_and_uses_cache():
    hit = SearchHit(title="Pine Island data center", url="https://example.com/pine")
    calls = 0
    cache = {}
    def fetch(url):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise FetchError("request_failed", "Temporary connection error")
        return FetchedDocument(url=url, media_type="text/plain",
                               text="Google proposed a data center in Pine Island, MN.")

    first = collect_sources([hit], PROJECT, fetcher=fetch, cache=cache,
                            min_interval_seconds=0, sleeper=lambda _: None)
    second = collect_sources([hit], PROJECT, fetcher=fetch, cache=cache,
                             min_interval_seconds=0, sleeper=lambda _: None)
    assert len(first.sources) == len(second.sources) == 1
    assert calls == 2


def test_provider_failure_does_not_erase_other_search_results():
    class SometimesFails:
        calls = 0
        def search(self, query, *, count):
            self.calls += 1
            if self.calls == 2:
                raise SearchError("provider_error", "Rate limited")
            return [SearchHit(title="Google Pine Island data center",
                              url="https://example.com/pine",
                              description="Google data center in Pine Island, MN")]

    result = discover_sources(PROJECT, SometimesFails(), max_queries=2)
    assert result.status == DiscoveryStatus.PARTIAL
    assert len(result.hits) == 1
    assert result.warnings
