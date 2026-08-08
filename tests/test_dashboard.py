"""
Mocked tests for dashboard/app.py routes. No live HTTP - reuses the same
FakeSession/FakeResponse fixtures from tests/conftest.py to drive the shared
openmeteo_adapter, exactly like the MCP server tests do.
"""

from mcp_server import openmeteo_adapter

from dashboard.app import app as flask_app

GEOCODE_HIT = {
    "results": [
        {
            "id": 2332459,
            "name": "Lagos",
            "latitude": 6.45407,
            "longitude": 3.39467,
            "country": "Nigeria",
            "admin1": "Lagos",
            "country_code": "NG",
            "timezone": "Africa/Lagos",
            "elevation": 39.0,
        }
    ]
}

GEOCODE_MISS = {}

CURRENT_PAYLOAD = {
    "timezone": "Africa/Lagos",
    "timezone_abbreviation": "WAT",
    "current": {
        "time": "2026-08-08T12:00",
        "temperature_2m": 29.5,
        "apparent_temperature": 33.1,
        "relative_humidity_2m": 78,
        "precipitation": 0.0,
        "weather_code": 1,
        "wind_speed_10m": 12.3,
        "wind_direction_10m": 210,
    },
}

FORECAST_PAYLOAD_5D = {
    "timezone": "Africa/Lagos",
    "timezone_abbreviation": "WAT",
    "daily": {
        "time": ["2026-08-08", "2026-08-09", "2026-08-10", "2026-08-11", "2026-08-12"],
        "weather_code": [1, 61, 95, 0, 0],
        "temperature_2m_max": [30.1, 28.4, 26.0, 25.0, 25.0],
        "temperature_2m_min": [24.0, 23.5, 22.1, 22.0, 22.0],
        "precipitation_sum": [0.0, 3.2, 12.5, 0.0, 0.0],
        "precipitation_probability_max": [10, 55, 90, 5, 5],
        "wind_speed_10m_max": [15.0, 22.0, 60.0, 10.0, 10.0],
    },
}


def _client():
    return flask_app.test_client()


def test_td1_healthz_returns_200_ok():
    client = _client()
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_td2_current_weather_success(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=CURRENT_PAYLOAD)]
    )
    client = _client()
    resp = client.get("/api/current_weather?location=Lagos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert "location" in data
    assert "current" in data
    assert "units" in data


def test_td3_current_weather_missing_location_returns_400():
    client = _client()
    resp = client.get("/api/current_weather")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_td4_forecast_returns_5_daily_dicts(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_5D)]
    )
    client = _client()
    resp = client.get("/api/forecast?location=Lagos&days=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data["forecast"], list)
    assert len(data["forecast"]) == 5


def test_td5_forecast_days_0_returns_400():
    client = _client()
    resp = client.get("/api/forecast?location=Lagos&days=0")
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_td6_recommendation_success(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_5D)]
    )
    client = _client()
    resp = client.get("/api/recommendation?location=Lagos&date=2026-08-09")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert "umbrella" in data
    assert "clothing" in data
    assert "travel" in data
    assert "facts_used" in data


def test_td7_recommendation_unknown_location_returns_json_error(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=GEOCODE_MISS))
    client = _client()
    resp = client.get("/api/recommendation?location=BogusPlace12345")
    # Location could not be resolved -> adapter raises -> route returns 502, JSON body.
    assert resp.status_code == 502
    assert resp.content_type.startswith("application/json")
    data = resp.get_json()
    assert "error" in data


def test_td8_unknown_route_returns_json_not_html():
    client = _client()
    resp = client.get("/this-route-does-not-exist")
    assert resp.content_type.startswith("application/json")
    data = resp.get_json()
    assert "error" in data
