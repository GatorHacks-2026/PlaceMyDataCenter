from time import sleep

from fastapi.testclient import TestClient

from app.main import app
from app import research_jobs, place_geocode
from scripts.ecocompute_research.models import ResearchResult, ResearchStatus


client = TestClient(app)


def test_background_research_completes(monkeypatch):
    monkeypatch.setattr(research_jobs, "run_research", lambda _request: ResearchResult(
        status=ResearchStatus.PARTIAL, limitations=["test result"]))
    created = client.post("/api/research/jobs", json={"mode": "manual_location", "location": "Texas"})
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    for _ in range(30):
        job = client.get(f"/api/research/jobs/{job_id}").json()
        if job["status"] == "complete":
            break
        sleep(0.01)
    assert job["result"]["status"] == "partial"
    assert client.get("/api/research/jobs/not-a-real-job").status_code == 404


def test_city_lookup_is_cached_and_rejects_wrong_place(monkeypatch):
    place_geocode._cache.clear()
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"lat": "31.76", "lon": "-106.48", "address": {
                "city": "El Paso", "state": "Texas", "country_code": "us"}}]

    monkeypatch.setattr(place_geocode.httpx, "get", lambda *args, **kwargs: (calls.append(args), Response())[1])
    first = client.get("/api/research/geocode?city=El%20Paso&state=TX")
    second = client.get("/api/research/geocode?city=El%20Paso&state=TX")
    assert first.status_code == second.status_code == 200
    assert first.json()["precision"] == "city"
    assert len(calls) == 1
    state = client.get("/api/research/geocode?state=TX")
    assert state.status_code == 200
    assert state.json()["precision"] == "state"
    assert client.get("/api/research/geocode?city=El%20Paso&state=ZZ").status_code == 422
