"""
Adapter around the Open-Meteo geocoding + forecast REST APIs.

No API key required. This module owns all HTTP calls, response validation,
and shape-checking for the weather MCP server - `weather_mcp_server.py`
never talks to `requests` directly; it only calls into this module.

Endpoints:
    Geocoding: https://geocoding-api.open-meteo.com/v1/search
    Forecast:  https://api.open-meteo.com/v1/forecast

All returned dicts are JSON-serializable (ISO 8601 strings, no datetime
objects) so they can be returned directly from `@mcp.tool` functions.
"""

import requests

# Import from local weather_codes module (copied into dashboard folder)
from weather_codes import describe as describe_weather_code

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# (connect_timeout, read_timeout) - be a good citizen of Open-Meteo's free tier.
_TIMEOUT = (5.0, 10.0)

_MIN_FORECAST_DAYS = 1
_MAX_FORECAST_DAYS = 7

_DEFAULT_UNITS = {
    "temperature_unit": "celsius",
    "wind_speed_unit": "kmh",
    "precipitation_unit": "mm",
}

# Module-level singleton session for connection pooling. Swap this attribute
# in tests (`openmeteo_adapter._session = FakeSession()`) instead of
# monkeypatching global `requests`.
_session = requests.Session()


class WeatherAdapterError(Exception):
    """Raised for any invalid input, HTTP failure, or malformed response."""


def _merge_units(units: dict | None) -> dict:
    merged = dict(_DEFAULT_UNITS)
    if units:
        merged.update(units)
    return merged


