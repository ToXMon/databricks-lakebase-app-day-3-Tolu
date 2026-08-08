"""
Open-Meteo weather MCP server.

Exposes weather tools over MCP (Model Context Protocol) so a Databricks
Agent Bricks agent can call them like any other tool:
    - get_current_weather(location)
    - get_weather_forecast(location, days)
    - get_weather_recommendation(location, date, activity)

These tools are backed by Open-Meteo's free, keyless geocoding + forecast
REST APIs (see openmeteo_adapter.py) - no API key, no secrets, no paid
service required.

Tools here are intentionally thin: all HTTP calls, response parsing, and
WMO weather-code lookups live in openmeteo_adapter.py / weather_codes.py.
Tools never raise - every tool always returns a JSON-serializable dict,
with a "status" field of "success" or "error" so a calling agent can
branch on failure without a stack trace leaking through MCP.

Deploy this as a Databricks App (see app.yaml), same FastMCP entrypoint
pattern documented at
https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp, so an
Agent Bricks agent (or any MCP client) can register its URL as an
external MCP server.

Run locally:
    python weather_mcp_server.py
"""

import logging
import os
from datetime import date as date_cls
from datetime import datetime

from fastmcp import FastMCP

# Support both "python weather_mcp_server.py" (run from inside mcp_server/,
# flat import) and "from mcp_server.weather_mcp_server import ..." (run from
# day3/ as a namespace package, e.g. in tests).
try:
    import openmeteo_adapter
    from openmeteo_adapter import WeatherAdapterError
except ImportError:
    from mcp_server import openmeteo_adapter
    from mcp_server.openmeteo_adapter import WeatherAdapterError

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("weather-mcp-server")

mcp = FastMCP("weather-mcp")


def _resolve_location(location: str) -> dict:
    """
    Resolve a location name to the best-matching geocoding result.

    Returns the first geocode match dict, or raises WeatherAdapterError if
    the location cannot be resolved.
    """
    geo = openmeteo_adapter.geocode(location)
    if geo["status"] != "found" or not geo["results"]:
        raise WeatherAdapterError(f"Could not resolve location: {location!r}")
    return geo["results"][0]


def _location_summary(match: dict) -> dict:
    """Build the small resolved-location block shared across tool responses."""
    return {
        "query": None,  # filled in by caller if needed
        "name": match.get("name"),
        "country": match.get("country"),
        "admin1": match.get("admin1"),
        "latitude": match.get("latitude"),
        "longitude": match.get("longitude"),
        "timezone": match.get("timezone"),
    }


@mcp.tool
def get_current_weather(location: str) -> dict:
    """
    Get current observed weather conditions for a location.

    Args:
        location: Human-readable place name, e.g. "Lagos, Nigeria" or "London, UK".

    Returns:
        On success: {"status": "success", "location": {name, country, admin1,
            latitude, longitude, timezone}, "current": {time, temperature_2m,
            apparent_temperature, relative_humidity_2m, precipitation,
            weather_code, weather_description, wind_speed_10m,
            wind_direction_10m}, "units": {...}}
        On failure: {"status": "error", "error": str, "location": str}
    """
    try:
        match = _resolve_location(location)
        result = openmeteo_adapter.get_current(match["latitude"], match["longitude"])
        location_block = _location_summary(match)
        location_block["query"] = location
        return {
            "status": "success",
            "location": location_block,
            "current": result["current"],
            "units": result["units"],
        }
    except WeatherAdapterError as exc:
        # Routine user/adapter errors (bad location, bad days, etc.) are debug-level noise,
        # not server errors - reserve logger.error for genuine 5xx-class adapter failures.
        logger.debug("get_current_weather failed for %r: %s", location, exc)
        return {"status": "error", "error": str(exc), "location": location}
    except Exception as exc:  # defensive: tools must never raise
        logger.error("get_current_weather unexpected error for %r: %s", location, exc)
        return {"status": "error", "error": f"Unexpected error: {exc}", "location": location}


