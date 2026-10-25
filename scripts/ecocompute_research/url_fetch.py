"""Bounded public-page fetcher. It never proxies past an access denial."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
from typing import Callable
from urllib.parse import urljoin, urlsplit

import httpx

from .html_text import ArticleLink, parse_html


MAX_BODY_BYTES = 5_000_000
MAX_REDIRECTS = 3
USER_AGENT = "EcoComputeResearch/0.1 (+public-data-center-research)"
Resolver = Callable[[str], list[str]]


class FetchError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FetchedDocument:
    url: str
    media_type: str
    text: str
    links: tuple[ArticleLink, ...] = ()


def _resolve_addresses(host: str) -> list[str]:
    try:
        return list({item[4][0] for item in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)})
    except socket.gaierror as exc:
        raise FetchError("dns_failed", "The article hostname could not be resolved") from exc


def validate_public_url(url: str, *, resolver: Resolver = _resolve_addresses) -> str:
    """Reject private/local targets, including every resolved redirect host.

    DNS can change between validation and connection; deployment also needs
    network egress controls. This check is one defense, not a DNS pin.
    """
    if not isinstance(url, str) or any(ord(char) < 32 for char in url):
        raise FetchError("invalid_url", "Use a public HTTP or HTTPS URL")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise FetchError("invalid_url", "The article URL is malformed") from exc
    if (parts.scheme not in {"http", "https"} or not host or
            parts.username is not None or parts.password is not None):
        raise FetchError("invalid_url", "Use a public HTTP or HTTPS URL without credentials")
    if port is not None and port != (443 if parts.scheme == "https" else 80):
        raise FetchError("invalid_url", "Only standard HTTP and HTTPS ports are allowed")
    host = host.rstrip(".").lower()
    if (not host or "\\" in host or "%" in host or
            host in {"localhost", "metadata.google.internal"} or
            host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))):
        raise FetchError("unsafe_url", "Local or internal article URLs are not allowed")

    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        if "." not in host:
            raise FetchError("unsafe_url", "Use a public hostname") from None
        addresses = resolver(host)
    if not addresses:
        raise FetchError("dns_failed", "The article hostname has no address")
    try:
        if any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise FetchError("unsafe_url", "The article URL resolves to a non-public address")
    except ValueError as exc:
        if isinstance(exc, FetchError):
            raise
        raise FetchError("dns_failed", "The article hostname returned an invalid address") from exc
    return url


def fetch_url(
    url: str,
    *,
    client: httpx.Client | None = None,
    resolver: Resolver = _resolve_addresses,
    max_body_bytes: int = MAX_BODY_BYTES,
) -> FetchedDocument:
    """Read bounded HTML/text/PDF from a public URL, with checked redirects."""
    owned_client = client is None
    if client is None:
        client = httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0), trust_env=False,
                              follow_redirects=False)
    try:
        current = url
        seen: set[str] = set()
        for _ in range(MAX_REDIRECTS + 1):
            validate_public_url(current, resolver=resolver)
            if current in seen:
                raise FetchError("redirect_loop", "The article redirects in a loop")
            seen.add(current)
            try:
                with client.stream("GET", current, headers={"User-Agent": USER_AGENT}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        target = response.headers.get("location")
                        if not target:
                            raise FetchError("redirect_failed", "The article redirect has no target")
                        current = urljoin(current, target)
                        continue
                    if response.status_code != 200:
                        raise FetchError("http_error", f"Article request returned HTTP {response.status_code}")
                    media_type = response.headers.get("content-type", "").split(";", 1)[0].lower().strip()
                    if media_type not in {"text/html", "application/xhtml+xml", "text/plain", "application/pdf"}:
                        raise FetchError("unsupported_type", "The article is not HTML, text, or PDF")
                    length = response.headers.get("content-length")
                    if length and length.isdigit() and int(length) > max_body_bytes:
                        raise FetchError("too_large", "The article exceeds the download limit")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > max_body_bytes:
                            raise FetchError("too_large", "The article exceeds the download limit")
                    links: tuple[ArticleLink, ...] = ()
                    if media_type == "application/pdf":
                        from .pdf_text import PdfTextError, extract_pdf_text
                        try:
                            text = extract_pdf_text(bytes(body))
                        except PdfTextError as exc:
                            raise FetchError(exc.code, str(exc)) from exc
                    else:
                        decoded = bytes(body).decode(response.encoding or "utf-8", errors="replace")
                        if media_type != "text/plain":
                            text, links = parse_html(decoded)
                        else:
                            text = decoded.strip()
                    if not text.strip():
                        raise FetchError("no_text", "No readable article text was found")
                    return FetchedDocument(url=current, media_type=media_type,
                                           text=text.strip(), links=links)
            except httpx.RequestError as exc:
                raise FetchError("request_failed", "The article could not be retrieved") from exc
        raise FetchError("too_many_redirects", "The article redirected too many times")
    finally:
        if owned_client:
            client.close()
