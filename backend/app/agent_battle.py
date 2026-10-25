"""Run the team's debate script against a completed site-screening job.

The screening job is read on the server so browser-supplied numbers cannot be
silently substituted for the values fetched and modeled by our own pipeline.
"""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import logging
import math
import os
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import dc_debate_agents
from app.research_jobs import _jobs as research_jobs, _lock as research_jobs_lock
from app.site_screening import jobs as screening_jobs, jobs_lock as screening_jobs_lock


router = APIRouter()
logger = logging.getLogger("uvicorn.error")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="agent-battle")
@dataclass
class BattleProgress:
    """Completed turns shared safely between the worker and polling requests."""

    conversation: list[dict] = field(default_factory=list)
    stage: str = "Waiting to start"
    lock: Lock = field(default_factory=Lock)

    def update(self, stage: str, turn: dict | None = None) -> None:
        with self.lock:
            if turn is not None:
                self.conversation.append(turn)
            self.stage = stage

    def snapshot(self) -> dict:
        with self.lock:
            return {"stage": self.stage, "conversation": list(self.conversation), "turns_total": 7}


jobs: dict[str, tuple[float, Future[dict], BattleProgress]] = {}
jobs_lock = Lock()
JOB_TTL = 1800


class BattleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    screening_job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    research_job_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    project_name: str | None = Field(default=None, max_length=160)
    location_label: str | None = Field(default=None, max_length=160)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def source_linked_claims(research: dict | None, state: str) -> list[dict]:
    """Give agents bounded, attributed facts from the selected research job."""
    if not research or research.get("status") in {"ambiguous", "failed"}:
        return []
    project = research.get("project") or {}
    project_state = (project.get("location") or {}).get("state")
    if not project_state or project_state != state:
        return []
    source_urls = {source["id"]: source.get("url") for source in research.get("sources", [])}
    allowed_fields = {
        "electricity.capacity_mw", "water.daily_gallons", "cooling.type",
        "community.permanent_jobs", "financial.investment_usd",
        "financial.project_value_usd", "financial.infrastructure_development_usd",
    }
    claims = []
    for claim in research.get("claims", []):
        if claim.get("field") not in allowed_fields or claim.get("status") not in {"reported", "verified"}:
            continue
        evidence = claim.get("evidence") or []
        if not evidence or claim.get("value") is None or claim.get("assumptions"):
            continue
        value = claim["value"]
        if isinstance(value, str):
            value = value[:80]
        elif _number(value) is None:
            continue
        claims.append({
            "field": claim["field"], "value": value, "unit": claim.get("unit"),
            "status": claim["status"], "phase": claim.get("phase"),
            "capacity_kind": claim.get("capacity_kind"),
            "source_urls": list(dict.fromkeys(source_urls.get(ref["source_id"]) for ref in evidence
                                              if source_urls.get(ref["source_id"])))[:3],
        })
        if len(claims) >= 20:
            break
    return claims


def economics_from_claims(claims: list[dict]) -> dict:
    """Only one unambiguous project claim per economic input can be used."""
    econ = {}
    for field, key in (("community.permanent_jobs", "permanent_jobs"),
                       ("financial.investment_usd", "investment_usd")):
        matches = [claim["value"] for claim in claims if claim["field"] == field and
                   _number(claim["value"]) is not None and claim["value"] > 0]
        if len(matches) == 1:
            econ[key] = matches[0]
    return econ