@mcp.tool
def get_weather_forecast(location: str, days: int) -> dict:
    """
    Get a multi-day daily weather forecast for a location.

    Args:
        location: Human-readable place name, e.g. "Lagos, Nigeria".
        days: Number of forecast days, 1-7 inclusive.

    Returns:
        On success: {"status": "success", "location": {...}, "forecast": [
            {date, weather_code, weather_description, temperature_2m_max,
             temperature_2m_min, precipitation_sum,
             precipitation_probability_max, wind_speed_10m_max}, ... ],
            "units": {...}}
        On failure: {"status": "error", "error": str, "location": str}
    """
    try:
        match = _resolve_location(location)
        result = openmeteo_adapter.get_forecast(match["latitude"], match["longitude"], days)
        location_block = _location_summary(match)
        location_block["query"] = location
        return {
            "status": "success",
            "location": location_block,
            "forecast": result["daily"],
            "units": result["units"],
        }
    except WeatherAdapterError as exc:
        # Routine user/adapter errors (bad location, bad days, etc.) are debug-level noise,
        # not server errors - reserve logger.error for genuine 5xx-class adapter failures.
        logger.debug("get_weather_forecast failed for %r: %s", location, exc)
        return {"status": "error", "error": str(exc), "location": location}
    except Exception as exc:  # defensive: tools must never raise
        logger.error("get_weather_forecast unexpected error for %r: %s", location, exc)
        return {"status": "error", "error": f"Unexpected error: {exc}", "location": location}


def _find_day(forecast: list[dict], target_date: str) -> dict | None:
    for day in forecast:
        if day.get("date") == target_date:
            return day
    return None


def _build_recommendation(day: dict, activity: str | None) -> dict:
    """
    Deterministic recommendation logic given a single forecast-day dict.

    Rules (see PLAN.md "Recommendation logic"):
      - umbrella.needed = precipitation_probability_max >= 40 OR precipitation_sum >= 2.0
      - clothing based on apparent temp (fallback to temperature_2m_max)
      - travel based on wind speed + thunderstorm codes
    """
    facts_used = []

    precip_prob = day.get("precipitation_probability_max")
    precip_sum = day.get("precipitation_sum")
    temp_max = day.get("temperature_2m_max")
    wind_max = day.get("wind_speed_10m_max")
    weather_code = day.get("weather_code")

    # Umbrella
    umbrella_reasons = []
    umbrella_needed = False
    if precip_prob is not None and precip_prob >= 40:
        umbrella_needed = True
        umbrella_reasons.append(f"precipitation_probability_max={precip_prob} >= 40")
    if precip_sum is not None and precip_sum >= 2.0:
        umbrella_needed = True
        umbrella_reasons.append(f"precipitation_sum={precip_sum} >= 2.0mm")
    facts_used.append({"name": "precipitation_probability_max", "value": precip_prob, "threshold": ">=40"})
    facts_used.append({"name": "precipitation_sum", "value": precip_sum, "threshold": ">=2.0mm"})

    # Clothing (apparent temp not in daily forecast payload; fall back to temperature_2m_max)
    clothing_temp = temp_max
    if clothing_temp is None:
        clothing_advice = "check forecast closer to date"
        clothing_reasons = ["temperature data unavailable"]
    elif clothing_temp < 10:
        clothing_advice = "warm layers"
        clothing_reasons = [f"temperature_2m_max={clothing_temp} < 10C"]
    elif clothing_temp > 22:
        clothing_advice = "light clothing"
        clothing_reasons = [f"temperature_2m_max={clothing_temp} > 22C"]
    else:
        clothing_advice = "light layers"
        clothing_reasons = [f"temperature_2m_max={clothing_temp} in [10, 22]C"]
    facts_used.append({"name": "temperature_2m_max", "value": temp_max, "threshold": "10-22C bands"})

    # Travel
    thunderstorm_codes = {95, 96, 99}
    clear_codes = {0, 1, 2, 3}
    if wind_max is None:
        travel_advice = "check forecast closer to date"
        travel_reasons = ["wind data unavailable"]
    elif wind_max > 50 or weather_code in thunderstorm_codes:
        travel_advice = "travel with caution"
        travel_reasons = [f"wind_speed_10m_max={wind_max} > 50 or thunderstorm code {weather_code}"]
    elif wind_max > 30:
        travel_advice = "watch for wind"
        travel_reasons = [f"wind_speed_10m_max={wind_max} in (30, 50]"]
    elif wind_max <= 30 and weather_code in clear_codes:
        travel_advice = "good for travel"
        travel_reasons = [f"wind_speed_10m_max={wind_max} <= 30 and weather_code {weather_code} is clear/cloudy"]
    else:
        travel_advice = "check forecast closer to date"
        travel_reasons = [f"wind_speed_10m_max={wind_max}, weather_code={weather_code} did not match a defined rule"]
    facts_used.append({"name": "wind_speed_10m_max", "value": wind_max, "threshold": "30/50 km/h bands"})
    facts_used.append({"name": "weather_code", "value": weather_code, "threshold": "clear={0,1,2,3}; storm={95,96,99}"})

    summary_bits = [day.get("weather_description", "Unknown")]
    if activity:
        summary_bits.append(f"for activity '{activity}'")
    summary = " ".join(summary_bits)

    return {
        "summary": summary,
        "umbrella": {"needed": umbrella_needed, "reasons": umbrella_reasons or ["no precipitation trigger met"]},
        "clothing": {"advice": clothing_advice, "reasons": clothing_reasons},
        "travel": {"advice": travel_advice, "reasons": travel_reasons},
        "facts_used": facts_used,
    }


