# Day 3 (Additional Homework): Open-Meteo Weather MCP Server

This is an **additional** homework built alongside Day 3's main capstone assignment (see
`docs/day-3-notes.md` for the capstone, which is out of scope here). It's a self-contained
weather-prediction MCP server backed by [Open-Meteo](https://open-meteo.com/) - a free,
keyless weather API - deployable as a Databricks App and usable as an external MCP tool by a
Databricks Agent Bricks agent.

## Architecture

```
Agent Bricks agent  --(MCP tool calls)-->  mcp_server/weather_mcp_server.py  --(REST, no key)-->  Open-Meteo
                                                        |
                                                        v
                                            mcp_server/openmeteo_adapter.py
                                                        |
                                                        v
                                            mcp_server/weather_codes.py (WMO code -> description)
```

- `weather_mcp_server.py` is the FastMCP entrypoint. It defines exactly three `@mcp.tool`
  functions (`get_current_weather`, `get_weather_forecast`, `get_weather_recommendation`).
  Tools are thin: no raw `requests`/`urllib`/`json.loads` of Open-Meteo data inside a tool body
  - every tool delegates to `openmeteo_adapter.py`. Tools never raise; they always return
  JSON-serializable dicts with a `status` field (`"success"`, `"error"`, or
  `"outside_forecast_window"`).
- `openmeteo_adapter.py` owns all HTTP calls (via a module-level `requests.Session`),
  input validation (blank names, lat/lon bounds, `days` in 1-7), response-shape validation, and
  translation into clean dicts with ISO 8601 strings. Raises `WeatherAdapterError` on any
  failure; the server catches this and turns it into an error dict.
- `weather_codes.py` maps [WMO weather codes](https://open-meteo.com/en/docs) to human-readable
  descriptions (`describe(code) -> str`, `"Unknown"` for unrecognized codes).

## Why Open-Meteo?

No API key, no signup, no rate-limit friction for a bootcamp exercise, and a clean
geocoding + forecast REST contract that's easy to validate deterministically in tests.

## Files

```
mcp_server/
├── weather_mcp_server.py   FastMCP server, 3 tools
├── openmeteo_adapter.py    HTTP + validation + parsing (Open-Meteo REST client)
├── weather_codes.py        WMO code -> description map
├── app.yaml                Databricks App config
└── requirements.txt        Pinned deps (fastmcp, requests, databricks-sdk)
tests/
├── conftest.py                   FakeSession/FakeResponse fixtures (no live HTTP)
├── test_openmeteo_adapter.py     Adapter-level tests (T1-T10)
├── test_weather_mcp_server.py    Tool-level tests (T11-T18)
├── test_recommendation.py        Recommendation-logic tests (T19-T20)
└── test_dashboard.py             Dashboard route tests (TD1-TD8)
dashboard/
├── app.py                  Flask app: /healthz, /, /api/current_weather, /api/forecast, /api/recommendation
├── templates/index.html    Single-page UI (current / forecast / recommendation panels)
├── app.yaml                Databricks App config (pulls in sibling mcp_server/ via resources:)
└── requirements.txt        flask only (reuses mcp_server's openmeteo_adapter, no duplicate HTTP client)
PLAN.md / EVIDENCE.md / AGENTS.md  Builder plan, verification log, ops guide
```

## Tools and JSON schemas

### `get_current_weather(location: str) -> dict`

Resolves `location` via geocoding, then fetches current conditions.

```json
{
  "status": "success",
  "location": {
    "query": "Lagos, Nigeria",
    "name": "Lagos",
    "country": "Nigeria",
    "admin1": "Lagos",
    "latitude": 6.45407,
    "longitude": 3.39467,
    "timezone": "Africa/Lagos"
  },
  "current": {
    "time": "2026-08-08T19:30",
    "temperature_2m": 25.5,
    "apparent_temperature": 28.6,
    "relative_humidity_2m": 86,
    "precipitation": 0.0,
    "weather_code": 3,
    "weather_description": "Overcast",
    "wind_speed_10m": 15.2,
    "wind_direction_10m": 233
  },
  "units": {"temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm"}
}
```

On failure: `{"status": "error", "error": "<message>", "location": "<original query>"}`.

### `get_weather_forecast(location: str, days: int) -> dict`

`days` must be 1-7 (clamped range; out-of-range raises inside the adapter and is turned into an
error dict by the tool).

```json
{
  "status": "success",
  "location": { "...same shape as above..." },
  "forecast": [
    {
      "date": "2026-08-08",
      "weather_code": 51,
      "weather_description": "Light drizzle",
      "temperature_2m_max": 27.5,
      "temperature_2m_min": 24.9,
      "precipitation_sum": 0.3,
      "precipitation_probability_max": 78,
      "wind_speed_10m_max": 19.8
    }
  ],
  "units": { "...same shape as above..." }
}
```

### `get_weather_recommendation(location: str, date: str | None = None, activity: str | None = None) -> dict`

`date` defaults to today (ISO `YYYY-MM-DD`); must fall within the 7-day forecast window or the
tool returns `{"status": "outside_forecast_window", "location": ..., "date": ...}`. Recommendation
logic is fully deterministic (see `mcp_server/weather_mcp_server.py::_build_recommendation` and
`PLAN.md`).

```json
{
  "status": "success",
  "location": { "...same shape as above..." },
  "date": "2026-08-09",
  "summary": "Light drizzle for activity 'outdoor'",
  "umbrella": {"needed": true, "reasons": ["precipitation_probability_max=70 >= 40"]},
  "clothing": {"advice": "light layers", "reasons": ["temperature_2m_max=20.0 in [10, 22]C"]},
  "travel": {"advice": "watch for wind", "reasons": ["wind_speed_10m_max=40.0 in (30, 50]"]},
  "facts_used": [
    {"name": "precipitation_probability_max", "value": 70, "threshold": ">=40"},
    {"name": "precipitation_sum", "value": 0.3, "threshold": ">=2.0mm"},
    {"name": "temperature_2m_max", "value": 20.0, "threshold": "10-22C bands"},
    {"name": "wind_speed_10m_max", "value": 40.0, "threshold": "30/50 km/h bands"},
    {"name": "weather_code", "value": 51, "threshold": "clear={0,1,2,3}; storm={95,96,99}"}
  ]
}
```

## Setup

```bash
cd homework/day3
python3 -m pip install -r mcp_server/requirements.txt
```

## Local run

```bash
cd mcp_server && python3 weather_mcp_server.py
# Serves MCP on http://0.0.0.0:8000/mcp (confirmed locally with FastMCP 3.4.6)
```

Port resolution precedence: `DATABRICKS_APP_PORT` -> `PORT` -> `8000` (matches the reference
Alpaca server's pattern).

## Tests

```bash
cd homework/day3
python3 -m pytest -q
```

31 tests (23 MCP server + 8 dashboard), all mocked (no live HTTP, no Databricks auth needed).
See `EVIDENCE.md` for the exact pass/fail counts from the last run.

## Dashboard

A small, **optional/extra-credit** read-only Flask app (`dashboard/`) lets a human reviewer try
the same Open-Meteo logic the Agent Bricks agent uses, without going through MCP: type a
location and see current weather, a 1-7 day forecast, and a recommendation (umbrella/clothing/
travel), all rendered from the exact same `mcp_server/openmeteo_adapter.py` module the MCP
server uses. No writes, no auth, no Lakebase, no Alpaca.

**Local run** (from `homework/day3/`, so `mcp_server` resolves as a sibling package):
```bash
python3 -m pip install -r dashboard/requirements.txt
python3 dashboard/app.py
# Dashboard UI: http://0.0.0.0:8001/  |  Health check: http://0.0.0.0:8001/healthz
```
Port precedence: `FLASK_RUN_PORT` env var, default `8001`.

**Databricks Apps deploy** — the dashboard deploys as its **own, separate** Databricks App
from `mcp_server/` (same pattern as the reference's `alpaca-paper-mcp` + `paper-trading-
dashboard` split): point a Custom app at `homework/day3/dashboard/` (picks up `dashboard/
app.yaml`, which pulls in the sibling `mcp_server/` folder via its `resources:` block so
`import mcp_server.openmeteo_adapter` resolves). It gets its **own app URL** and needs its
**own `CAN USE` grant** (independent from the MCP server app's grant) — `PENDING HUMAN
EVIDENCE`, same as the MCP server's deploy steps above.

This dashboard is not part of the graded Agent Bricks flow - it's an optional convenience for
manually sanity-checking the adapter/recommendation logic - but it is fully wired and tested
(see `tests/test_dashboard.py`, TD1-TD8).

## MCP client curl example

```bash
curl -sS -i -X POST http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Expect `HTTP/1.1 200 OK`, `content-type: text/event-stream`, and a `result.serverInfo` block in
the SSE `data:` payload.

## Databricks Apps deploy steps (PENDING HUMAN EVIDENCE)

Following the [Custom MCP server on Databricks Apps](https://learn.microsoft.com/azure/databricks/generative-ai/agent-framework/custom-mcp) doc:

**UI:**
1. Create a Git folder in your Databricks workspace pointing at this repo.
2. Compute > Apps > Create app > Custom. Name it e.g. `weather-mcp`.
3. Point the app's source at the Git folder's `homework/day3/mcp_server/` subfolder (so it picks
   up `mcp_server/app.yaml`).
4. Deploy. Copy the app's URL once it's running - you'll register that URL as an external MCP
   server in Agent Bricks.

**CLI (equivalent):**
```bash
databricks apps create weather-mcp
databricks sync homework/day3/mcp_server /Workspace/Users/<you>/weather-mcp
databricks apps deploy weather-mcp --source-code-path /Workspace/Users/<you>/weather-mcp
```

## Agent Bricks registration steps (PENDING HUMAN EVIDENCE)

1. In your workspace, go to **AI Gateway** > **MCPs** > **Add MCP** (or **Register external
   MCP**). Paste the deployed app's URL (streamable HTTP, path `/mcp`).
2. Name it e.g. `weather-openmeteo`. Databricks will introspect the server and list the 3 tools.
3. In **Agents** > **Agent Bricks** > **Create agent**, choose a Custom LLM agent type, add the
   `weather-openmeteo` MCP server under **Tools** (all 3 tools), choose a foundation model
   (FM), and set the system prompt to the **exact verbatim text below**.
4. Grant the agent (or the app it runs under) `CAN USE` permission on the `weather-mcp`
   Databricks App via Unity Catalog / workspace permissions.
5. Evaluate against sample prompts (e.g. "Should I bring an umbrella in Lagos tomorrow?"),
   iterate, then deploy and chat with it.

### Exact system prompt (verbatim - do not paraphrase)

```
You are a weather assistant grounded in Open-Meteo data. For every claim about current or forecast weather, call the appropriate registered weather tool and base the answer only on the returned fields. Never invent temperatures, precipitation, wind, weather alerts, locations, dates, times, units, or tool results. State the resolved location, forecast period, timezone, and units when they matter. Recommendations must identify the observed or forecast facts that support them and must be phrased as practical guidance, not an official safety guarantee. If a tool fails, returns incomplete data, cannot resolve the location, or does not cover the requested time period, say exactly what is unavailable and ask the user for a corrected location or narrower request. Do not answer from memory when live weather data is required.
```

## Reviewer permissions

Reviewer (Tolu) must grant `CAN USE` on the deployed `weather-mcp` Databricks App to whichever
principal runs the Agent Bricks agent, per step 4 above. `PENDING HUMAN EVIDENCE`.

## Demo evidence

- Deployed app URL: `PENDING HUMAN EVIDENCE`
- Registered MCP name in Agent Bricks: `PENDING HUMAN EVIDENCE`
- Agent Bricks agent name + FM chosen: `PENDING HUMAN EVIDENCE`
- Screenshot / transcript of a live agent chat calling all 3 tools: `PENDING HUMAN EVIDENCE`

## Troubleshooting

- **`ModuleNotFoundError: No module named 'fastmcp'`** - run
  `python3 -m pip install -r mcp_server/requirements.txt` (use `--break-system-packages` or a
  venv if your OS Python is externally managed, per PEP 668).
- **`curl` to `/mcp` hangs or 404s** - confirm the server actually bound to the port you're
  curling (`DATABRICKS_APP_PORT`/`PORT`/`8000` precedence); check server stdout for the
  "Starting MCP server ... on http://0.0.0.0:PORT/mcp" line.
- **Geocoding returns no results** - Open-Meteo's geocoder is picky about spelling; try a
  simpler query (e.g. `"Lagos"` instead of `"Lagos, Nigeria, West Africa"`).
- **`get_weather_forecast` raises for `days` outside 1-7** - this is intentional (Open-Meteo
  supports up to 16, but this server clamps to 1-7 per `PLAN.md`).
- **Agent Bricks can't reach the MCP server** - confirm the Databricks App is deployed and
  `CAN USE` is granted to the agent's principal; check the app's logs in the Apps UI.