def facts_for_debate(screening: dict, research: dict | None = None) -> dict:
    """Translate the current API result to the script's older facts contract.

    A state energy proxy is never represented as firm spare grid capacity. The
    deterministic verdict stays INCOMPLETE because utility capacity, water
    rights, and local noise law have not been verified by the screening API.
    """
    site = screening["site"]
    input_data = screening["input"]
    layers = screening["layers"]
    facility = screening["facility"]
    water = layers["water"]
    carbon = layers["carbon"]
    noise = layers["noise"]
    water_values = water.get("values") or {}
    carbon_values = carbon.get("values") or {}
    noise_values = noise.get("values") or {}
    flow = _number(water_values.get("dry_flow_mgd"))
    need = _number(water_values.get("peak_facility_need_mgd"))
    water_percent = round(100 * need / flow, 3) if flow and need is not None else None
    mapped_layers = {
        "power": {"status": "UNKNOWN"},
        "water": {"status": water["status"].upper() if water["status"] != "not_checked" else "UNKNOWN",
                  "need_mgd": need, "dry_flow_p10_mgd": flow,
                  "need_pct_of_dry_flow": water_percent},
        "carbon": {"status": carbon["status"].upper() if carbon["status"] != "not_checked" else "UNKNOWN",
                   "total_tco2e_per_year": _number(carbon_values.get("annual_tco2e")),
                   "cars_equivalent": None},
        "noise": {"status": noise["status"].upper() if noise["status"] != "not_checked" else "UNKNOWN",
                  "continuous_db_at_house": _number(noise_values.get("at_home_dba")),
                  "distance_to_house_m": _number(noise_values.get("distance_m")),
                  "night_limit": _number(noise_values.get("assumed_night_limit_dba"))},
    }
    claims = source_linked_claims(research, site["state"])
    return {
        "site": {"state": site["state"], "lat": site["lat"], "lon": site["lng"],
                 "radius_miles": input_data["radius_miles"]},
        "data_center": {"it_mw": input_data["it_capacity_mw"],
                        "capacity_basis": input_data["capacity_basis"]},
        "verdict": {"code": "INCOMPLETE", "red": [], "amber": [],
                    "not_checked": ["grid_connection_capacity", "water_rights", "local_noise_law"]},
        "comparison": {"power": {}, "water": {}, "carbon": {}, "noise": {}},
        "layers": mapped_layers,
        "source_linked_research_claims": claims,
        "screening_context": {
            "scope": "Preliminary site screening, not a permit or facility-specific finding.",
            "electricity": {
                "screening_flag": layers["power"]["status"],
                "state_energy_proxy_mw": layers["power"].get("values", {}).get("monthly_proxy_mw"),
                "average_facility_demand_mw": facility.get("average_mw"),
                "limitation": "State generation minus retail sales, area-scaled, is not spare connection capacity.",
            },
            "water": {"screening_flag": water["status"], "river": water_values.get("river"),
                      "limitation": "Nearby gauge flow does not establish a water source or withdrawal rights."},
            "carbon": {"screening_flag": carbon["status"],
                       "limitation": "Uses a fixed eGRID factor and assumed generator operation."},
            "noise": {"screening_flag": noise["status"],
                      "limitation": "Equipment and comparison limit are assumed; local law and measured noise are unknown."},
            "defaulted_assumptions": screening.get("defaulted_assumptions", []),
            "assumptions": screening.get("assumptions", {}),
            "warnings": screening.get("warnings", []),
        },
    }


def _streaming_chat(facts: dict, econ: dict, progress: BattleProgress) -> dict:
    """Use the unchanged script's agents and report logic, publishing each turn."""
    helper = dc_debate_agents.helper_numbers(facts, json.dumps(facts))
    complete_econ = dict(dc_debate_agents.ECON, **econ)
    facts_text = json.dumps(facts, indent=1, ensure_ascii=False)
    helper_text = json.dumps(helper, indent=1)
    econ_text = json.dumps(complete_econ, indent=1)
    llm = dc_debate_agents.make_llm()
    sentinel = dc_debate_agents.ChatAgent("SENTINEL", dc_debate_agents.SENT_CHAT, llm)
    catalyst = dc_debate_agents.ChatAgent("CATALYST", dc_debate_agents.CATA_CHAT, llm)
    agents = (sentinel, catalyst)
    conversation: list[tuple[str, str]] = []
    for index in range(7):
        agent = agents[index % 2]
        progress.update(f"{agent.name.title()} is composing turn {index + 1} of 7")
        transcript = "\n\n".join(f"{name}: {message}" for name, message in conversation)
        task = dc_debate_agents.chat_task(agent.name, index, 7)
        message = agent.speak(task, facts_text, helper_text, econ_text, transcript)
        conversation.append((agent.name, message))
        progress.update("Preparing the next turn" if index < 6 else "Preparing bottom lines and number check",
                        {"speaker": agent.name.lower(), "text": message})
    transcript = "\n\n".join(f"{name}: {message}" for name, message in conversation)
    bottom = {}
    for agent in agents:
        progress.update(f"{agent.name.title()} is writing a bottom line")
        bottom[agent.name] = agent.speak(dc_debate_agents.BOTTOM_TASK, facts_text, helper_text,
                                        econ_text, transcript)
    progress.update("Checking numbers and compiling the report")
    bad = dc_debate_agents.number_check([message for _, message in conversation] +
                                        list(bottom.values()), facts, helper, complete_econ, facts_text)
    return {
        "convo": conversation,
        "bottom": bottom,
        "unverified_numbers": bad,
        "report": dc_debate_agents.build_chat_report(facts, helper, complete_econ,
                                                     conversation, bottom, bad),
    }


