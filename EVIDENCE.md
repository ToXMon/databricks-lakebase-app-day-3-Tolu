# EVIDENCE.md — Day 3 Weather MCP Server

Facts-only verification log. `VERIFIED` = proven by this build's local runs. `PENDING HUMAN
EVIDENCE` = requires Tolu's Databricks workspace access; not claimed here.

## Post-eval fixes (EVAL_REPORT.md M1 + L1)

- **M1**: `tests/test_weather_mcp_server.py::test_t12_...` now uses a distinct 3-day fixture and
  asserts `len(result["forecast"]) == 3` (plus per-day field-type checks), so it verifies the
  requested `days` count actually propagates instead of matching a fixed 7-day fixture regardless
  of input.
- **L1**: In `mcp_server/weather_mcp_server.py`, all three tools now log `WeatherAdapterError`
  (routine user/adapter errors) at `logger.debug` instead of `logger.warning`, and reserve
  `logger.error` for the unexpected/defensive `except Exception` branch (was `logger.exception`).
  23/23 tests still pass after both changes — VERIFIED.

## Dashboard added (this turn)

Total test count is now **31** (23 MCP server + 8 new `tests/test_dashboard.py`), all passing —
`python3 -m pytest -q` → `31 passed`, exit code `0`. See the "Dashboard" section below for full
proof (compileall, pip install, live curl smokes).

## Environment

- Python: `3.12.3` (system `python3`; no `python` alias present)
- Package install method: `python3 -m pip install --break-system-packages -q -r mcp_server/requirements.txt pytest`
  (system Python is PEP 668 "externally managed"; no `sudo`/`apt` access to install
  `python3-venv`, so a venv could not be created — `--break-system-packages` was used for local
  validation only, no system packages were removed or downgraded)
- `fastmcp` version installed: `3.4.6` — VERIFIED (`python3 -c "import fastmcp; print(fastmcp.__version__)"`)

## Deviations from PLAN.md

1. **pip install requires `--break-system-packages`.** The sandbox has no `python3-venv` and no
   `sudo`, so a virtualenv could not be created per PEP 668. Used
   `python3 -m pip install --break-system-packages -q -r mcp_server/requirements.txt pytest`
   for local validation only. Rationale: no other install path was available; this does not
   affect the deployed Databricks App (which manages its own env via `app.yaml` resources).
2. **Added `mcp_server/__init__.py`** (empty) so `mcp_server` is importable as a package from
   `tests/` (`from mcp_server import openmeteo_adapter`) while still supporting flat/standalone
   execution (`python weather_mcp_server.py` from inside `mcp_server/`). Both `openmeteo_adapter.py`
   and `weather_mcp_server.py` use a try/except import fallback to support both modes. Not in
   the original file list but required for the tests-import-as-package pattern PLAN.md
   specifies.
3. **Added `homework/day3/pytest.ini`** with `testpaths = tests` so `python -m pytest -q` run
   from `homework/day3/` does not also try to collect `reference/mcp_server/test_watchlist.py`
   (which fails to import due to missing Databricks auth/credentials in this sandbox — that file
   is untouched, read-only reference). This scoping does not touch `reference/`.
4. **`transport="http"`** used exactly as in the reference (`alpaca_mcp_server.py`), no
   deviation needed — confirmed working with FastMCP 3.4.6 (see Server smoke below).

## Self-validation results

| Step | Command | Exit code |
|---|---|---|
| pip install | `python3 -m pip install --break-system-packages -q -r mcp_server/requirements.txt pytest` | `0` — VERIFIED |
| compileall | `python3 -m compileall -q mcp_server tests` | `0` — VERIFIED |
| pytest | `python3 -m pytest -q` | `0` — VERIFIED, `23 passed in 2.44s` |
| live smoke: geocode | `python3 -c "from mcp_server.openmeteo_adapter import geocode; ..."` | `0` — VERIFIED, returned 5 Lagos, Nigeria results |
| live smoke: get_current | `python3 -c "from mcp_server.openmeteo_adapter import get_current; ..."` | `0` — VERIFIED, `weather_code=3` -> `"Overcast"` |
| live smoke: get_forecast(days=5) | `python3 -c "from mcp_server.openmeteo_adapter import get_forecast; ..."` | `0` — VERIFIED, 5 daily entries returned |
| live smoke: get_forecast(days=0) | `python3 -c "from mcp_server.openmeteo_adapter import get_forecast; print(get_forecast(6.5244, 3.3792, days=0))"` | `1` — VERIFIED, raised `WeatherAdapterError: days must be between 1 and 7, got 0` |
| server smoke: MCP initialize | `python3 mcp_server/weather_mcp_server.py &` then `curl -sS -i -X POST http://127.0.0.1:8000/mcp ...` | `curl` exit `0`, server response `HTTP/1.1 200 OK`, `content-type: text/event-stream`, SSE body contains `"serverInfo":{"name":"weather-mcp","version":"3.4.6"}` — VERIFIED |

