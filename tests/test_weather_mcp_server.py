"""
Mocked tests for mcp_server/weather_mcp_server.py tool functions. No live HTTP.
"""

import json

from mcp_server import openmeteo_adapter, weather_mcp_server

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

FORECAST_PAYLOAD_7D = {
    "timezone": "Africa/Lagos",
    "timezone_abbreviation": "WAT",
    "daily": {
        "time": ["2026-08-08", "2026-08-09", "2026-08-10", "2026-08-11",
                 "2026-08-12", "2026-08-13", "2026-08-14"],
        "weather_code": [1, 61, 95, 0, 0, 0, 0],
        "temperature_2m_max": [30.1, 5.0, 26.0, 25.0, 25.0, 25.0, 25.0],
        "temperature_2m_min": [24.0, 23.5, 22.1, 22.0, 22.0, 22.0, 22.0],
        "precipitation_sum": [0.0, 3.2, 12.5, 0.0, 0.0, 0.0, 0.0],
        "precipitation_probability_max": [10, 80, 90, 5, 5, 5, 5],
        "wind_speed_10m_max": [15.0, 40.0, 60.0, 10.0, 10.0, 10.0, 10.0],
    },
}


def _tool_fn(tool):
    """Unwrap a @mcp.tool-decorated function to its plain callable, across FastMCP versions."""
    return getattr(tool, "fn", tool)


def _get_fn(name):
    return _tool_fn(getattr(weather_mcp_server, name))


def test_t11_current_weather_returns_success_dict(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=CURRENT_PAYLOAD)]
    )
    fn = _get_fn("get_current_weather")
    result = fn("Lagos, Nigeria")
    assert result["status"] == "success"
    assert result["current"]["temperature_2m"] == 29.5
    assert result["location"]["name"] == "Lagos"


FORECAST_PAYLOAD_3D = {
    "timezone": "Africa/Lagos",
    "timezone_abbreviation": "WAT",
    "daily": {
        "time": ["2026-08-08", "2026-08-09", "2026-08-10"],
        "weather_code": [1, 61, 95],
        "temperature_2m_max": [30.1, 28.4, 26.0],
        "temperature_2m_min": [24.0, 23.5, 22.1],
        "precipitation_sum": [0.0, 3.2, 12.5],
        "precipitation_probability_max": [10, 55, 90],
        "wind_speed_10m_max": [15.0, 22.0, 60.0],
    },
}


def test_t12_forecast_returns_list_of_daily_dicts(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_3D)]
    )
    fn = _get_fn("get_weather_forecast")
    result = fn("Lagos, Nigeria", 3)
    assert result["status"] == "success"
    assert isinstance(result["forecast"], list)
    # Fixture has exactly 3 days (distinct from the 7-day fixture used elsewhere), so this
    # actually verifies the requested "days" count propagates from request -> response,
    # instead of tautologically matching a 7-day fixture regardless of the requested count.
    assert len(result["forecast"]) == 3
    for day in result["forecast"]:
        assert isinstance(day["date"], str) and day["date"]
        assert isinstance(day["weather_description"], str) and day["weather_description"]
        assert isinstance(day["temperature_2m_max"], (int, float))
        assert isinstance(day["temperature_2m_min"], (int, float))
        assert isinstance(day["precipitation_sum"], (int, float))
        assert isinstance(day["precipitation_probability_max"], (int, float))
        assert isinstance(day["wind_speed_10m_max"], (int, float))


def test_t13_recommendation_umbrella_yes_on_high_precip_prob(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    fn = _get_fn("get_weather_recommendation")
    result = fn("Lagos, Nigeria", date="2026-08-09")
    assert result["status"] == "success"
    assert result["umbrella"]["needed"] is True


def test_t14_recommendation_umbrella_no_on_dry_day(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    fn = _get_fn("get_weather_recommendation")
    result = fn("Lagos, Nigeria", date="2026-08-08")
    assert result["status"] == "success"
    assert result["umbrella"]["needed"] is False


def test_t15_recommendation_clothing_cold_mild_hot(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    fn = _get_fn("get_weather_recommendation")

    # Cold day (temp_max=5.0 on 2026-08-09)
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    cold = fn("Lagos, Nigeria", date="2026-08-09")
    assert cold["clothing"]["advice"] == "warm layers"

    # Mild day (temp_max=26.0? no that's >22 -> light clothing; use 2026-08-11 temp=25 -> light clothing)
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    hot = fn("Lagos, Nigeria", date="2026-08-11")
    assert hot["clothing"]["advice"] == "light clothing"

    # Mild band (10-22) day: patch a payload with temp_max=15
    mild_payload = json.loads(json.dumps(FORECAST_PAYLOAD_7D))
    mild_payload["daily"]["temperature_2m_max"][3] = 15.0
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=mild_payload)]
    )
    mild = fn("Lagos, Nigeria", date="2026-08-11")
    assert mild["clothing"]["advice"] == "light layers"


def test_t16_recommendation_travel_watch_for_wind(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    fn = _get_fn("get_weather_recommendation")
    # 2026-08-09: wind_speed_10m_max=40.0, weather_code=61 (not thunderstorm) -> watch for wind
    result = fn("Lagos, Nigeria", date="2026-08-09")
    assert result["travel"]["advice"] == "watch for wind"


def test_t17_unknown_location_returns_error_not_raise(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=GEOCODE_MISS))
    fn = _get_fn("get_current_weather")
    result = fn("Nowhereland12345")
    assert result["status"] == "error"
    assert "location" in result


def test_t18_all_tool_return_values_json_serializable(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory

    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=CURRENT_PAYLOAD)]
    )
    current_result = _get_fn("get_current_weather")("Lagos, Nigeria")
    json.dumps(current_result)  # raises if not serializable

    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    forecast_result = _get_fn("get_weather_forecast")("Lagos, Nigeria", 5)
    json.dumps(forecast_result)

    openmeteo_adapter._session = FakeSession(
        responses=[FakeResponse(json_data=GEOCODE_HIT), FakeResponse(json_data=FORECAST_PAYLOAD_7D)]
    )
    rec_result = _get_fn("get_weather_recommendation")("Lagos, Nigeria", date="2026-08-08")
    json.dumps(rec_result)
