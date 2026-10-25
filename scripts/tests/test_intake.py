"""Offline tests for bounded input ingestion and honest locations."""

import sys
from io import BytesIO
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError

from scripts.ecocompute_research.intake import IntakeError, IntakeRequest, read_input
from scripts.ecocompute_research.html_text import ArticleLink
from scripts.ecocompute_research.location import LocationInputError, parse_location
from scripts.ecocompute_research.models import LocationPrecision
from scripts.ecocompute_research.pdf_text import PdfTextError, extract_pdf_text
from scripts.ecocompute_research.url_fetch import (
    FetchError, FetchedDocument, fetch_url, validate_public_url,
)


PUBLIC_DNS = lambda _host: ["93.184.216.34"]


def test_location_parser_keeps_unknown_details_null():
    city = parse_location("Pine Island, Minnesota")
    assert (city.city, city.state, city.precision) == ("Pine Island", "MN", LocationPrecision.CITY)
    assert (city.county, city.zip_code, city.latitude, city.longitude) == (None, None, None, None)

    county = parse_location("Goodhue County, MN")
    assert (county.county, county.city, county.precision) == (
        "Goodhue County", None, LocationPrecision.COUNTY,
    )
    address = parse_location("123 Main Street, Pine Island, MN")
    assert address.address == "123 Main Street"
    assert address.precision == LocationPrecision.ADDRESS
    assert address.latitude is None
    assert parse_location("55963").zip_code == "55963"
    assert parse_location("55963, MN").state == "MN"


def test_all_state_names_parse_without_default_coordinates():
    from scripts.ecocompute_research.location import STATE_NAMES

    assert len(STATE_NAMES) >= 50
    for name, code in STATE_NAMES.items():
        parsed = parse_location(name)
        assert parsed.state == code
        assert parsed.precision == LocationPrecision.STATE
        assert parsed.latitude is None


@pytest.mark.parametrize("raw", ["", "Pine Island", "Pine Island, ZZ", "1234", "A, B, C, MN"])
def test_ambiguous_or_invalid_place_is_rejected(raw):
    with pytest.raises(LocationInputError):
        parse_location(raw)


def test_request_mode_matches_exactly_one_input():
    with pytest.raises(ValidationError):
        IntakeRequest(mode="url", location="MN", article_url="https://example.com", article_text="extra")
    with pytest.raises(ValidationError):
        IntakeRequest(mode="pdf", location="MN", pdf_bytes=b"")
    with pytest.raises(ValidationError):
        IntakeRequest(mode="manual_location", location="MN", article_text="extra")
    with pytest.raises(ValidationError):
        IntakeRequest(mode="manual_location", location="MN",
                      additional_urls=["https://example.gov/project"])
    with pytest.raises(ValidationError):
        IntakeRequest(mode="text", location="MN", article_text="Project document",
                      additional_urls=["http://localhost/private"] * 6)
    with pytest.raises(ValidationError):
        IntakeRequest(mode="text", location="MN", article_text="Project document",
                      additional_urls=["not a URL"])


def test_text_and_location_only_paths_do_not_call_network():
    def unexpected_fetch(_url):
        raise AssertionError("network should not be used")

    text = read_input(IntakeRequest(
        mode="text", location="Pine Island, MN", article_text="  A proposed data center.  ",
    ), fetcher=unexpected_fetch)
    assert text.status == "ready"
    assert text.text == "A proposed data center."
    assert text.location.latitude is None

    only = read_input(IntakeRequest(mode="manual_location", location="Minnesota"),
                      fetcher=unexpected_fetch)
    assert only.status == "ready"
    assert only.text is None
    assert only.location.precision == LocationPrecision.STATE


def test_url_path_and_failed_access_are_explicit():
    request = IntakeRequest(mode="url", location="Pine Island, MN",
                            article_url="https://example.com/story")
    success = read_input(request, fetcher=lambda url: FetchedDocument(
        url=url, media_type="text/html", text="A specific article about a data center.",
    ))
    assert success.text.startswith("A specific article")
    assert success.status == "ready"

    def denied(_url):
        raise FetchError("http_error", "Article request returned HTTP 403")

    partial = read_input(request, fetcher=denied)
    assert partial.status == "partial"
    assert partial.text is None
    assert partial.article_url == request.article_url
    assert partial.warnings[0].code == "http_error"

    def unsafe(_url):
        raise FetchError("unsafe_url", "Local target")

    with pytest.raises(IntakeError, match="Local target"):
        read_input(request, fetcher=unsafe)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "http://localhost/", "http://127.0.0.1/",
    "http://169.254.169.254/", "http://example.com:8000/",
    "https://user:pass@example.com/",
])
def test_unsafe_urls_are_rejected(url):
    with pytest.raises(FetchError):
        validate_public_url(url, resolver=PUBLIC_DNS)


