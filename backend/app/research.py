"""Research API. The current local implementation runs a bounded synchronous job."""

from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.ecocompute_research.intake import IntakeError, IntakeRequest
from scripts.ecocompute_research.pdf_text import MAX_PDF_BYTES
from scripts.ecocompute_research.pipeline import run_research
from scripts.ecocompute_research.models import ResearchResult


router = APIRouter()


class ResearchJsonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["url", "text", "manual_location"]
    location: str = Field(min_length=1, max_length=160)
    article_url: str | None = None
    article_text: str | None = None
    additional_urls: list[str] = Field(default_factory=list, max_length=5)


def _research(request: IntakeRequest) -> ResearchResult:
    try:
        return run_research(request)
    except IntakeError as exc:
        raise HTTPException(status_code=422, detail=f"{exc.code}: {exc}") from exc


@router.post("/api/research", response_model=ResearchResult)
def research_json(request: ResearchJsonRequest) -> ResearchResult:
    try:
        intake = IntakeRequest.model_validate(request.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Input does not match the selected mode") from exc
    return _research(intake)


@router.post("/api/research/pdf", response_model=ResearchResult)
def research_pdf(location: str = Form(...), file: UploadFile = File(...),
                 additional_urls: list[str] = Form(default=[])) -> ResearchResult:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=422, detail="Upload a PDF file")
    content = file.file.read(MAX_PDF_BYTES + 1)
    try:
        intake = IntakeRequest(mode="pdf", location=location, pdf_bytes=content,
                               additional_urls=additional_urls)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="PDF or location is invalid or too large") from exc
    return _research(intake)