@mcp.tool
def get_weather_recommendation(
    location: str,
    date: str | None = None,
    activity: str | None = None,
) -> dict:
    """
    Get a deterministic weather-based recommendation (umbrella, clothing,
    travel) for a location on a given date.

    Args:
        location: Human-readable place name, e.g. "Lagos, Nigeria".
        date: Optional ISO date (YYYY-MM-DD). Defaults to today. Must fall
            within the 7-day forecast window, else returns
            status="outside_forecast_window".
        activity: Optional activity hint (e.g. "outdoor", "commute",
            "travel", or free text); used only to bias the summary text.

    Returns:
        On success: {"status": "success", "location": {...}, "date": str,
            "summary": str, "umbrella": {...}, "clothing": {...},
            "travel": {...}, "facts_used": [...]}
        On out-of-window date: {"status": "outside_forecast_window",
            "location": str, "date": str}
        On failure: {"status": "error", "error": str, "location": str}
    """
    try:
        target_date = date or date_cls.today().isoformat()
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError as exc:
            raise WeatherAdapterError(f"date must be YYYY-MM-DD, got {date!r}") from exc

        match = _resolve_location(location)
        forecast_result = openmeteo_adapter.get_forecast(match["latitude"], match["longitude"], days=7)

        day = _find_day(forecast_result["daily"], target_date)
        if day is None:
            return {
                "status": "outside_forecast_window",
                "location": location,
                "date": target_date,
            }

        recommendation = _build_recommendation(day, activity)
        location_block = _location_summary(match)
        location_block["query"] = location

        return {
            "status": "success",
            "location": location_block,
            "date": target_date,
            **recommendation,
        }
    except WeatherAdapterError as exc:
        # Routine user/adapter errors (bad location, bad date, etc.) are debug-level noise,
        # not server errors - reserve logger.error for genuine 5xx-class adapter failures.
        logger.debug("get_weather_recommendation failed for %r: %s", location, exc)
        return {"status": "error", "error": str(exc), "location": location}
    except Exception as exc:  # defensive: tools must never raise
        logger.error("get_weather_recommendation unexpected error for %r: %s", location, exc)
        return {"status": "error", "error": f"Unexpected error: {exc}", "location": location}


if __name__ == "__main__":
    # Databricks Apps route external HTTP traffic to this port via app.yaml;
    # streamable-http is the transport Databricks' MCP client/gateway expects
    # (see https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp).
    port = int(os.getenv("DATABRICKS_APP_PORT", os.getenv("PORT", 8000)))
    mcp.run(transport="http", host="0.0.0.0", port=port)
