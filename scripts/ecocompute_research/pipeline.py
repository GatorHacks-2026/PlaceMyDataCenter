"""Bounded orchestration from one seed input to a cited research result."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
import re
from typing import Callable
from urllib.parse import urlsplit

from pydantic import Field

from .collection import CollectedSource, collect_sources
from .discovery import (
    BraveSearchProvider, SearchHit, SearchProvider, canonical_url,
    discover_seed_links, discover_sources,
)
from .estimates import assess_scale
from .fact_extractor import extract_facts
from .gemini import GeminiFactExtractor
from .grounded_search import GeminiGroundedSearchProvider
from .tavily_search import TavilySearchProvider
from .identity import IdentificationStatus, identify_project
from .intake import IntakeRequest, read_input
from .models import Location, ProjectIdentity, ResearchResult, ResearchStatus, SearchLead, SourceRecord, SourceType, StrictModel
from .reconciliation import reconcile_claims
from .report import build_summary, find_missing_fields
from .url_fetch import FetchedDocument, fetch_url
from .zip_lookup import resolve_us_zip


class ResearchConfig(StrictModel):
    max_queries: int = Field(default=6, ge=1, le=20)
    hits_per_query: int = Field(default=8, ge=1, le=20)
    max_hits: int = Field(default=24, ge=1, le=100)
    max_sources: int = Field(default=10, ge=1, le=50)
    max_linked_sources: int = Field(default=8, ge=1, le=20)


def _seed_source(intake) -> CollectedSource | None:
    if not intake.text:
        return None
    url = intake.article_url if intake.status == "ready" else None
    identity = url or f"user_{sha256(intake.text.encode()).hexdigest()[:12]}"
    source_id = f"source_{sha256(identity.encode()).hexdigest()[:12]}"
    host = urlsplit(url).hostname if url else None
    source = SourceRecord(
        id=source_id, title="User-provided article or document",
        source_type=SourceType.USER_SUPPLIED,
        independent_origin=host or source_id,
        url=url,
        retrieved_at=datetime.now(timezone.utc),
    )
    return CollectedSource(source=source, text=intake.text,
                           relevance_reason="User-provided seed document")


def run_research(
    request: IntakeRequest,
    *,
    provider: SearchProvider | None = None,
    fetcher: Callable[[str], FetchedDocument] = fetch_url,
    gemini: GeminiFactExtractor | None = None,
    config: ResearchConfig | None = None,
    zip_resolver: Callable[[str], Location] = resolve_us_zip,
) -> ResearchResult:
    """Research the exact project; never claim completeness after a failed stage."""
    config = config or ResearchConfig()
    intake = read_input(request, fetcher=fetcher, zip_resolver=zip_resolver)
    location_context = dict(location_input=intake.location_input,
                            location_hint=intake.location,
                            location_source=intake.location_source)
    limitations = [warning.message for warning in intake.warnings]
    identity = identify_project(intake.text, intake.location)
    if identity.status == IdentificationStatus.AMBIGUOUS:
        return ResearchResult(status=ResearchStatus.AMBIGUOUS,
                              candidates=[item.project for item in identity.candidates],
                              limitations=[identity.explanation, *limitations],
                              **location_context)

    search_provider = os.environ.get("RESEARCH_SEARCH_PROVIDER", "tavily").lower()
    provider = provider or (GeminiGroundedSearchProvider() if search_provider == "gemini" else
                            BraveSearchProvider() if search_provider == "brave" else TavilySearchProvider())
    if isinstance(provider, TavilySearchProvider) and not provider.api_key and config.max_queries > 2:
        config = config.model_copy(update={"max_queries": 2})
    if identity.status != IdentificationStatus.SELECTED:
        location_project = ProjectIdentity(location=intake.location)
        leads = discover_sources(location_project, provider,
                                 max_queries=config.max_queries,
                                 hits_per_query=config.hits_per_query,
                                 max_hits=config.max_hits)
        candidates: dict[tuple, ProjectIdentity] = {}
        for hit in leads.hits:
            found = identify_project(f"{hit.title}. {hit.description}", intake.location)
            for item in found.candidates:
                project = item.project
                key = (project.developer, project.location.city, project.location.state)
                candidates[key] = project
        search_unavailable = (request.mode == "manual_location" and not leads.hits and
                              any("not_configured" in warning for warning in leads.warnings))
        search_leads = [SearchLead(title=hit.title, url=hit.url, description=hit.description)
                        for hit in leads.hits[:8]
                        if urlsplit(hit.url).scheme in {"http", "https"} and urlsplit(hit.url).hostname]
        # A city or resolved ZIP can identify one project from search leads.
        # Fetch the article and pass it through the normal evidence pipeline;
        # a snippet alone never becomes a claim. Broad state searches still
        # require the user to choose a source.
        if request.mode == "manual_location" and intake.location.city and len(candidates) == 1:
            candidate = next(iter(candidates.values()))
            if candidate.location.city and candidate.location.state:
                for hit in leads.hits:
                    found = identify_project(f"{hit.title}. {hit.description}", intake.location)
                    if (found.status != IdentificationStatus.SELECTED or not found.selected or
                            (candidate.developer and (found.selected.developer or "").casefold()
                             != candidate.developer.casefold())):
                        continue
                    class CachedLeadsProvider:
                        def search(self, query: str, *, count: int) -> list[SearchHit]:
                            return leads.hits[:count]
                    researched = run_research(
                        IntakeRequest(mode="url", location=request.location, article_url=hit.url),
                        provider=CachedLeadsProvider(), fetcher=fetcher, gemini=gemini,
                        config=config, zip_resolver=zip_resolver,
                    )
                    if (researched.project and researched.sources and
                            (not candidate.developer or (researched.project.developer or "").casefold()
                             == candidate.developer.casefold())):
                        researched.limitations.append(
                            "The starting article was found by web search from a location-only input.")
                        return researched
                    break
        return ResearchResult(
            status=(ResearchStatus.AMBIGUOUS if candidates else
                    ResearchStatus.FAILED if search_unavailable else ResearchStatus.PARTIAL),
            candidates=list(candidates.values()), search_leads=search_leads,
            limitations=[*(
                ["Web search is unavailable. Add an article URL, pasted text, or PDF to research this project now."]
                if search_unavailable else [identity.explanation]
            ), *limitations, *leads.warnings,
                         "Search snippets are candidate leads, not reviewed project evidence."],
            **location_context,
        )

    project = identity.selected
    seed = _seed_source(intake)
    collected = [seed] if seed else []
    leads = discover_sources(project, provider,
                             max_queries=config.max_queries,
                             hits_per_query=config.hits_per_query,
                             max_hits=config.max_hits)
    seed_url = canonical_url(intake.article_url) if intake.article_url else None
    explicit = [SearchHit(title=f"Additional source: {urlsplit(url).hostname}",
                          url=url, query="user_additional_url")
                for url in request.additional_urls]
    linked = (discover_seed_links(intake.seed_links, intake.article_url, project,
                                  max_links=config.max_linked_sources)
              if intake.article_url else [])
    additional = []
    seen_urls = {seed_url} if seed_url else set()
    for hit in [*explicit, *linked, *leads.hits]:
        key = canonical_url(hit.url)
        if key not in seen_urls:
            additional.append(hit)
            seen_urls.add(key)
    collection = collect_sources(additional, project, fetcher=fetcher,
                                 max_sources=config.max_sources)
    seed_text = re.sub(r"\s+", " ", intake.text or "").casefold()
    for item in collection.sources:
        if ((seed_url and item.source.url and canonical_url(str(item.source.url)) == seed_url) or
                re.sub(r"\s+", " ", item.text).casefold() == seed_text):
            collection.skipped[str(item.source.url)] = "Duplicate of the starting document"
            continue
        collected.append(item)
    limitations.extend(leads.warnings)
    limitations.extend(f"{url}: {reason}" for url, reason in collection.skipped.items())

    if gemini is None:
        gemini = GeminiFactExtractor()
    facts = extract_facts(collected, project, gemini=gemini)
    limitations.extend(facts.warnings)
    if not gemini.api_key:
        limitations.append("Gemini was not configured; deterministic extraction has limited coverage.")
    sources = [item.source for item in collected]
    reconciled = reconcile_claims(facts.claims, sources)
    scale = assess_scale(reconciled.claims)
    claims = [*reconciled.claims, *([scale.proxy_claim] if scale.proxy_claim else [])]
    missing = find_missing_fields(claims, sources)
    complete = (intake.status == "ready" and leads.status.value == "complete" and
                collection.status.value == "complete" and not facts.warnings and
                len(collected) > (1 if seed else 0) and bool(gemini.api_key))
    status = ResearchStatus.COMPLETE if complete else ResearchStatus.PARTIAL
    summary = build_summary(project, sources, claims, reconciled.conflicts, missing, status)
    return ResearchResult(
        status=status, project=project, sources=sources, claims=claims,
        conflicts=reconciled.conflicts, missing_fields=missing,
        summary=summary, limitations=limitations, **location_context,
    )
