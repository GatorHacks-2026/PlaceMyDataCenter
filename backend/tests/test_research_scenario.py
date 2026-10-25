from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_scenario_requires_explicit_inputs_and_does_not_invent_carbon():
    payload = {"it_capacity_mw": 100, "utilization": 0.8, "pue": 1.2,
               "wue_l_per_kwh": 0.5, "grid_factor_kg_per_mwh": None}
    response = client.post("/api/research/scenario", json=payload)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "modeled_scenario"
    assert result["it_energy_mwh_year"] == 700800
    assert result["facility_energy_mwh_year"] == 840960
    assert result["water_liters_year"] == 350400000
    assert result["carbon_tonnes_year"] is None
    assert client.post("/api/research/scenario", json={**payload, "it_capacity_mw": 0}).status_code == 422
