"""Text-based PDF extraction; scanned PDFs need a later OCR service."""

from __future__ import annotations

from io import BytesIO


MAX_PDF_BYTES = 10_000_000
MAX_PDF_PAGES = 100
MAX_EXTRACTED_CHARS = 200_000


class PdfTextError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def extract_pdf_text(pdf_bytes: bytes) -> str:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise PdfTextError("invalid_pdf", "The uploaded file is not a PDF")
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise PdfTextError("too_large", "The PDF exceeds the upload limit")
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PdfTextError("dependency_missing", "PDF extraction requires pypdf") from exc
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=False)
        if reader.is_encrypted:
            raise PdfTextError("encrypted_pdf", "Encrypted PDFs are not supported")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise PdfTextError("too_many_pages", "The PDF exceeds the page limit")
        pages: list[str] = []
        total = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_EXTRACTED_CHARS:
                raise PdfTextError("too_much_text", "The PDF contains too much text")
            pages.append(text.strip())
    except PdfTextError:
        raise
    except Exception as exc:
        raise PdfTextError("unreadable_pdf", "The PDF could not be read") from exc
    result = "\n\n".join(page for page in pages if page)
    if not result:
        raise PdfTextError("no_text", "No text was found; this PDF may be scanned")
    return result
