from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DOCUMENT = "A proposed data center is under discussion in this fictional example."


def test_location_precision_and_document_round_trip():
    for submitted, kind, precision in (
        ("32601", "zip", "zip_area"),
        ("Gainesville, FL", "city_state", "city"),
        ("Florida", "state", "state"),
    ):
        response = client.post(
            "/api/investigations/preview",
            json={"location": submitted, "document_text": DOCUMENT},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["location"]["kind"] == kind
        assert body["location"]["precision"] == precision
        assert body["document"]["text"] == DOCUMENT
        assert body["extraction"]["status"] == "awaiting_integration"
        assert body["environmental_context"]["status"] == "awaiting_integration"
        assert "facts" not in body


def test_ambiguous_or_invalid_inputs_are_rejected():
    for location in ("Gainesville", "1234", "Nowhere, ZZ"):
        response = client.post(
            "/api/investigations/preview",
            json={"location": location, "document_text": DOCUMENT},
        )
        assert response.status_code == 422

    short = client.post(
        "/api/investigations/preview",
        json={"location": "Florida", "document_text": "too short"},
    )
    assert short.status_code == 422

    padded_short = client.post(
        "/api/investigations/preview",
        json={"location": "Florida", "document_text": "too short" + " " * 30},
    )
    assert padded_short.status_code == 422
