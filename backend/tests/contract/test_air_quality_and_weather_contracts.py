from __future__ import annotations

from httpx import AsyncClient


async def test_air_quality_and_weather_openapi_and_validation_contracts(
    api_client: AsyncClient,
) -> None:
    openapi = (await api_client.get("/openapi.json")).json()
    paths = set(openapi["paths"].keys())
    expected = {
        "/api/v1/air-quality/current",
        "/api/v1/air-quality/history",
        "/api/v1/air-quality/forecast",
        "/api/v1/air-quality/stations",
        "/api/v1/air-quality/map",
        "/api/v1/weather/current",
        "/api/v1/system/cron/ingest-air-quality",
    }
    assert expected.issubset(paths)

    # Malformed bbox returns 422 VALIDATION_ERROR envelope
    bad_bbox = await api_client.get("/api/v1/air-quality/map?bbox=invalid")
    assert bad_bbox.status_code == 422
    assert bad_bbox.json()["error"]["code"] == "VALIDATION_ERROR"

    # Unknown fixture city returns 503 standardized error (never hardcoded fake numbers)
    unknown_city = await api_client.get("/api/v1/air-quality/current?city=Atlantis")
    assert unknown_city.status_code == 503
    assert "request_id" in unknown_city.json()["error"]
