"""
Weather dashboard: a small, read-only Flask app to let a human reviewer try
the same Open-Meteo-backed weather logic the Agent Bricks agent uses via
the weather MCP server (mcp_server/weather_mcp_server.py). This app never
writes anything - no Lakebase, no Databricks SDK, no auth - it only calls
the shared openmeteo_adapter module (the exact same adapter the MCP server
uses) and renders the results.

Deploy this as its OWN Databricks App (separate from weather_mcp_server.py) -
one app serves MCP tool calls, the other serves the human-facing UI. When
deployed, the dashboard's app.yaml resources block pulls in the sibling
mcp_server/ folder so `import mcp_server.openmeteo_adapter` resolves.

Run locally (from homework/day3/, so `mcp_server` resolves as a package):
    python dashboard/app.py
"""

import os
import sys

from datetime import date as date_cls
from datetime import datetime

from flask import Flask, jsonify, render_template, request

# Import from local modules (copied directly into dashboard folder for self-contained deployment)
import openmeteo_adapter
from openmeteo_adapter import WeatherAdapterError

app = Flask(__name__)


def _resolve_location(location: str) -> dict:
    """Resolve a location name to the best-matching geocoding result, or raise."""
    geo = openmeteo_adapter.geocode(location)
    if geo["status"] != "found" or not geo["results"]:
        raise WeatherAdapterError(f"Could not resolve location: {location!r}")
    return geo["results"][0]


def _location_summary(match: dict, query: str) -> dict:
    return {
        "query": query,
        "name": match.get("name"),
        "country": match.get("country"),
        "admin1": match.get("admin1"),
        "latitude": match.get("latitude"),
        "longitude": match.get("longitude"),
        "timezone": match.get("timezone"),
    }


def _find_day(forecast: list, target_date: str):
    """Same lookup as mcp_server.weather_mcp_server._find_day, duplicated here so the
    dashboard's requirements.txt doesn't need to pull in fastmcp (weather_mcp_server.py
    imports FastMCP at module level) just to reuse this tiny helper."""
    for day in forecast:
        if day.get("date") == target_date:
            return day
    return None


def _build_recommendation(day: dict, activity):
    """
    Deterministic recommendation logic - kept byte-for-byte identical to
    mcp_server.weather_mcp_server._build_recommendation (same rules, same
    thresholds; see PLAN.md "Recommendation logic"). Duplicated rather than
    imported so the dashboard's requirements.txt stays flask-only (importing
    weather_mcp_server would transitively require fastmcp, which the
    dashboard app never uses).
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


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.errorhandler(Exception)
def handle_exception(err):
    """Ensure all unhandled errors return JSON (not an HTML error page)."""
    status_code = getattr(err, "code", 500)
    if not isinstance(status_code, int):
        status_code = 500
    return jsonify({"error": str(err)}), status_code


@app.route("/")
def index():
    """Dashboard UI: current weather / forecast / recommendation lookup."""
    return render_template("index.html")


@app.route("/api/current_weather")
def api_current_weather():
    """Current weather conditions for a typed location."""
    location = request.args.get("location", "").strip()
    if not location:
        return jsonify({"error": "location query param is required"}), 400

    try:
        match = _resolve_location(location)
        result = openmeteo_adapter.get_current(match["latitude"], match["longitude"])
        return jsonify(
            {
                "status": "success",
                "location": _location_summary(match, location),
                "current": result["current"],
                "units": result["units"],
            }
        )
    except WeatherAdapterError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/forecast")
def api_forecast():
    """1-7 day forecast for a typed location."""
    location = request.args.get("location", "").strip()
    if not location:
        return jsonify({"error": "location query param is required"}), 400

    days_raw = request.args.get("days", "5")
    try:
        days = int(days_raw)
    except ValueError:
        return jsonify({"error": f"days must be an integer, got {days_raw!r}"}), 400
    if not (1 <= days <= 7):
        return jsonify({"error": f"days must be between 1 and 7, got {days}"}), 400

    try:
        match = _resolve_location(location)
        result = openmeteo_adapter.get_forecast(match["latitude"], match["longitude"], days)
        return jsonify(
            {
                "status": "success",
                "location": _location_summary(match, location),
                "forecast": result["daily"],
                "units": result["units"],
            }
        )
    except WeatherAdapterError as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/recommendation")
def api_recommendation():
    """
    Deterministic weather-based recommendation (umbrella/clothing/travel) for
    a typed location and optional date/activity - reuses the exact same
    recommendation logic as the MCP tool (mcp_server.weather_mcp_server).
    """
    location = request.args.get("location", "").strip()
    if not location:
        return jsonify({"error": "location query param is required"}), 400

    date_param = request.args.get("date") or None
    activity = request.args.get("activity") or None

    if date_param is not None:
        try:
            datetime.strptime(date_param, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": f"date must be YYYY-MM-DD, got {date_param!r}"}), 400

    try:
        match = _resolve_location(location)
        # Default date is "today" in the resolved location's timezone is not
        # directly available without a tz library; fall back to the server's
        # local date (matches weather_mcp_server's behavior) when unset.
        target_date = date_param or date_cls.today().isoformat()

        forecast_result = openmeteo_adapter.get_forecast(match["latitude"], match["longitude"], days=7)
        day = _find_day(forecast_result["daily"], target_date)
        if day is None:
            return jsonify(
                {
                    "status": "outside_forecast_window",
                    "location": location,
                    "date": target_date,
                }
            )

        recommendation = _build_recommendation(day, activity)
        return jsonify(
            {
                "status": "success",
                "location": _location_summary(match, location),
                "date": target_date,
                **recommendation,
            }
        )
    except WeatherAdapterError as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("DATABRICKS_APP_PORT", os.getenv("FLASK_RUN_PORT", "8001")))
    app.run(debug=False, host=host, port=port)
