"""Gemini grounding yields URL leads, never evidence from generated prose."""

import httpx
import pytest

from scripts.ecocompute_research.discovery import SearchError
from scripts.ecocompute_research.grounded_search import GeminiGroundedSearchProvider


def test_google_grounding_request_and_cited_urls_only():
    cited = "Google data center in Pine Island, MN has a filing."
    def answer(request: httpx.Request):
        assert request.url.path == "/v1beta/models/gemini-2.5-flash:generateContent"
        assert request.headers["x-goog-api-key"] == "test-key"
        body = __import__("json").loads(request.content)
        assert body["tools"] == [{"google_search": {}}]
        return httpx.Response(200, json={"candidates": [
            {"content": {"parts": [{"text": "A generated answer with an uncited URL https://uncited.example/wrong"}]},
             "groundingMetadata": {
                 "groundingChunks": [{"web": {"uri": "https://example.com/filing", "title": "Filing"}},
                                     {"web": {"uri": "javascript:alert(1)", "title": "Bad"}}],
                 "groundingSupports": [{"segment": {"text": cited}, "groundingChunkIndices": [0]}],
             }},
        ]})

    with httpx.Client(transport=httpx.MockTransport(answer)) as client:
        hits = GeminiGroundedSearchProvider(api_key="test-key", client=client).search(
            "Google Pine Island data center", count=2)
    assert len(hits) == 1
    assert hits[0].url == "https://example.com/filing"
    assert hits[0].description == cited


def test_no_citations_is_a_partial_search_failure():
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"candidates": [
            {"content": {"parts": [{"text": "A claim"}]}, "groundingMetadata": {}},
        ]})
    )) as client:
        provider = GeminiGroundedSearchProvider(api_key="test-key", client=client)
        with pytest.raises(SearchError, match="no usable cited URLs") as error:
            provider.search("Pine Island", count=3)
    assert error.value.code == "no_citations"


def test_no_key_reports_configuration_error():
    provider = GeminiGroundedSearchProvider(api_key="")
    with pytest.raises(SearchError) as error:
        provider.search("Pine Island", count=2)
    assert error.value.code == "not_configured"


@pytest.mark.parametrize("status,code", [(404, "model_unavailable"), (429, "quota_exhausted")])
def test_account_access_errors_are_distinct(status, code):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={"error": {"message": "provider detail"}})
    )) as client:
        provider = GeminiGroundedSearchProvider(api_key="test-key", client=client)
        with pytest.raises(SearchError) as error:
            provider.search("Pine Island", count=2)
    assert error.value.code == code
