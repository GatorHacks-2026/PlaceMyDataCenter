from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BASE = {
    "location": {
        "id": "gnv",
        "name": "Gainesville",
        "state": "FL",
        "lat": 29.6516,
        "lng": -82.3248,
        "gridFactorKgPerMWh": 380,
        "droughtRisk": "Low",
        "source": "preset",
    },
    "capacityMW": 100,
    "utilization": 0.85,
    "cooling": "Evaporative",
}


def test_known_value_and_response_shape():
    response = client.post("/api/estimate", json=BASE)
    assert response.status_code == 200
    result = response.json()
    assert result["metrics"] == {
        "itEnergyMWhYear": 744_600,
        "facilityEnergyMWhYear": 893_520,
        "waterLitersYear": 1_340_280_000,
        "carbonTonnesYear": 339_537.6,
        "droughtRisk": "Low",
    }
    assert result["assumptions"] == {
        "pue": 1.2,
        "wueLPerKwh": 1.8,
        "utilization": 0.85,
        "gridFactorKgPerMWh": 380,
    }


def test_cooling_tradeoff_and_location_independent_water():
    dry = client.post("/api/estimate", json={**BASE, "cooling": "Dry"}).json()
    evap = client.post("/api/estimate", json=BASE).json()
    assert dry["metrics"]["waterLitersYear"] < evap["metrics"]["waterLitersYear"]
    assert dry["metrics"]["facilityEnergyMWhYear"] > evap["metrics"]["facilityEnergyMWhYear"]
    other = client.post(
        "/api/estimate",
        json={**BASE, "location": {**BASE["location"], "gridFactorKgPerMWh": 120}},
    ).json()
    assert other["metrics"]["waterLitersYear"] == evap["metrics"]["waterLitersYear"]
    assert other["metrics"]["carbonTonnesYear"] < evap["metrics"]["carbonTonnesYear"]


def test_invalid_inputs_rejected():
    for change in (
        {"capacityMW": 5},
        {"utilization": 2},
        {"cooling": "Other"},
        {"location": {**BASE["location"], "gridFactorKgPerMWh": -1}},
    ):
        response = client.post("/api/estimate", json={**BASE, **change})
        assert response.status_code == 422
