"""API validation and route wiring without external search or AI services."""

from fastapi.testclient import TestClient

from app.main import app
from scripts.ecocompute_research.fixtures import pine_island_contract_fixture


client = TestClient(app)


def test_json_modes_route_to_pipeline(monkeypatch):
    seen = []
    def fake_run(request):
        seen.append(request)
        return pine_island_contract_fixture()

    monkeypatch.setattr("app.research.run_research", fake_run)
    for body in (
        {"mode": "url", "location": "Pine Island, MN", "article_url": "https://example.com/story"},
        {"mode": "text", "location": "Pine Island, MN", "article_text": "A project article."},
        {"mode": "manual_location", "location": "Minnesota"},
    ):
        response = client.post("/api/research", json=body)
        assert response.status_code == 200
        assert response.json()["schema_version"] == "1.0"
    assert [request.mode for request in seen] == ["url", "text", "manual_location"]


def test_json_rejects_wrong_mode_payload():
    response = client.post("/api/research", json={
        "mode": "manual_location", "location": "MN", "article_url": "https://example.com",
    })
    assert response.status_code == 422


def test_pdf_upload_routes_binary_to_pipeline(monkeypatch):
    seen = []
    def fake_run(request):
        seen.append(request)
        return pine_island_contract_fixture()

    monkeypatch.setattr("app.research.run_research", fake_run)
    response = client.post("/api/research/pdf", data={"location": "MN"},
                           files={"file": ("source.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert response.status_code == 200
    assert seen[0].mode == "pdf"
    assert seen[0].pdf_bytes == b"%PDF-1.4 test"


def test_pdf_upload_rejects_non_pdf_type():
    response = client.post("/api/research/pdf", data={"location": "MN"},
                           files={"file": ("source.txt", b"hello", "text/plain")})
    assert response.status_code == 422
