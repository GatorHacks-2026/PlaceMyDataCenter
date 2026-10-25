import math

from app import area_boundary, site_screening


def test_area_query_uses_exact_codes(monkeypatch):
    seen = []
    def fake_query(url, **params):
        seen.append((url, params))
        return {"type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"STUSAB": "TX"},
            "geometry": {"type": "Polygon", "coordinates": []},
        }]}
    monkeypatch.setattr(area_boundary, "_query", fake_query)
    area_boundary.zcta_boundary.cache_clear()
    area_boundary.state_boundary.cache_clear()
    assert area_boundary.zcta_boundary("79901") is not None
    assert area_boundary.state_boundary("TX") is not None
    assert area_boundary.state_at_point(31.76, -106.49) == "TX"
    assert seen[0][1]["where"] == "GEOID='79901'"
    assert seen[1][1]["where"] == "STUSAB='TX'"
    assert seen[2][1]["geometry"] == "-106.49,31.76"


def test_screening_keeps_missing_live_layers_separate(monkeypatch):
    monkeypatch.setattr(site_screening, "state_at_point", lambda lat, lon: "TX")
    model = site_screening.engine()
    def no_water(_cfg, _key):
        raise RuntimeError("USGS unavailable")
    monkeypatch.setattr(model, "fetch_river", no_water)
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    request = site_screening.SiteScreeningRequest(
        facility=site_screening.Point(lat=31.76, lng=-106.49),
        state_hint="TX", it_capacity_mw=100, capacity_basis="hypothetical",
    )
    result = site_screening.calculate(request)
    assert result["status"] == "partial"
    assert result["layers"]["power"]["status"] == "not_checked"
    assert result["layers"]["water"]["status"] == "not_checked"
    assert result["layers"]["carbon"]["values"]["annual_tco2e"] > 0
    assert result["layers"]["noise"]["status"] == "not_checked"
    assert result["facility"]["peak_mw"] == 140
    assert "pue" in result["defaulted_assumptions"]
    assert result["map_overlays"]["water_gauges"] == []
    assert result["map_overlays"]["usgs_search_radius_miles"] == 25
    assert result["map_overlays"]["noise_threshold"]["radius_miles"] > 0


def test_usgs_geometry_coordinates_keep_latitude_longitude_order():
    model = site_screening.engine()
    assert model.gauge_coordinates([-84.4, 33.7]) == (33.7, -84.4)
    assert all(math.isnan(value) for value in model.gauge_coordinates(None))
