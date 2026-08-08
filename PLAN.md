# Day 3 Weather MCP — Builder Plan

## Goal recap

Build an Open-Meteo-backed weather MCP server (FastMCP, streamable-http) with three tools — `get_current_weather`, `get_weather_forecast`, `get_weather_recommendation` — and the surrounding docs/tests/`app.yaml` to deploy it as a Databricks App and register it with an Agent Bricks agent. Mirror the Alpaca reference repo's *style* (thin `@mcp.tool` → adapter dispatch, `app.yaml` shape, README structure), but use **no Alpaca code at runtime**.

## Reference patterns I'll mirror (not copy)

From `homework/day3/reference/mcp_server/alpaca_mcp_server.py`:
- `@mcp.tool` decorator + Google-style docstring (`Args:` / `Returns:`).
- `mcp = FastMCP("weather-mcp")` and `if __name__ == "__main__": mcp.run(transport="http", host="0.0.0.0", port=port)` entrypoint.
- `DATABRICKS_APP_PORT` → `PORT` → `8000` port resolution.
- All HTTP/SDK calls in a sibling adapter module — `weather_mcp_server.py` only orchestrates.

From `homework/day3/reference/mcp_server/alpaca_broker.py`:
- Adapter module is importable; raises typed errors; returns clean dicts.
- Single `requests.Session` for connection pooling (good citizen for Open-Meteo's free tier).

From `homework/day3/reference/mcp_server/app.yaml`:
- `command: ["python", "<entry>.py"]`; `resources: - name: requirements`; env list of simple key/value pairs.

## Files I'll create (under `homework/day3/`)

```
homework/day3/
├── PLAN.md               ← this file (pre-build)
├── EVAL_PLAN.md          ← evaluator's plan (separate)
├── AGENTS.md             ← repo guidance for Tolu (post-build hand-hold)
├── README.md             ← architecture, tools, run, deploy, agent setup
├── EVIDENCE.md           ← facts-only verification log
├── mcp_server/
│   ├── weather_mcp_server.py   ← FastMCP server, 3 tools, thin wrappers
│   ├── openmeteo_adapter.py    ← HTTP + parsing + WMO code map + errors
│   ├── weather_codes.py        ← WMO code → description (used by adapter)
│   ├── app.yaml                ← Databricks App config
│   └── requirements.txt        ← pinned deps
├── dashboard/                  ← optional stretch; mirror reference's Flask shape
│   ├── app.py
│   ├── app.yaml
│   ├── requirements.txt
│   └── templates/index.html
└── tests/
    ├── conftest.py             ← pytest fixtures: fake adapter, location fixtures
    ├── test_openmeteo_adapter.py
    ├── test_weather_mcp_server.py
    └── test_recommendation.py
```

## Open-Meteo API contracts (confirmed from docs)

- Geocoding: `GET https://geocoding-api.open-meteo.com/v1/search?name=<q>&count=5&language=en&format=json` → `{"results":[{"id":int,"name":str,"latitude":float,"longitude":float,"country":str,"admin1":str,"country_code":str,"timezone":str,"elevation":float,...}]}` or `{}` (no `results` key on miss).
- Forecast: `GET https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max&timezone=auto&forecast_days={N}&temperature_unit={celsius|fahrenheit}&wind_speed_unit={kmh|mph|ms|kn}&precipitation_unit={mm|inch}`. Response includes `current` block (single object), `daily` block (parallel arrays), `timezone` and `timezone_abbreviation`.
- Forecast `days` valid range: 1–7 per spec (Open-Meteo allows 1–16; clamp to 1–7 in adapter, raise on out-of-range).
- WMO codes: 0=clear, 1/2/3=mainly clear/partly cloudy/overcast, 45/48=fog, 51/53/55=drizzle, 56/57=freezing drizzle, 61/63/65=rain, 66/67=freezing rain, 71/73/75=snow, 77=snow grains, 80/81/82=rain showers, 85/86=snow showers, 95=thunderstorm, 96/99=thunderstorm with hail. Unknown code → `"Unknown"`.

## Tool contracts

```python
@mcp.tool
def get_current_weather(location: str) -> dict:
    """... one-line summary ...
    Args:
        location: human-readable place name, e.g. "Lagos, Nigeria" or "London, UK".
    Returns:
        {"status": "success", "location": {...resolved...}, "current": {...}, "units": {...}}
        or {"status": "error", "error": str, "location": str} on failure.
    """

@mcp.tool
def get_weather_forecast(location: str, days: int) -> dict:
    """... 1-7 day forecast ...
    Args:
        location: human-readable place name.
        days: 1-7 (clamped; raises cleanly outside that range).
    Returns:
        {"status": "success", "location": {...}, "forecast": [daily dicts], "units": {...}}
    """

@mcp.tool
def get_weather_recommendation(
    location: str,
    date: str | None = None,
    activity: str | None = None,
) -> dict:
    """... deterministic advice ...
    Args:
        location: human-readable place name.
        date: optional ISO date (YYYY-MM-DD). If None, uses today. Must be within the 7-day forecast window — else the tool returns "outside_forecast_window".
        activity: optional activity hint (one of {"outdoor","commute","travel"} or free-text); used only to bias the recommendation text.
    Returns:
        {"status": "success", "location": {...}, "date": str, "summary": str,
         "umbrella": {"needed": bool, "reasons": [str]},
         "clothing": {"advice": str, "reasons": [str]},
         "travel": {"advice": str, "reasons": [str]},
         "facts_used": [{name: str, value: <json-serializable>, threshold: str|None}], ...}
    """
```

## Recommendation logic (deterministic, versioned in this doc)

Given the forecast day for `date`:
- `umbrella.needed = precipitation_probability_max >= 40 OR precipitation_sum >= 2.0`
- `clothing.advice = "light layers"` if `apparent_temp_max` ∈ [10, 22]°C; `"warm layers"` if `< 10`; `"light clothing"` if `> 22`; falls back to `temperature_2m_max` if apparent unavailable.
- `travel.advice = "good for travel"` if `wind_speed_10m_max <= 30 AND weather_code ∈ {0,1,2,3}`; `"watch for wind"` if `wind_speed_10m_max ∈ (30, 50]`; `"travel with caution"` if `>50 OR weather_code ∈ {95,96,99}` (thunderstorms); `"check forecast closer to date"` otherwise.
- `facts_used` enumerates every input + the threshold that fired.

## Tests (≥18, all mocked — no live HTTP, no Databricks auth)

`test_openmeteo_adapter.py`:
- T1 geocode hit (Lagos, Nigeria)
- T2 geocode miss (returns `{}`)
- T3 geocode blank input raises
- T4 get_current happy path
- T5 get_forecast happy path 3 days
- T6 get_forecast days=0 raises; days=8 raises
- T7 get_forecast days=-1 raises
- T8 get_forecast empty daily arrays raises
- T9 unknown WMO code maps to "Unknown"
- T10 timeout raises WeatherAdapterError; non-2xx raises; malformed JSON raises

`test_weather_mcp_server.py`:
- T11 tool returns dict with `status: success` for current
- T12 forecast returns list of daily dicts
- T13 recommendation umbrella YES on precip_prob_max=80
- T14 recommendation umbrella NO on dry day
- T15 recommendation clothing on cold day vs mild vs hot
- T16 recommendation travel "watch for wind" on 40km/h
- T17 unknown location returns `status: error`, not raise
- T18 all tool return values JSON-serializable (round-trip through `json.dumps`)

`test_recommendation.py`:
- T19 facts_used lists every observed field
- T20 thunderstorm weather_code triggers travel caution

Plus `tests/conftest.py` with a `FakeSession` that monkeypatches `requests.Session` in the adapter module (no `monkeypatch.setattr` on `requests.get`; we swap the adapter's `_session` directly so we don't pollute the test process).

## Validation plan (commands + expected exit codes)

```bash
cd /home/opadmin/databricks_bootcamp/homework/day3
python -m pip install -r mcp_server/requirements.txt            # expect: 0
python -m compileall -q mcp_server tests dashboard             # expect: 0
python -m pytest -q                                             # expect: 0, all green
# Live smoke (only after mocked tests green):
python -m pip install requests
python -c "
from mcp_server.openmeteo_adapter import geocode, get_current, get_forecast
print(geocode('Lagos'))
print(get_current(6.5244, 3.3792))
print(get_forecast(6.5244, 3.3792, days=5))
"
# Start server:
python mcp_server/weather_mcp_server.py &
sleep 3
curl -sS -i http://localhost:8000/mcp -X POST -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
# expect: HTTP 200, JSON-ish body (streamable-http respond with text/event-stream)
```

## Risks / open questions

- **FastMCP version drift.** Reference pins `fastmcp>=3.2.0`. If pip pulls a newer release that changes the `mcp.run(transport=...)` signature, I'll detect at install time (`python -c "import fastmcp; print(fastmcp.__version__)"`) and pin to the closest version where `transport="http"` is supported (likely 3.x stable; if needed, fall back to `mcp.run(transport="streamable-http")` — same intent). Documented in EVIDENCE.md.
- **Streamable HTTP endpoint path.** FastMCP 3.x exposes `/mcp` by default; I'll confirm via the live `curl` smoke and report the exact path the Databricks App will need in the README.
- **Databricks workspace access.** I won't deploy, won't register, won't change permissions. EVIDENCE.md marks all of that `PENDING HUMAN EVIDENCE`.
- **Dashboard scope.** README/system-prompt/tools/tests come first. Dashboard built only if mocked tests pass cleanly with time to spare; if not, marked "NOT IMPLEMENTED" with a one-line reason.

## Reporting (after build)

- Files created, LOC totals, test totals, exit codes for the 5 validation commands.
- Any deviations from this plan, with rationale.
- The exact `DATABRICKS_APP_PORT`/`PORT`/`8000` precedence and the `streamable-http` endpoint path observed locally.
