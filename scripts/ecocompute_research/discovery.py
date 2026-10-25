"""Bounded project-specific search using a replaceable provider."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
import os
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from pydantic import Field

from .models import ProjectIdentity, StrictModel


BRAVE_WEB_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class SearchError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class SearchHit(StrictModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    description: str = ""
    query: str = ""
    page_date: date | None = None
    relevance_score: int = 0


class SearchProvider(Protocol):
    def search(self, query: str, *, count: int) -> list[SearchHit]: ...


class BraveSearchProvider:
    """Brave Web Search API adapter; no mock results in production."""

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY")
        self.client = client

    def search(self, query: str, *, count: int) -> list[SearchHit]:
        if not self.api_key:
            raise SearchError("not_configured", "BRAVE_SEARCH_API_KEY is not configured")
        if not 1 <= count <= 20:
            raise ValueError("Brave count must be between 1 and 20")
        owned = self.client is None
        client = self.client or httpx.Client(timeout=10.0, trust_env=False)
        try:
            response = client.get(
                BRAVE_WEB_ENDPOINT,
                params={"q": query[:600], "count": count, "country": "US",
                        "search_lang": "en", "result_filter": "web"},
                headers={"X-Subscription-Token": self.api_key, "Accept": "application/json"},
            )
            if response.status_code != 200:
                raise SearchError("provider_error", f"Search provider returned HTTP {response.status_code}")
            try:
                rows = response.json().get("web", {}).get("results", [])
                if not isinstance(rows, list):
                    raise ValueError("results is not a list")
            except (ValueError, AttributeError) as exc:
                raise SearchError("invalid_response", "Search provider returned invalid JSON") from exc
            hits: list[SearchHit] = []
            for row in rows[:count]:
                if not isinstance(row, dict) or not row.get("title") or not row.get("url"):
                    continue
                raw_date = row.get("page_age")
                try:
                    page_date = date.fromisoformat(raw_date[:10]) if isinstance(raw_date, str) else None
                except ValueError:
                    page_date = None
                hits.append(SearchHit(
                    title=row["title"], url=row["url"],
                    description=row.get("description") or "", query=query,
                    page_date=page_date,
                ))
            return hits
        except httpx.RequestError as exc:
            raise SearchError("request_failed", "Search provider could not be reached") from exc
        finally:
            if owned:
                client.close()


class DiscoveryStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class DiscoveryResult(StrictModel):
    status: DiscoveryStatus
    queries: list[str]
    hits: list[SearchHit]
    warnings: list[str] = Field(default_factory=list)


def make_queries(project: ProjectIdentity, *, max_queries: int = 8) -> list[str]:
    location = project.location
    place = " ".join(part for part in [location.city or location.county,
                                        location.state] if part)
    identity = " ".join(part for part in [project.developer, place] if part)
    if not identity:
        return []
    prefix = f'"{project.developer}" "{location.city}"' if project.developer and location.city else identity
    subjects = [
        "data center", "data center megawatts electricity utility",
        "data center water cooling permit", "data center electric service agreement tariff",
        "data center planning zoning environmental review",
        "data center tax incentives jobs", "data center transmission substation",
        "data center filetype:pdf",
    ]
    queries = [f"{prefix} {subject}" for subject in subjects]
    return queries[:max_queries]


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query)
             if not key.lower().startswith(("utm_", "fbclid", "gclid"))]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/",
                       urlencode(query), ""))


def score_hit(hit: SearchHit, project: ProjectIdentity) -> int:
    """A search snippet is a lead, not evidence; reject clear site mismatch."""
    content = f"{hit.title} {hit.description} {hit.url}".casefold()
    location = project.location
    city = location.city.casefold() if location.city else None
    state = location.state.casefold() if location.state else None
    developer = project.developer.casefold() if project.developer else None
    aliases = [alias.casefold() for alias in project.aliases]
    if city and city not in content and not any(alias in content for alias in aliases):
        return 0
    if state and state not in content and not city:
        return 0
    score = (4 if city and city in content else 0) + (2 if developer and developer in content else 0)
    score += 3 if any(alias in content for alias in aliases) else 0
    score += 1 if "data center" in content or "datacenter" in content else 0
    return score


def discover_sources(
    project: ProjectIdentity,
    provider: SearchProvider,
    *,
    max_queries: int = 8,
    hits_per_query: int = 10,
    max_hits: int = 30,
) -> DiscoveryResult:
    if not 1 <= max_queries <= 20 or not 1 <= hits_per_query <= 20 or not 1 <= max_hits <= 100:
        raise ValueError("Search breadth is outside configured bounds")
    queries = make_queries(project, max_queries=max_queries)
    if not queries:
        return DiscoveryResult(status=DiscoveryStatus.PARTIAL, queries=[], hits=[],
                               warnings=["Project identity lacks enough detail for search"])
    found: dict[str, SearchHit] = {}
    warnings: list[str] = []
    for query in queries:
        try:
            hits = provider.search(query, count=hits_per_query)
        except SearchError as exc:
            warnings.append(f"{exc.code}: {exc}")
            if exc.code == "not_configured":
                break
            continue
        for hit in hits:
            score = score_hit(hit, project)
            if score < 4:
                continue
            key = canonical_url(hit.url)
            ranked = hit.model_copy(update={"relevance_score": score})
            if key not in found or found[key].relevance_score < score:
                found[key] = ranked
        if len(found) >= max_hits:
            break
    ordered = sorted(found.values(), key=lambda hit: hit.relevance_score, reverse=True)[:max_hits]
    return DiscoveryResult(
        status=DiscoveryStatus.PARTIAL if warnings else DiscoveryStatus.COMPLETE,
        queries=queries, hits=ordered, warnings=warnings,
    )
