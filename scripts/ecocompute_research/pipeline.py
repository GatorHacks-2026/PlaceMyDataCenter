"""Bounded orchestration from one seed input to a cited research result."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Callable
from urllib.parse import urlsplit

from pydantic import Field

from .collection import CollectedSource, collect_sources
from .discovery import BraveSearchProvider, SearchProvider, canonical_url, discover_sources
from .estimates import assess_scale
from .fact_extractor import extract_facts
from .gemini import GeminiFactExtractor
from .identity import IdentificationStatus, identify_project
from .intake import IntakeRequest, read_input
from .models import ProjectIdentity, ResearchResult, ResearchStatus, SourceRecord, SourceType, StrictModel
from .reconciliation import reconcile_claims
from .report import build_summary, find_missing_fields
from .url_fetch import FetchedDocument, fetch_url


class ResearchConfig(StrictModel):
    max_queries: int = Field(default=6, ge=1, le=20)
    hits_per_query: int = Field(default=8, ge=1, le=20)
    max_hits: int = Field(default=24, ge=1, le=100)
    max_sources: int = Field(default=10, ge=1, le=50)


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
) -> ResearchResult:
    """Research the exact project; never claim completeness after a failed stage."""
    config = config or ResearchConfig()
    intake = read_input(request, fetcher=fetcher)
    limitations = [warning.message for warning in intake.warnings]
    identity = identify_project(intake.text, intake.location)
    if identity.status == IdentificationStatus.AMBIGUOUS:
        return ResearchResult(status=ResearchStatus.AMBIGUOUS,
                              candidates=[item.project for item in identity.candidates],
                              limitations=[identity.explanation, *limitations])

    provider = provider or BraveSearchProvider()
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
        return ResearchResult(
            status=ResearchStatus.AMBIGUOUS if candidates else ResearchStatus.PARTIAL,
            candidates=list(candidates.values()),
            limitations=[identity.explanation, *limitations, *leads.warnings,
                         "Search snippets are candidate leads, not reviewed project evidence."],
        )

    project = identity.selected
    seed = _seed_source(intake)
    collected = [seed] if seed else []
    leads = discover_sources(project, provider,
                             max_queries=config.max_queries,
                             hits_per_query=config.hits_per_query,
                             max_hits=config.max_hits)
    seed_url = canonical_url(intake.article_url) if intake.article_url else None
    additional = [hit for hit in leads.hits if canonical_url(hit.url) != seed_url]
    collection = collect_sources(additional, project, fetcher=fetcher,
                                 max_sources=config.max_sources)
    collected.extend(collection.sources)
    limitations.extend(leads.warnings)
    limitations.extend(collection.skipped.values())

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
                bool(collection.sources) and bool(gemini.api_key))
    status = ResearchStatus.COMPLETE if complete else ResearchStatus.PARTIAL
    summary = build_summary(project, sources, claims, reconciled.conflicts, missing, status)
    return ResearchResult(
        status=status, project=project, sources=sources, claims=claims,
        conflicts=reconciled.conflicts, missing_fields=missing,
        summary=summary, limitations=limitations,
    )
