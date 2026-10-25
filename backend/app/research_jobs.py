"""Bounded local background research jobs for the single-process prototype."""

from concurrent.futures import Future, ThreadPoolExecutor
import logging
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.ecocompute_research.intake import IntakeError, IntakeRequest
from scripts.ecocompute_research.pdf_text import MAX_PDF_BYTES
from scripts.ecocompute_research.models import ResearchResult
from scripts.ecocompute_research.pipeline import run_research


router = APIRouter()
logger = logging.getLogger("uvicorn.error")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="research")
_jobs: dict[str, tuple[float, Future[ResearchResult]]] = {}
_lock = Lock()
MAX_ACTIVE_JOBS = 6
JOB_TTL_SECONDS = 1800


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str
    location: str = Field(min_length=1, max_length=160)
    article_url: str | None = None
    article_text: str | None = None
    additional_urls: list[str] = Field(default_factory=list, max_length=5)


def _submit(intake: IntakeRequest) -> dict[str, str]:
    with _lock:
        now = monotonic()
        for key, (created, future) in list(_jobs.items()):
            if future.done() and now - created > JOB_TTL_SECONDS:
                del _jobs[key]
        if sum(not future.done() for _, future in _jobs.values()) >= MAX_ACTIVE_JOBS:
            raise HTTPException(429, "Research queue is full; retry shortly")
        job_id = uuid4().hex
        _jobs[job_id] = (now, _executor.submit(run_research, intake))
        return {"job_id": job_id, "status": "queued"}


@router.post("/api/research/jobs", status_code=202)
def submit_json(request: JobRequest) -> dict[str, str]:
    try:
        return _submit(IntakeRequest.model_validate(request.model_dump()))
    except ValidationError as exc:
        raise HTTPException(422, "Input does not match the selected mode") from exc


@router.post("/api/research/jobs/pdf", status_code=202)
def submit_pdf(location: str = Form(...), file: UploadFile = File(...),
               additional_urls: list[str] = Form(default=[])) -> dict[str, str]:
    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(422, "Upload a PDF file")
    content = file.file.read(MAX_PDF_BYTES + 1)
    try:
        intake = IntakeRequest(mode="pdf", location=location, pdf_bytes=content,
                               additional_urls=additional_urls)
    except ValidationError as exc:
        raise HTTPException(422, "PDF or location is invalid or too large") from exc
    return _submit(intake)


@router.get("/api/research/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with _lock:
        entry = _jobs.get(job_id)
    if entry is None:
        raise HTTPException(404, "Research job was not found or has expired")
    _, future = entry
    if not future.done():
        return {"job_id": job_id, "status": "running" if future.running() else "queued"}
    try:
        result = future.result()
    except IntakeError as exc:
        return {"job_id": job_id, "status": "failed", "error": f"{exc.code}: {exc}"}
    except Exception:
        logger.exception("research job failed job_id=%s", job_id)
        return {"job_id": job_id, "status": "failed", "error": "Research failed; check backend logs"}
    return {"job_id": job_id, "status": "complete", "result": result.model_dump(mode="json")}
