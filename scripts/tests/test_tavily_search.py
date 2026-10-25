import httpx
import pytest

from scripts.ecocompute_research.discovery import SearchError
from scripts.ecocompute_research.tavily_search import TavilySearchProvider


def test_keyless_tavily_results_are_candidate_leads():
    def respond(request):
        assert request.headers["X-Tavily-Access-Mode"] == "keyless"
        assert "Authorization" not in request.headers
        assert request.url.path == "/search"
        assert b'"search_depth":"basic"' in request.content
        return httpx.Response(200, json={"results": [
            {"title": "El Paso data center", "url": "https://example.com/project",
             "content": "Meta data center in El Paso, TX"},
            {"title": "Unsafe result", "url": "javascript:alert(1)", "content": "ignored"},
        ]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        results = TavilySearchProvider(api_key="", client=client).search("El Paso data center", count=5)
    assert len(results) == 1
    assert results[0].url == "https://example.com/project"
    assert results[0].description == "Meta data center in El Paso, TX"


def test_keyless_limit_is_reported():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429))) as client:
        with pytest.raises(SearchError) as error:
            TavilySearchProvider(api_key="", client=client).search("data center", count=5)
    assert error.value.code == "quota_exhausted"
