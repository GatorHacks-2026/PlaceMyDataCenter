from concurrent.futures import Future
from threading import Event
from time import monotonic, sleep

from fastapi.testclient import TestClient

from app import agent_battle, site_screening
from app.main import app


client = TestClient(app)


def sample_screening():
    return {
        "status": "screened",
        "site": {"state": "TX", "lat": 31.76, "lng": -106.49},
        "input": {"it_capacity_mw": 100, "capacity_basis": "hypothetical", "radius_miles": 25},
        "facility": {"average_mw": 112},
        "defaulted_assumptions": ["pue", "wue"], "assumptions": {"pue": 1.4}, "warnings": [],
        "layers": {
            "power": {"status": "red", "values": {"monthly_proxy_mw": -107}},
            "water": {"status": "green", "values": {"river": "Test River", "dry_flow_mgd": 100, "peak_facility_need_mgd": 1}},
            "carbon": {"status": "amber", "values": {"annual_tco2e": 323000}},
            "noise": {"status": "not_checked", "values": {}},
        },
    }


def test_adapter_keeps_energy_proxy_out_of_spare_capacity():
    facts = agent_battle.facts_for_debate(sample_screening())
    assert facts["verdict"]["code"] == "INCOMPLETE"
    assert facts["layers"]["power"]["status"] == "UNKNOWN"
    assert facts["comparison"]["power"] == {}
    assert facts["screening_context"]["electricity"]["state_energy_proxy_mw"] == -107
    assert facts["layers"]["water"]["need_pct_of_dry_flow"] == 1
    assert facts["layers"]["carbon"]["total_tco2e_per_year"] == 323000


def test_research_claims_need_evidence_and_matching_state():
    research = {
        "status": "complete", "project": {"location": {"state": "TX"}},
        "sources": [{"id": "source-1", "url": "https://example.org/report"}],
        "claims": [
            {"field": "community.permanent_jobs", "value": 200, "unit": "jobs",
             "status": "reported", "phase": "proposed", "evidence": [{"source_id": "source-1"}]},
            {"field": "financial.investment_usd", "value": 1_000_000, "unit": "USD",
             "status": "reported", "phase": "proposed", "evidence": [{"source_id": "source-1"}]},
            {"field": "community.permanent_jobs", "value": 400, "unit": "jobs",
             "status": "conflicting", "evidence": [{"source_id": "source-1"}]},
            {"field": "financial.project_value_usd", "value": 8_000_000, "unit": "USD",
             "status": "reported", "evidence": []},
        ],
    }
    claims = agent_battle.source_linked_claims(research, "TX")
    assert len(claims) == 2
    assert claims[0]["source_urls"] == ["https://example.org/report"]
    assert agent_battle.economics_from_claims(claims) == {
        "permanent_jobs": 200, "investment_usd": 1_000_000,
    }
    assert agent_battle.source_linked_claims(research, "GA") == []


def test_battle_requires_key_and_completed_server_screening(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert client.post("/api/agent-battle/jobs", json={"screening_job_id": "a" * 32}).status_code == 503
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    assert client.post("/api/agent-battle/jobs", json={"screening_job_id": "a" * 32}).status_code == 404

    completed = Future()
    completed.set_result(sample_screening())
    with site_screening.jobs_lock:
        site_screening.jobs["a" * 32] = (monotonic(), completed)
    second_started, release_second = Event(), Event()
    calls = []

    class FakeChatAgent:
        def __init__(self, name, _system, _llm):
            self.name = name

        def speak(self, _task, _facts, _helper, _econ, _transcript):
            calls.append(self.name)
            if len(calls) == 2:
                second_started.set()
                assert release_second.wait(3)
            return f"{self.name} reply {len(calls)}"

    monkeypatch.setattr(agent_battle.dc_debate_agents, "make_llm", lambda: object())
    monkeypatch.setattr(agent_battle.dc_debate_agents, "ChatAgent", FakeChatAgent)
    job_id = None
    try:
        queued = client.post("/api/agent-battle/jobs", json={"screening_job_id": "a" * 32, "project_name": "Test project"})
        assert queued.status_code == 202
        job_id = queued.json()["job_id"]
        assert second_started.wait(3)
        response = client.get(f"/api/agent-battle/jobs/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "running"
        assert response.json()["conversation"] == [{"speaker": "sentinel", "text": "SENTINEL reply 1"}]
        assert response.json()["turns_total"] == 7
        release_second.set()
        deadline = monotonic() + 3
        while response.json()["status"] != "complete" and monotonic() < deadline:
            sleep(0.01)
            response = client.get(f"/api/agent-battle/jobs/{job_id}")
        assert response.json()["status"] == "complete"
        assert response.json()["result"]["conversation"][0]["speaker"] == "sentinel"
        assert len(response.json()["result"]["conversation"]) == 7
        assert response.json()["result"]["project_name"] == "Test project"
    finally:
        release_second.set()
        with site_screening.jobs_lock:
            site_screening.jobs.pop("a" * 32, None)
        if job_id:
            with agent_battle.jobs_lock:
                agent_battle.jobs.pop(job_id, None)