def test_private_dns_and_redirect_target_are_rejected():
    with pytest.raises(FetchError, match="non-public"):
        validate_public_url("https://example.com", resolver=lambda _host: ["10.0.0.2"])

    def redirect(_request):
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    with httpx.Client(transport=httpx.MockTransport(redirect)) as client:
        with pytest.raises(FetchError, match="non-public"):
            fetch_url("https://example.com/story", client=client, resolver=PUBLIC_DNS)


def test_html_fetch_strips_navigation_and_obeys_body_limit():
    html = ("<html><nav><p>Unrelated navigation</p></nav><article>"
            "<h1>Pine Island project</h1><p>Google proposes a data center.</p>"
            "</article><script>unsafe text</script></html>")

    def serve(_request):
        return httpx.Response(200, headers={"Content-Type": "text/html"}, content=html)

    with httpx.Client(transport=httpx.MockTransport(serve)) as client:
        document = fetch_url("https://example.com/story", client=client, resolver=PUBLIC_DNS)
        assert "Google proposes" in document.text
        assert "Unrelated navigation" not in document.text
        assert "unsafe text" not in document.text
        with pytest.raises(FetchError, match="download limit"):
            fetch_url("https://example.com/story", client=client, resolver=PUBLIC_DNS,
                      max_body_bytes=20)


def test_html_fetch_retains_article_links_but_not_navigation_links():
    html = ('<nav><p><a href="https://example.com/menu">Menu</a></p></nav>'
            '<article><p>El Paso officials linked the '
            '<a href="https://example.gov/project">project filing</a> '
            'for the Meta data center in El Paso.</p></article>')

    with httpx.Client(transport=httpx.MockTransport(
        lambda _request: httpx.Response(200, headers={"Content-Type": "text/html"}, content=html),
    )) as client:
        fetched = fetch_url("https://example.com/story", client=client, resolver=PUBLIC_DNS)
    assert fetched.links == (ArticleLink(
        href="https://example.gov/project", label="project filing",
        context="El Paso officials linked the project filing for the Meta data center in El Paso.",
    ),)


def test_pdf_route_extracts_pages_and_scanned_pdf_is_partial(monkeypatch):
    from scripts.ecocompute_research import pdf_text
    monkeypatch.setattr(pdf_text.shutil, "which", lambda _name: None)
    class FakeReader:
        is_encrypted = False
        pages = [SimpleNamespace(extract_text=lambda: "Project summary"),
                 SimpleNamespace(extract_text=lambda: "Water details")]

        def __init__(self, _stream, strict=False):
            pass

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))
    request = IntakeRequest(mode="pdf", location="MN", pdf_bytes=b"%PDF-1.4 fake")
    result = read_input(request)
    assert result.status == "ready"
    assert result.text == "Project summary\n\nWater details"

    FakeReader.pages = [SimpleNamespace(extract_text=lambda: None)]
    scanned = read_input(request)
    assert scanned.status == "partial"
    assert scanned.warnings[0].code == "no_text"
    assert scanned.text is None

    with pytest.raises(PdfTextError, match="not a PDF"):
        extract_pdf_text(b"not a pdf")


def test_real_text_pdf_when_dependency_is_installed():
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Pine Island data center) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)

    result = read_input(IntakeRequest(
        mode="pdf", location="Pine Island, MN", pdf_bytes=output.getvalue(),
    ))
    assert result.text == "Pine Island data center"
    assert result.status == "ready"


def test_image_only_pdf_uses_ocr_when_available(monkeypatch):
    from scripts.ecocompute_research import pdf_text
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    monkeypatch.setattr(pdf_text.shutil, "which", lambda _name: "/usr/bin/mock")

    def run(args, **_kwargs):
        return SimpleNamespace(stdout="Meta data center in El Paso, Texas" if args[0] == "tesseract" else "")

    monkeypatch.setattr(pdf_text.subprocess, "run", run)
    assert pdf_text.extract_pdf_text(output.getvalue()) == "Meta data center in El Paso, Texas"
