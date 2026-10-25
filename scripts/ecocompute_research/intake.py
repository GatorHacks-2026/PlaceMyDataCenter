"""Route one user input into bounded text and an honest location hint."""

from __future__ import annotations

from typing import Callable, Literal

from pydantic import Field, model_validator

from .location import LocationInputError, parse_location
from .models import Location, StrictModel
from .pdf_text import MAX_PDF_BYTES, PdfTextError, extract_pdf_text
from .url_fetch import FetchError, FetchedDocument, fetch_url
from .zip_lookup import ZipLookupError, resolve_us_zip


InputMode = Literal["url", "text", "pdf", "manual_location"]


class IntakeError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class IntakeRequest(StrictModel):
    mode: InputMode
    location: str = Field(min_length=1, max_length=160)
    article_url: str | None = None
    article_text: str | None = None
    pdf_bytes: bytes | None = None

    @model_validator(mode="after")
    def matching_input(self) -> IntakeRequest:
        if not self.location.strip():
            raise ValueError("Location cannot be blank")
        required = {
            "url": "article_url",
            "text": "article_text",
            "pdf": "pdf_bytes",
            "manual_location": None,
        }[self.mode]
        present = {
            "article_url": self.article_url is not None,
            "article_text": self.article_text is not None,
            "pdf_bytes": self.pdf_bytes is not None,
        }
        if any(is_present != (name == required) for name, is_present in present.items()):
            raise ValueError("Provide exactly the input matching the selected mode")
        if self.mode == "url" and not self.article_url.strip():
            raise ValueError("Article URL cannot be blank")
        if self.mode == "text" and not self.article_text.strip():
            raise ValueError("Article text cannot be blank")
        if self.mode == "text" and len(self.article_text) > 100_000:
            raise ValueError("Article text exceeds 100,000 characters")
        if self.mode == "pdf" and (not self.pdf_bytes or len(self.pdf_bytes) > MAX_PDF_BYTES):
            raise ValueError("PDF is empty or exceeds the upload limit")
        return self


class IntakeWarning(StrictModel):
    code: str
    message: str


class IntakeResult(StrictModel):
    mode: InputMode
    status: Literal["ready", "partial"]
    location_input: str
    location: Location
    location_source: Literal["user_input", "zippopotam"] = "user_input"
    text: str | None = None
    article_url: str | None = None
    media_type: str | None = None
    warnings: list[IntakeWarning] = Field(default_factory=list)


def read_input(
    request: IntakeRequest,
    *,
    fetcher: Callable[[str], FetchedDocument] = fetch_url,
    zip_resolver: Callable[[str], Location] = resolve_us_zip,
) -> IntakeResult:
    """Read the seed input; failed access is visible and does not invent text."""
    try:
        location = parse_location(request.location)
    except LocationInputError as exc:
        raise IntakeError("invalid_location", str(exc)) from exc

    result = IntakeResult(
        mode=request.mode,
        status="ready",
        location_input=request.location,
        location=location,
        article_url=request.article_url,
    )
    if location.zip_code:
        try:
            resolved = zip_resolver(location.zip_code)
            if location.state and resolved.state != location.state:
                raise IntakeError("zip_state_mismatch",
                                  f"ZIP {location.zip_code} is not in {location.state}")
            result.location = resolved
            result.location_source = "zippopotam"
        except ZipLookupError as exc:
            result.status = "partial"
            result.warnings.append(IntakeWarning(code="zip_lookup_failed", message=str(exc)))
    if request.mode == "manual_location":
        return result
    if request.mode == "text":
        result.text = request.article_text.strip()
        result.media_type = "text/plain"
        return result
    if request.mode == "pdf":
        try:
            result.text = extract_pdf_text(request.pdf_bytes)
            result.media_type = "application/pdf"
        except PdfTextError as exc:
            if exc.code != "no_text":
                raise IntakeError(exc.code, str(exc)) from exc
            result.status = "partial"
            result.warnings.append(IntakeWarning(code=exc.code, message=str(exc)))
        return result

    try:
        fetched = fetcher(request.article_url)
    except FetchError as exc:
        if exc.code in {"invalid_url", "unsafe_url"}:
            raise IntakeError(exc.code, str(exc)) from exc
        result.status = "partial"
        result.warnings.append(IntakeWarning(code=exc.code, message=str(exc)))
        return result
    result.text = fetched.text
    result.article_url = fetched.url
    result.media_type = fetched.media_type
    return result
