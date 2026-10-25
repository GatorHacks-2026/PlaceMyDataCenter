"""Bounded PDF text extraction with optional local OCR for image-only pages."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


MAX_PDF_BYTES = 10_000_000
MAX_PDF_PAGES = 100
MAX_EXTRACTED_CHARS = 200_000
MAX_OCR_PAGES = 20


class PdfTextError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _ocr_pages(pdf_bytes: bytes, page_numbers: list[int]) -> dict[int, str]:
    if not page_numbers or not shutil.which("pdftoppm") or not shutil.which("tesseract"):
        return {}
    if len(page_numbers) > MAX_OCR_PAGES:
        raise PdfTextError("too_many_scanned_pages", "Split the scanned PDF into files of 20 pages or fewer")
    results: dict[int, str] = {}
    with TemporaryDirectory(prefix="ecocompute-ocr-") as folder:
        pdf_path = Path(folder) / "input.pdf"
        pdf_path.write_bytes(pdf_bytes)
        for page_number in page_numbers:
            image_base = Path(folder) / f"page-{page_number}"
            try:
                subprocess.run(
                    ["pdftoppm", "-f", str(page_number), "-l", str(page_number),
                     "-r", "150", "-png", "-singlefile", str(pdf_path), str(image_base)],
                    check=True, capture_output=True, timeout=30,
                )
                text = subprocess.run(
                    ["tesseract", f"{image_base}.png", "stdout", "-l", "eng"],
                    check=True, capture_output=True, text=True, timeout=30,
                ).stdout.strip()
                results[page_number] = text
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise PdfTextError("ocr_failed", f"OCR failed on page {page_number}") from exc
            finally:
                image_base.with_suffix(".png").unlink(missing_ok=True)
    return results


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
        image_only: list[int] = []
        total = 0
        for number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_EXTRACTED_CHARS:
                raise PdfTextError("too_much_text", "The PDF contains too much text")
            pages.append(text.strip())
            if not text.strip():
                image_only.append(number)
    except PdfTextError:
        raise
    except Exception as exc:
        raise PdfTextError("unreadable_pdf", "The PDF could not be read") from exc
    if image_only:
        ocr = _ocr_pages(pdf_bytes, image_only)
        for number, text in ocr.items():
            pages[number - 1] = text
    result = "\n\n".join(page for page in pages if page)
    if len(result) > MAX_EXTRACTED_CHARS:
        raise PdfTextError("too_much_text", "The PDF contains too much text")
    if not result:
        raise PdfTextError("no_text", "No text was found; this PDF may be scanned")
    return result
