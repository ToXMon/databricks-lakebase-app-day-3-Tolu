---
name: databricks-day3-weather-mcp-root
description: Root DOX for Tolu's Day 3 weather MCP homework — Open-Meteo–backed FastMCP server + Flask dashboard + Agent Bricks agent. Built 2026-08-08.
---

# Day 3 Weather MCP — Root AGENTS.md

## Purpose

Root DOX for the Day 3 weather-prediction MCP homework. Built from the `databricks-lakebase-app-day-3` reference fork's *style* (FastMCP `@mcp.tool` → adapter dispatch, `app.yaml` shape, docstring convention) but using **Open-Meteo** as the runtime data source — no Alpaca at runtime.

This file is the project's documentation contract: every change to `mcp_server/`, `dashboard/`, or `tests/` must update the matching `AGENTS.md` in the same turn.

## Project Overview

- **Assignment:** Build a weather-prediction MCP server backed by Open-Meteo, deploy as a Databricks App, wire a Databricks Agent Bricks agent to use it as an external tool. Provide a small dashboard. (See `README.md` for the brief and `ADAL_DAY3_WEATHER_MCP_PROMPT.md` for the original engineer-supervisor brief.)
- **Status:** Built, 31/31 mocked tests green, live Open-Meteo smoke green, evaluator verdict ACCEPT. Databricks App deploy + Agent Bricks registration + reviewer access + demo screenshots are **Tolu's human gates** (tracked in `EVIDENCE.md` § "PENDING HUMAN EVIDENCE").
- **Reference fork:** `https://github.com/ToXMon/databricks-lakebase-app-day-3-Tolu.git` (Alpaca paper-trading pattern; style-only, never imported at runtime).
- **Repo conventions:** This project follows the documentation hierarchy used by `space_agent` and `solana_bootcamp` — one root `AGENTS.md` per project, ownership boundaries clear, stable contracts documented at the level closest to the code.

## Tech Stack

| Tool | Purpose |
|---|---|
| Python 3.10+ | Runtime |
| FastMCP 3.2+ (`fastmcp>=3.2,<4`) | MCP server framework, streamable HTTP transport |
| Open-Meteo (`api.open-meteo.com`, `geocoding-api.open-meteo.com`) | Weather data; no API key required |
| Flask (`flask>=3.0,<4`) | Dashboard web app |
| `requests>=2.31,<3` | Adapter HTTP client with injectable session |
| `databricks-sdk>=0.30,<1` | Optional; only used if you call Databricks APIs from the app |
| pytest | Mocked test runner |
| Databricks Apps | Two separate Apps: MCP server (port 8000) + dashboard (port 8001) |
| Databricks Agent Bricks | Agent that calls the MCP server's `/mcp` endpoint |

## Architecture

```
Agent Bricks agent  --(streamable-http MCP calls)-->  mcp_server/weather_mcp_server.py  --(REST, no key)-->  api.open-meteo.com + geocoding-api.open-meteo.com
        ^
        | system prompt: verbatim from brief (see § "System prompt")
        +---> dashboard/app.py  (Flask, read-only Flask view of the same adapter)
```

- **Two Databricks Apps**, deployed independently:
  - `mcp-weather` — the MCP server (FastMCP, port 8000, MCP endpoint `/mcp`).
  - `weather-dashboard` — the Flask UI (port 8001, sibling to `mcp_server/`).
