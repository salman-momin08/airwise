from __future__ import annotations

from httpx import AsyncClient

async def test_current_history_forecast_stations_geojson_and_weather_flows(
    api_client: AsyncClient,
) -> None:
    # 1. Standard isolation on identical Delhi telemetry
    india_res = await api_client.get(
        "/api/v1/air-quality/current?city=Delhi&standard=india_naqi"
    )
    epa_res = await api_client.get(
        "/api/v1/air-quality/current?city=Delhi&standard=us_epa"
    )
    assert india_res.status_code == 200
    assert epa_res.status_code == 200

    india_data = india_res.json()["data"]
    epa_data = epa_res.json()["data"]
    assert india_data["standard"] == "india_naqi"
    assert epa_data["standard"] == "us_epa"
    assert india_data["is_development_fixture"] is True
    assert india_data["category"] == "Very Poor"
    assert epa_data["category"] == "Very Unhealthy"
    assert india_data["aqi"] != epa_data["aqi"]

    # 2. Historical series across 24h, 7d, and 30d
    for period, expected_min_len in (("24h", 20), ("7d", 20), ("30d", 25)):
        hist_res = await api_client.get(
            f"/api/v1/air-quality/history?city=Bengaluru&period={period}&standard=india_naqi"
        )
        assert hist_res.status_code == 200
        hist_body = hist_res.json()["data"]
        assert hist_body["period"] == period
        assert len(hist_body["series"]) >= expected_min_len

    # 3. Hourly forecast: severe Delhi smog (>300 NAQI) marks zero outdoor windows safe,
    # whereas Moderate Mumbai identifies lower-exposure afternoon windows
    delhi_fc_res = await api_client.get(
        "/api/v1/air-quality/forecast?city=Delhi&hours=24&standard=india_naqi"
    )
    assert delhi_fc_res.status_code == 200
    delhi_fc_points = delhi_fc_res.json()["data"]["points"]
    assert len(delhi_fc_points) == 8
    assert all(pt["safer_outdoor_window"] is False for pt in delhi_fc_points)

    mumbai_fc_res = await api_client.get(
        "/api/v1/air-quality/forecast?city=Mumbai&hours=24&standard=india_naqi"
    )
    assert mumbai_fc_res.status_code == 200
    assert any(pt["safer_outdoor_window"] is True for pt in mumbai_fc_res.json()["data"]["points"])

    # 4. Spatial stations lookup & GeoJSON FeatureCollection map layer
    st_res = await api_client.get(
        "/api/v1/air-quality/stations?lat=28.6139&lon=77.2090&radius_km=20&standard=india_naqi"
    )
    assert st_res.status_code == 200
    stations = st_res.json()["data"]
    assert len(stations) == 3
    assert stations[0]["distance_km"] == 0.0

    map_res = await api_client.get(
        "/api/v1/air-quality/map?bbox=77.0,28.4,77.5,28.8&standard=us_epa"
    )
    assert map_res.status_code == 200
    geojson = map_res.json()["data"]
    assert geojson["type"] == "FeatureCollection"
    assert geojson["standard"] == "us_epa"
    assert len(geojson["features"]) >= 3

    # 5. Weather dispersion & winter thermal-inversion detection
    delhi_wx = await api_client.get("/api/v1/weather/current?city=Delhi")
    blr_wx = await api_client.get("/api/v1/weather/current?city=Bengaluru")
    assert delhi_wx.status_code == 200
    assert blr_wx.status_code == 200
    assert delhi_wx.json()["data"]["inversion_risk_flag"] is True
    assert blr_wx.json()["data"]["inversion_risk_flag"] is False

    # 6. Authenticated scheduled ingestion cron persists stations & warms cache
    cron_res = await api_client.get(
        "/api/v1/system/cron/ingest-air-quality",
        headers={"Authorization": "Bearer test-cron-secret-value-123456"},
    )
    assert cron_res.status_code == 200
    assert cron_res.json()["data"]["cities_refreshed"] == 5
