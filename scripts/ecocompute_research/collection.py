"""Collect relevant public documents while retaining source provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import re
import time
from typing import Callable
from urllib.parse import urlsplit

from pydantic import Field

from .discovery import SearchHit, canonical_url
from .identity import IdentificationStatus, identify_project
from .models import ProjectIdentity, SourceRecord, SourceType, StrictModel
from .url_fetch import FetchError, FetchedDocument, fetch_url


class CollectionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"


class CollectedSource(StrictModel):
    source: SourceRecord
    text: str = Field(min_length=1)
    relevance_reason: str


class CollectionResult(StrictModel):
    status: CollectionStatus
    sources: list[CollectedSource]
    skipped: dict[str, str] = Field(default_factory=dict)


def _source_type(url: str, project: ProjectIdentity) -> SourceType:
    host = urlsplit(url).hostname or ""
    if host.endswith(".gov"):
        return SourceType.GOVERNMENT
    developer_words = (project.developer or "").split()
    company = developer_words[0].casefold() if developer_words else ""
    if company and company in host.casefold():
        return SourceType.COMPANY
    return SourceType.OTHER


def _relevance_reason(text: str, project: ProjectIdentity) -> str | None:
    identity = identify_project(text, project.location)
    if identity.status == IdentificationStatus.SELECTED:
        selected = identity.selected
        if project.developer and selected.developer and project.developer.casefold() != selected.developer.casefold():
            return None
        if project.developer and project.developer.casefold() not in text.casefold():
            return None
        return "Document names a data center at the target location"
    if identity.status == IdentificationStatus.AMBIGUOUS:
        return None
    if identity.candidates:
        # A document that explicitly identifies only another project cannot
        # pass the looser text fallback.
        return None
    # Filings may not use a sentence shaped like a news announcement. Keep
    # only documents that still mention the exact city and developer.
    body = text.casefold()
    city = project.location.city
    if city and city.casefold() in body and project.developer and project.developer.casefold() in body:
        if "data center" in body or "datacenter" in body:
            return "Document mentions target city, developer, and data center"
    return None


def collect_sources(
    hits: list[SearchHit],
    project: ProjectIdentity,
    *,
    fetcher: Callable[[str], FetchedDocument] = fetch_url,
    max_sources: int = 12,
    retries: int = 1,
    min_interval_seconds: float = 0.25,
    cache: dict[str, FetchedDocument] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> CollectionResult:
    if not 1 <= max_sources <= 50 or not 0 <= retries <= 2 or min_interval_seconds < 0:
        raise ValueError("Collection limits are outside allowed bounds")
    seen_urls: set[str] = set()
    seen_text: set[str] = set()
    collected: list[CollectedSource] = []
    skipped: dict[str, str] = {}
    access_failures = False
    attempts = 0
    for hit in hits:
        if len(collected) >= max_sources:
            break
        key = canonical_url(hit.url)
        if key in seen_urls:
            continue
        seen_urls.add(key)
        document = cache.get(key) if cache is not None else None
        if document is None:
            for attempt in range(retries + 1):
                if attempts:
                    sleeper(min_interval_seconds)
                attempts += 1
                try:
                    document = fetcher(hit.url)
                    if cache is not None:
                        cache[key] = document
                    break
                except FetchError as exc:
                    if exc.code == "request_failed" and attempt < retries:
                        continue
                    skipped[hit.url] = f"{exc.code}: {exc}"
                    access_failures = True
                    break
        if document is None:
            continue
        normalized = re.sub(r"\s+", " ", document.text).casefold()
        digest = sha256(normalized.encode()).hexdigest()
        if digest in seen_text:
            skipped[hit.url] = "Duplicate document text"
            continue
        reason = _relevance_reason(document.text, project)
        if reason is None:
            skipped[hit.url] = "Document did not establish the target project"
            continue
        seen_text.add(digest)
        url = document.url
        host = urlsplit(url).hostname or "unknown"
        source = SourceRecord(
            id=f"source_{sha256(canonical_url(url).encode()).hexdigest()[:12]}",
            title=hit.title,
            source_type=_source_type(url, project),
            independent_origin=host,
            url=url,
            retrieved_at=datetime.now(timezone.utc),
        )
        collected.append(CollectedSource(source=source, text=document.text,
                                         relevance_reason=reason))
    return CollectionResult(
        status=CollectionStatus.PARTIAL if access_failures else CollectionStatus.COMPLETE,
        sources=collected,
        skipped=skipped,
    )