def _run(screening: dict, research: dict | None, request: BattleRequest,
         progress: BattleProgress) -> dict:
    facts = facts_for_debate(screening, research)
    claims = facts["source_linked_research_claims"]
    result = _streaming_chat(facts, economics_from_claims(claims), progress)
    claim_lines = [f"- {claim['field']}: {claim['value']} {claim['unit'] or ''} "
                   f"({claim['status']}; {', '.join(claim['source_urls']) or 'user-supplied source'})"
                   for claim in claims]
    report = result["report"]
    if claim_lines:
        report += "\n\nSOURCE-LINKED PROJECT CLAIMS GIVEN TO THE AGENTS\n" + "\n".join(claim_lines)
    return {
        "project_name": request.project_name or "Proposed data center",
        "location_label": request.location_label or screening["site"]["state"],
        "screening_status": screening["status"],
        "research_claims_used": len(claims),
        "verdict_code": facts["verdict"]["code"],
        "conversation": [{"speaker": speaker.lower(), "text": message} for speaker, message in result["convo"]],
        "bottom_line": {key.lower(): value for key, value in result["bottom"].items()},
        "unverified_numbers": result["unverified_numbers"],
        "report": report,
    }


@router.post("/api/agent-battle/jobs", status_code=202)
def submit(request: BattleRequest) -> dict:
    if not os.environ.get("LLM_API_KEY"):
        raise HTTPException(503, "LLM_API_KEY is not configured on the backend")
    with screening_jobs_lock:
        entry = screening_jobs.get(request.screening_job_id)
    if entry is None:
        raise HTTPException(404, "Site screening job was not found; run site screening again")
    screening_future = entry[1]
    if not screening_future.done():
        raise HTTPException(409, "Site screening is still running")
    try:
        screening = screening_future.result()
    except Exception:
        raise HTTPException(409, "Site screening failed; run it again") from None

    research = None
    if request.research_job_id:
        with research_jobs_lock:
            research_entry = research_jobs.get(request.research_job_id)
        if research_entry and research_entry[1].done():
            try:
                research = research_entry[1].result().model_dump(mode="json")
            except Exception:
                logger.warning("research job unavailable for agent battle")

    with jobs_lock:
        now = monotonic()
        for key, (created, future, _) in list(jobs.items()):
            if future.done() and now - created > JOB_TTL:
                del jobs[key]
        if sum(not future.done() for _, future, _ in jobs.values()) >= 2:
            raise HTTPException(429, "Agent battle queue is full; retry shortly")
        job_id = uuid4().hex
        progress = BattleProgress()
        jobs[job_id] = (now, executor.submit(_run, screening, research, request, progress), progress)
    return {"job_id": job_id, "status": "queued"}


@router.get("/api/agent-battle/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with jobs_lock:
        entry = jobs.get(job_id)
    if entry is None:
        raise HTTPException(404, "Agent battle job was not found or has expired")
    future, progress = entry[1], entry[2]
    if not future.done():
        return {"job_id": job_id, "status": "running" if future.running() else "queued",
                **progress.snapshot()}
    try:
        result = future.result()
    except Exception:
        logger.exception("agent battle failed job_id=%s", job_id)
        return {"job_id": job_id, "status": "failed", "error": "Agent battle failed; check backend logs",
                **progress.snapshot()}
    return {"job_id": job_id, "status": "complete", "result": result,
            **progress.snapshot()}
