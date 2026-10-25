"""Tavily Search adapter; keyless access is the default for small demos.

Search results are candidate leads. The research pipeline fetches source pages
before treating their contents as evidence.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx

from .discovery import SearchError, SearchHit


TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"


class TavilySearchProvider:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("TAVILY_API_KEY", "")
        self.client = client

    def search(self, query: str, *, count: int) -> list[SearchHit]:
        if not 1 <= count <= 20:
            raise ValueError("Tavily count must be between 1 and 20")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["X-Tavily-Access-Mode"] = "keyless"
        owned = self.client is None
        client = self.client or httpx.Client(timeout=15.0, trust_env=False)
        try:
            response = client.post(
                TAVILY_SEARCH_ENDPOINT,
                headers=headers,
                json={"query": query[:600], "search_depth": "basic", "max_results": count,
                      "include_answer": False, "include_raw_content": False},
            )
            if response.status_code in {429, 432}:
                raise SearchError("quota_exhausted", "Free web-search limit reached; try again later")
            if response.status_code in {401, 403}:
                raise SearchError("provider_error", "Tavily rejected the configured API key")
            if response.status_code != 200:
                raise SearchError("provider_error", f"Tavily search returned HTTP {response.status_code}")
            try:
                rows = response.json()["results"]
                if not isinstance(rows, list):
                    raise ValueError("results is not a list")
            except (ValueError, KeyError, TypeError) as exc:
                raise SearchError("invalid_response", "Tavily search returned invalid JSON") from exc
            hits = []
            for row in rows[:count]:
                if not isinstance(row, dict) or not row.get("title") or not row.get("url"):
                    continue
                parsed = urlsplit(row["url"])
                if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                    continue
                hits.append(SearchHit(title=str(row["title"])[:300], url=row["url"],
                                      description=str(row.get("content") or "")[:1000], query=query))
            return hits
        except httpx.RequestError as exc:
            raise SearchError("request_failed", "Tavily search could not be reached") from exc
        finally:
            if owned:
                client.close()
