"""
Mocked tests for mcp_server/openmeteo_adapter.py. No live HTTP.
"""

import requests

from mcp_server import openmeteo_adapter
from mcp_server.openmeteo_adapter import WeatherAdapterError

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


def test_t1_geocode_hit(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=GEOCODE_HIT))
    result = openmeteo_adapter.geocode("Lagos, Nigeria")
    assert result["status"] == "found"
    assert result["results"][0]["name"] == "Lagos"
    assert result["results"][0]["country"] == "Nigeria"


def test_t2_geocode_miss(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=GEOCODE_MISS))
    result = openmeteo_adapter.geocode("Nowhereland12345")
    assert result["status"] == "not_found"
    assert result["results"] == []


def test_t3_geocode_blank_input_raises():
    try:
        openmeteo_adapter.geocode("   ")
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t4_get_current_happy_path(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=CURRENT_PAYLOAD))
    result = openmeteo_adapter.get_current(6.45407, 3.39467)
    assert result["current"]["temperature_2m"] == 29.5
    assert result["current"]["weather_description"] == "Mainly clear"
    assert result["timezone"] == "Africa/Lagos"


def test_t5_get_forecast_happy_path_3_days(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=FORECAST_PAYLOAD_3D))
    result = openmeteo_adapter.get_forecast(6.45407, 3.39467, days=3)
    assert len(result["daily"]) == 3
    assert result["daily"][0]["date"] == "2026-08-08"
    assert result["daily"][2]["weather_description"] == "Thunderstorm"


def test_t6_get_forecast_days_0_raises():
    try:
        openmeteo_adapter.get_forecast(6.45407, 3.39467, days=0)
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t6b_get_forecast_days_8_raises():
    try:
        openmeteo_adapter.get_forecast(6.45407, 3.39467, days=8)
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t7_get_forecast_days_negative_raises():
    try:
        openmeteo_adapter.get_forecast(6.45407, 3.39467, days=-1)
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t8_get_forecast_empty_daily_arrays_raises(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    empty_payload = {
        "timezone": "Africa/Lagos",
        "timezone_abbreviation": "WAT",
        "daily": {"time": [], "weather_code": [], "temperature_2m_max": [],
                   "temperature_2m_min": [], "precipitation_sum": [],
                   "precipitation_probability_max": [], "wind_speed_10m_max": []},
    }
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=empty_payload))
    try:
        openmeteo_adapter.get_forecast(6.45407, 3.39467, days=3)
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t9_unknown_wmo_code_maps_to_unknown(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    payload = dict(CURRENT_PAYLOAD)
    payload["current"] = dict(CURRENT_PAYLOAD["current"])
    payload["current"]["weather_code"] = 12345
    openmeteo_adapter._session = FakeSession(response=FakeResponse(json_data=payload))
    result = openmeteo_adapter.get_current(6.45407, 3.39467)
    assert result["current"]["weather_description"] == "Unknown"


def test_t10a_timeout_raises_adapter_error(fake_session_factory):
    FakeSession, _ = fake_session_factory

    def side_effect(url, params, timeout):
        raise requests.exceptions.Timeout("simulated timeout")

    openmeteo_adapter._session = FakeSession(side_effect=side_effect)
    try:
        openmeteo_adapter.geocode("Lagos")
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t10b_non_2xx_status_raises(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(status_code=500, text="server error"))
    try:
        openmeteo_adapter.geocode("Lagos")
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass


def test_t10c_malformed_json_raises(fake_session_factory):
    FakeSession, FakeResponse = fake_session_factory
    openmeteo_adapter._session = FakeSession(response=FakeResponse(raise_json_error=True))
    try:
        openmeteo_adapter.geocode("Lagos")
        assert False, "expected WeatherAdapterError"
    except WeatherAdapterError:
        pass