### Redacted server smoke output

```
HTTP/1.1 200 OK
content-type: text/event-stream
mcp-session-id: d9751332e6d64951a2ad0a8091ce67a2

event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-03-26", ...,"serverInfo":{"name":"weather-mcp","version":"3.4.6"}}}
```

### Test totals

- **23 passed, 0 failed** — VERIFIED (`python3 -m pytest -q` from `homework/day3/`)
  - `tests/test_openmeteo_adapter.py`: T1-T10 (11 tests incl. T6/T6b split) — all pass
  - `tests/test_weather_mcp_server.py`: T11-T18 (8 tests) — all pass
  - `tests/test_recommendation.py`: T19-T20 (2 tests) — all pass
  - Plan called for "≥18 mocked tests" — 23 delivered, exceeds minimum.

### MCP endpoint path observed

`/mcp` — VERIFIED (FastMCP 3.4.6 log line: `Starting MCP server 'weather-mcp' with transport
'http' on http://0.0.0.0:8000/mcp`).

## Dashboard

`dashboard/` — **VERIFIED**. Read-only Flask app (`app.py`, `templates/index.html`, `app.yaml`,
`requirements.txt`) reusing `mcp_server.openmeteo_adapter` directly (no duplicate HTTP client,
no Alpaca). Proof:

- `python3 -m pytest -q` (31 total, 23 MCP server + 8 dashboard) — `31 passed`, exit code `0`.
- `python3 -m compileall -q mcp_server tests dashboard` — exit code `0`.
- Live smoke, dashboard running on `:8001`:
  - `curl http://127.0.0.1:8001/healthz` → `healthz=200`
  - `curl 'http://127.0.0.1:8001/api/current_weather?location=Lagos%2C%20Nigeria'` →
    `current=200`, live Open-Meteo data returned (`"weather_description":"Overcast"`,
    `"temperature_2m":25.3`) — real network access confirmed working in this sandbox at the
    time of this run.
  - `curl http://127.0.0.1:8001/api/current_weather` (no `location`) → `current_no_loc=400`
- Dashboard tests (`tests/test_dashboard.py`, TD1-TD8) all pass using the same
  `FakeSession`/`FakeResponse` fixtures from `tests/conftest.py` — no live HTTP in the test
  suite itself; the live-network curl checks above were a separate manual smoke, run once.

## Repository hygiene

- `git status --short` (only `homework/day3/*` files touched, verified before handoff) —
  see the builder's final report for the literal command output.
- No files in `homework/day1/`, `homework/day2/`, `homework/day3/reference/`, or `docs/` were
  created, modified, or deleted.
- No `alpaca-py`, `alpaca_broker`, `paper_broker`, or `massive_broker` imports anywhere in the
  new code (`mcp_server/`, `tests/`) — VERIFIED by inspection; the only "broker" pattern reused
  is the *style* (thin tool -> adapter, module-level `requests.Session`), not the code itself.

## PENDING HUMAN EVIDENCE (requires Tolu's Databricks workspace)

- Databricks App deployment (UI or CLI) and resulting app URL
- Registering the deployed URL as an external MCP server in AI Gateway
- Creating the Agent Bricks agent, choosing a foundation model, wiring the 3 tools
- Setting the exact verbatim system prompt on the agent
- Granting `CAN USE` permission on the `weather-mcp` Databricks App
- A live chat transcript/screenshot of the agent calling all 3 tools end-to-end
- Any workspace-side auth, secrets, or permission configuration