def _request(url: str, params: dict) -> dict:
    """Perform a GET request and return the parsed JSON body, or raise WeatherAdapterError."""
    try:
        response = _session.get(url, params=params, timeout=_TIMEOUT)
    except requests.exceptions.Timeout as exc:
        raise WeatherAdapterError(f"Request to {url} timed out: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise WeatherAdapterError(f"Request to {url} failed: {exc}") from exc

    if response.status_code != 200:
        raise WeatherAdapterError(
            f"Request to {url} returned status {response.status_code}: {response.text[:200]}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise WeatherAdapterError(f"Response from {url} was not valid JSON: {exc}") from exc


def geocode(name: str) -> dict:
    """
    Resolve a human-readable place name to lat/lon + metadata via Open-Meteo's
    geocoding API.

    Args:
        name: Place name, e.g. "Lagos, Nigeria".

    Returns:
        On match: {"status": "found", "results": [ {id, name, latitude,
        longitude, country, admin1, country_code, timezone, elevation}, ... ]}
        On no match: {"status": "not_found", "results": []}

    Raises:
        WeatherAdapterError: if `name` is blank, or the HTTP call fails.
    """
    if not name or not name.strip():
        raise WeatherAdapterError("geocode() requires a non-blank location name")

    data = _request(
        GEOCODING_URL,
        {"name": name.strip(), "count": 5, "language": "en", "format": "json"},
    )

    raw_results = data.get("results") or []
    results = [
        {
            "id": r.get("id"),
            "name": r.get("name"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
            "country": r.get("country"),
            "admin1": r.get("admin1"),
            "country_code": r.get("country_code"),
            "timezone": r.get("timezone"),
            "elevation": r.get("elevation"),
        }
        for r in raw_results
    ]

    return {
        "status": "found" if results else "not_found",
        "results": results,
    }


def _validate_lat_lon(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise WeatherAdapterError(f"latitude out of range [-90, 90]: {lat!r}")
    if not (-180.0 <= lon <= 180.0):
        raise WeatherAdapterError(f"longitude out of range [-180, 180]: {lon!r}")


def get_current(lat: float, lon: float, *, units: dict | None = None) -> dict:
    """
    Fetch current weather conditions for a lat/lon.

    Args:
        lat: Latitude in [-90, 90].
        lon: Longitude in [-180, 180].
        units: Optional overrides for temperature_unit/wind_speed_unit/precipitation_unit.

    Returns:
        {"timezone": str, "timezone_abbreviation": str, "current": {
            "time": ISO 8601 str, "temperature_2m": float, "apparent_temperature": float,
            "relative_humidity_2m": float, "precipitation": float, "weather_code": int,
            "weather_description": str, "wind_speed_10m": float, "wind_direction_10m": float
         }, "units": {...}}

    Raises:
        WeatherAdapterError: on invalid lat/lon, HTTP failure, or malformed response.
    """
    _validate_lat_lon(lat, lon)
    merged_units = _merge_units(units)

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "precipitation,weather_code,wind_speed_10m,wind_direction_10m"
        ),
        "timezone": "auto",
        **merged_units,
    }
    data = _request(FORECAST_URL, params)

    current = data.get("current")
    if not current:
        raise WeatherAdapterError("Forecast response missing 'current' block")

    weather_code = current.get("weather_code")

    return {
        "timezone": data.get("timezone"),
        "timezone_abbreviation": data.get("timezone_abbreviation"),
        "current": {
            "time": current.get("time"),
            "temperature_2m": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "relative_humidity_2m": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "weather_code": weather_code,
            "weather_description": describe_weather_code(weather_code) if weather_code is not None else "Unknown",
            "wind_speed_10m": current.get("wind_speed_10m"),
            "wind_direction_10m": current.get("wind_direction_10m"),
        },
        "units": merged_units,
    }


def get_forecast(lat: float, lon: float, days: int, *, units: dict | None = None) -> dict:
    """
    Fetch a daily forecast for a lat/lon.

    Args:
        lat: Latitude in [-90, 90].
        lon: Longitude in [-180, 180].
        days: Number of forecast days, 1-7 inclusive.
        units: Optional overrides for temperature_unit/wind_speed_unit/precipitation_unit.

    Returns:
        {"timezone": str, "timezone_abbreviation": str, "daily": [ {
            "date": ISO 8601 date str, "weather_code": int, "weather_description": str,
            "temperature_2m_max": float, "temperature_2m_min": float,
            "precipitation_sum": float, "precipitation_probability_max": float,
            "wind_speed_10m_max": float
         }, ... ], "units": {...}}

    Raises:
        WeatherAdapterError: on invalid lat/lon/days, HTTP failure, or malformed response.
    """
    _validate_lat_lon(lat, lon)
    if not isinstance(days, int) or isinstance(days, bool):
        raise WeatherAdapterError(f"days must be an int, got {days!r}")
    if not (_MIN_FORECAST_DAYS <= days <= _MAX_FORECAST_DAYS):
        raise WeatherAdapterError(
            f"days must be between {_MIN_FORECAST_DAYS} and {_MAX_FORECAST_DAYS}, got {days!r}"
        )

    merged_units = _merge_units(units)

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max,wind_speed_10m_max"
        ),
        "timezone": "auto",
        "forecast_days": days,
        **merged_units,
    }
    data = _request(FORECAST_URL, params)

    daily = data.get("daily")
    if not daily or not daily.get("time"):
        raise WeatherAdapterError("Forecast response missing or empty 'daily' block")

    dates = daily.get("time") or []
    weather_codes = daily.get("weather_code") or []
    temp_max = daily.get("temperature_2m_max") or []
    temp_min = daily.get("temperature_2m_min") or []
    precip_sum = daily.get("precipitation_sum") or []
    precip_prob_max = daily.get("precipitation_probability_max") or []
    wind_max = daily.get("wind_speed_10m_max") or []

    n = len(dates)
    if n == 0:
        raise WeatherAdapterError("Forecast response 'daily.time' is empty")

    daily_out = []
    for i in range(n):
        code = weather_codes[i] if i < len(weather_codes) else None
        daily_out.append(
            {
                "date": dates[i],
                "weather_code": code,
                "weather_description": describe_weather_code(code) if code is not None else "Unknown",
                "temperature_2m_max": temp_max[i] if i < len(temp_max) else None,
                "temperature_2m_min": temp_min[i] if i < len(temp_min) else None,
                "precipitation_sum": precip_sum[i] if i < len(precip_sum) else None,
                "precipitation_probability_max": precip_prob_max[i] if i < len(precip_prob_max) else None,
                "wind_speed_10m_max": wind_max[i] if i < len(wind_max) else None,
            }
        )

    return {
        "timezone": data.get("timezone"),
        "timezone_abbreviation": data.get("timezone_abbreviation"),
        "daily": daily_out,
        "units": merged_units,
    }