- The dashboard imports `mcp_server.openmeteo_adapter` directly (deployed as a separate Databricks App; the dashboard's `app.yaml` `resources:` block pulls in `../mcp_server`).
- The recommendation logic is **byte-for-byte duplicated** between the MCP tool (`weather_mcp_server._build_recommendation`) and the dashboard (`dashboard/app._build_recommendation`) — see "Stable contracts" below.

## File Map (ownership boundaries)

| Path | Owns | Stable contract |
|---|---|---|
| `mcp_server/weather_mcp_server.py` | FastMCP server, 3 tools, port resolution | Three `@mcp.tool` funcs with exact names: `get_current_weather(location: str)`, `get_weather_forecast(location: str, days: int)`, `get_weather_recommendation(location: str, date: str | None = None, activity: str | None = None)`. Tools never raise; always return dicts with `status: success` or `status: error`. |
| `mcp_server/openmeteo_adapter.py` | All HTTP/parsing against Open-Meteo | Public funcs: `geocode(name)`, `get_current(lat, lon, *, units=None)`, `get_forecast(lat, lon, days, *, units=None)`. Raises `WeatherAdapterError` on any failure. Uses a module-level `requests.Session` swappable via `_session` attribute for tests. |
| `mcp_server/weather_codes.py` | WMO weather-code → human description map | `describe(code: int) -> str`; unknown codes return `"Unknown"`. |
| `mcp_server/agent/system_prompt.md` | Exact system prompt for the weather agent | Stored verbatim; the agent must call weather MCP tools and must not guess weather values. |
| `mcp_server/app.yaml` | Databricks App config for the MCP server | Command `python weather_mcp_server.py`; env `DATABRICKS_APP_PORT=8000`, `LOG_LEVEL=INFO`. |
| `mcp_server/requirements.txt` | Pinned deps for MCP server | `fastmcp>=3.2,<4`, `requests>=2.31,<3`, `databricks-sdk>=0.30,<1`. |
| `dashboard/app.py` | Flask UI server | Routes: `/healthz`, `/`, `/api/current_weather`, `/api/forecast`, `/api/recommendation`. Global JSON error handler. Port `FLASK_RUN_PORT` → `8001`. |
| `dashboard/templates/index.html` | UI markup + vanilla JS | Three panels (Current/Forecast/Recommendation). Honors `prefers-color-scheme`. |
| `dashboard/app.yaml` | Databricks App config for dashboard | Command `python app.py`; env `FLASK_RUN_HOST=0.0.0.0`, `FLASK_RUN_PORT=8001`. `resources:` block pulls in `../mcp_server` so the import resolves when deployed. |
| `dashboard/requirements.txt` | Dashboard deps | `flask>=3.0,<4` only. |
| `tests/conftest.py` | Shared pytest fixtures | `FakeSession` / `FakeResponse` / location fixtures. No live HTTP. |
| `tests/test_openmeteo_adapter.py` | Adapter unit tests | 11 tests covering geocode, current, forecast, days boundaries, unknown WMO codes, error paths. |
| `tests/test_weather_mcp_server.py` | MCP tool tests | 8 tests; T12 uses a distinct 3-day fixture to catch regressions in the `days` parameter. |
| `tests/test_recommendation.py` | Recommendation-logic tests | 2 tests: `facts_used` enumerates inputs; thunderstorm codes trigger travel caution. |
| `tests/test_dashboard.py` | Dashboard route tests | 8 tests (TD1–TD8) covering `/healthz`, all three `/api/*` endpoints, bad-input boundaries, and JSON-on-error behavior. |
| `pytest.ini` | Pytest scope | `testpaths = tests` so the discovery doesn't try to import anything outside `tests/`. |
| `README.md` | Public source of truth | Brief, architecture, setup, deploy, system prompt, demo questions, troubleshooting. |
| `EVIDENCE.md` | Facts-only verification log | VERIFIED rows for things the build proves; `PENDING HUMAN EVIDENCE` rows for Tolu's workspace actions. |
| `EVAL_REPORT.md` | Adversarial review record | Verdict, bugs found, fixes shipped. |
| `PLAN.md` | Original builder plan (frozen) | Read-only context for future contributors. |
| `TRANSCRIPT_NOTES.md` | Day 3 transcript ↔ build reconciliation | Read-only; only updated if the build changes in a way that contradicts the transcript. |
| `ADAL_DAY3_WEATHER_MCP_PROMPT.md` | Original engineer-supervisor brief | Read-only context. |

## Stable Contracts (do NOT break without updating AGENTS.md + README + EVIDENCE.md)

1. **Tool names.** Exactly `get_current_weather`, `get_weather_forecast`, `get_weather_recommendation`. Case-sensitive, no aliases.
2. **Tool signatures.** `location: str`; `days: int` (1–7 inclusive; out-of-range returns clean `status: error`); `date: str | None` (ISO `YYYY-MM-DD` or `None`); `activity: str | None` (free-text, optional).
3. **Adapter signature.** `geocode(name)`, `get_current(lat, lon, *, units=None)`, `get_forecast(lat, lon, days, *, units=None)`. All return plain `dict`; all raise `WeatherAdapterError` on failure.
4. **Recommendation thresholds.**
   - `umbrella.needed = precipitation_probability_max ≥ 40% OR precipitation_sum ≥ 2.0 mm`
   - `clothing.advice` ∈ `{"warm layers", "light layers", "light clothing"}` by apparent-temp buckets `<10`, `10–22`, `>22` °C; falls back to `temperature_2m_max` if apparent unavailable.
   - `travel.advice` ∈ `{"good for travel", "watch for wind", "travel with caution", "check forecast closer to date"}` by wind + WMO-code tiers.
   - `facts_used` enumerates every observed field + the threshold that fired.
5. **Port resolution.** MCP server: `DATABRICKS_APP_PORT` → `PORT` → `8000`. Dashboard: `FLASK_RUN_PORT` → `8001`.
6. **HTTP transport.** FastMCP `mcp.run(transport="http", host="0.0.0.0", port=port)`. Confirmed working with FastMCP 3.4.6; if FastMCP version drift breaks this, document the deviation in `EVIDENCE.md`.
7. **No raw HTTP in `@mcp.tool` bodies.** All `requests.*`, `urllib.*`, and Open-Meteo JSON parsing live in `openmeteo_adapter.py`. Verified by grep in CI (see `EVAL_REPORT.md`).
8. **No Alpaca at runtime.** Do not import `alpaca-py`, `alpaca_broker`, `paper_broker`, `massive_broker`. The Alpaca files were removed from this project tree in turn 5.

## System prompt (verbatim — required for Agent Bricks)

```
You are a weather assistant grounded in Open-Meteo data. For every claim about current or forecast weather, call the appropriate registered weather tool and base the answer only on the returned fields. Never invent temperatures, precipitation, wind, weather alerts, locations, dates, times, units, or tool results. State the resolved location, forecast period, timezone, and units when they matter. Recommendations must identify the observed or forecast facts that support them and must be phrased as practical guidance, not an official safety guarantee. If a tool fails, returns incomplete data, cannot resolve the location, or does not cover the requested time period, say exactly what is unavailable and ask the user for a corrected location or narrower request. Do not answer from memory when live weather data is required.
```

Do NOT paraphrase. Do NOT shorten. Paste character-for-character into the Agent Bricks system prompt field.

## Demo Questions (run in Agent Bricks)

1. "What is the current weather in Lagos, Nigeria?"
2. "Give me the next 5 days of weather for London, UK. Which days should I carry an umbrella?"
3. "I am planning to travel to New York City in the next 3 days. Are there weather conditions I should plan around?"

For each: capture the question, the tool name + args the agent called, the raw tool result, the final answer, the timestamp/timezone, the Agent Bricks session ID, and a screenshot. Save to `evidence/demo{1,2,3}.png` and populate `EVIDENCE.md`'s `Demo 1/2/3` rows.

## What Changes Require Doc Updates

| If you change... | Update... |
|---|---|
| A tool signature | this file (Stable Contracts §1, §2), `README.md` (Tools section), `mcp_server/AGENTS.md` (if it exists), `EVAL_REPORT.md` (note any signature diff) |
| The adapter (new endpoint, new error, new field) | this file (Stable Contracts §3), `README.md`, `mcp_server/AGENTS.md`, `tests/test_openmeteo_adapter.py` |
| Recommendation thresholds | this file (Stable Contracts §4), `README.md` (verifies the rationale), `tests/test_recommendation.py`, `EVAL_REPORT.md` |
| Port resolution or transport | this file (Stable Contracts §5, §6), `mcp_server/app.yaml`, `EVIDENCE.md` (FastMCP version note) |
| Adding a new dependency | `mcp_server/requirements.txt` or `dashboard/requirements.txt`, this file (Tech Stack table) |
| Adding a new tool | this file (File Map + Stable Contracts), `README.md`, `tests/`, the system prompt (if the new tool changes what the agent can answer) |
| Databricks deploy steps (CLI/UI changes) | `README.md` (Deploy section), `AGENTS.md` (Human Gates), this file (What Changes Require Doc Updates if the workflow shifts) |
| Adding a new environment variable | `mcp_server/app.yaml` or `dashboard/app.yaml`, this file (Stable Contracts §5) |

## Local Dev Quickstart

```bash
cd /path/to/this/project
python3 -m pip install -r mcp_server/requirements.txt --break-system-packages
python3 -m pip install -r dashboard/requirements.txt --break-system-packages
python3 -m pytest -q            # expect: 31 passed
# Live Open-Meteo smoke:
python3 -c "from mcp_server.openmeteo_adapter import geocode; import json; print(json.dumps(geocode('Lagos, Nigeria')))"
# Server smoke:
python3 mcp_server/weather_mcp_server.py &   # binds 0.0.0.0:8000
curl -sS -X POST http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

## Databricks Human Gates (Tolu's checklist)

All steps in `README.md` § "Databricks Apps deployment" + "Agent Bricks registration" + "Reviewer permissions". Summary:

1. Authenticate: `databricks auth login --host https://<workspace>`
2. Create App: `databricks apps create mcp-weather` (UI alternative: Compute → Apps → Create app, name must start with `mcp-`)
3. Sync + deploy source: `databricks sync mcp_server/ "/Users/<you>/mcp-weather"` then `databricks apps deploy mcp-weather --source-code-path "/Workspace/Users/<you>/mcp-weather"`
4. Copy app URL from Apps UI; the MCP endpoint is `<url>/mcp`.
5. Register: AI Gateway → MCPs → Add MCP, paste endpoint, save.
6. Create Agent Bricks agent, attach the registered weather MCP, paste the verbatim system prompt.
7. Choose a Databricks-supported open-source / cost-effective FM (Llama 3.x 70B, DBRX, etc.).
8. Grant `CAN USE` to your reviewer on both Apps.
9. Run the three demo questions, capture evidence, populate `EVIDENCE.md`.

## Common Problems

- **`pytest` collects the wrong tests.** Make sure `pytest.ini` is at the project root with `testpaths = tests`. Without it, pytest may try to import outside the `tests/` directory.
- **Databricks App deploy fails immediately.** Check the Apps UI **Logs** tab; look for `FastMCP` startup banner + `Uvicorn running on http://0.0.0.0:8000`. If you see a different port or transport, your `app.yaml` env or the `mcp.run(...)` line drifted.
- **Agent Bricks doesn't see the three tools.** Re-check the external-MCP registration in `AI Gateway → MCPs`; the introspected tool list must include all three exact names.
- **Open-Meteo returns rate-limit errors.** Open-Meteo's free tier is ~10,000 calls/day for non-commercial. Cache responses in the agent (not implemented here; do it at the agent layer if needed).
- **"Only one prompt turn" free-tier bug.** Known Databricks free-edition limitation per Zach's Day 3 class. Single-shot demos work; multi-turn may crash. Re-init the chat.
- **Dashboard can't import `mcp_server.openmeteo_adapter`.** The dashboard's `app.yaml` `resources:` block must pull in `../mcp_server`. Locally, run from the project root (`python3 dashboard/app.py`), not from inside `dashboard/`.

## Status

Built 2026-08-08. Tests: 31/31 green. Live smoke: green. Evaluator: ACCEPT. Awaiting Tolu's Databricks workspace execution.
