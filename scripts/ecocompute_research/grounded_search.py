"""Gemini Google Search grounding as a source-lead provider.

Only cited URLs become leads. Generated answer text is never source evidence.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import httpx

from .discovery import SearchError, SearchHit


GENERATE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"


class GeminiGroundedSearchProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_SEARCH_MODEL", "gemini-2.5-flash")
        self.client = client

    def search(self, query: str, *, count: int) -> list[SearchHit]:
        if not self.api_key:
            raise SearchError("not_configured", "GEMINI_API_KEY is not configured")
        if not 1 <= count <= 20:
            raise ValueError("Search count must be between 1 and 20")
        owned = self.client is None
        client = self.client or httpx.Client(timeout=30.0, trust_env=False)
        try:
            response = client.post(
                GENERATE_ENDPOINT.format(self.model),
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": (
                        "Search the web for public documents about this exact data center project. "
                        "Give concise project-specific facts with cited sources. "
                        "Prefer official utility, government, company, and independent news URLs. "
                        "Do not invent sources. Search topic: " + query[:600]
                    )}]}],
                    "tools": [{"google_search": {}}],
                },
            )
            if response.status_code != 200:
                if response.status_code == 404:
                    raise SearchError("model_unavailable", "Configured Gemini search model is unavailable to this account")
                if response.status_code == 429:
                    raise SearchError("quota_exhausted", "Gemini Google Search quota is unavailable or exhausted")
                raise SearchError("provider_error", f"Gemini search returned HTTP {response.status_code}")
            try:
                candidates = response.json()["candidates"]
                if not isinstance(candidates, list):
                    raise ValueError("candidates must be a list")
                hits = _cited_hits(candidates, query, count)
            except (ValueError, KeyError, TypeError, AttributeError) as exc:
                raise SearchError("invalid_response", "Gemini search response was invalid") from exc
            if not hits:
                raise SearchError("no_citations", "Gemini search returned no usable cited URLs")
            return hits
        except httpx.RequestError as exc:
            raise SearchError("request_failed", "Gemini search could not be reached") from exc
        finally:
            if owned:
                client.close()


def _cited_hits(candidates: list[dict], query: str, count: int) -> list[SearchHit]:
    hits: dict[str, SearchHit] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        metadata = candidate.get("groundingMetadata") or {}
        chunks = metadata.get("groundingChunks") or []
        supports = metadata.get("groundingSupports") or []
        if not isinstance(chunks, list) or not isinstance(supports, list):
            continue
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict) or not isinstance(chunk.get("web"), dict):
                continue
            web = chunk["web"]
            url = web.get("uri")
            if not isinstance(url, str):
                continue
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            title = web.get("title")
            if not isinstance(title, str) or not title.strip():
                title = parsed.hostname
            passages = []
            for support in supports:
                if not isinstance(support, dict) or index not in support.get("groundingChunkIndices", []):
                    continue
                segment = support.get("segment") or {}
                sentence = segment.get("text") if isinstance(segment, dict) else None
                if isinstance(sentence, str) and sentence.strip():
                    passages.append(sentence.strip())
            description = " ".join(dict.fromkeys(passages))[:500]
            hits.setdefault(url, SearchHit(title=title[:200], url=url,
                                           description=description, query=query))
            if len(hits) >= count:
                return list(hits.values())
    return list(hits.values())
