# ADAL Day 3 Weather MCP — Engineer Brief (replacement for stale Alpaca brief)

This document replaces the original Alpaca-based engineer brief that came with the cloned `databricks-lakebase-app-day-3` reference fork. That brief was a style reference only; the actual homework Tolu is building is an **Open-Meteo–backed weather MCP server**, not Alpaca paper-trading. The Alpaca reference files have been removed from this project tree.

## User Goal (verbatim)

> Build a weather-prediction MCP server backed by Open-Meteo and prepare a Databricks Agent Bricks agent that uses it. Deploy the MCP server as a Databricks App after Tolu approves deployment. Use the forked reference repo at `https://github.com/ToXMon/databricks-lakebase-app-day-3-Tolu.git` (style reference only — no Alpaca at runtime). Tool names: `get_current_weather`, `get_weather_forecast`, `get_weather_recommendation`. Build path: `/home/opadmin/databricks_bootcamp/homework/day3/`. Completed project returns to Agent Zero for independent review before any commit or push. Be cost-conscious — no expensive frontier models in our code; use Databricks-supported open/cost-effective models.

## What Was Built

- **`mcp_server/`** — FastMCP 3.4.6 server with three `@mcp.tool` functions (exact names above), thin wrappers around `mcp_server/openmeteo_adapter.py`. Streamable HTTP transport at `/mcp`. Port `DATABRICKS_APP_PORT` → `PORT` → `8000`. 304 LOC.
- **`mcp_server/openmeteo_adapter.py`** — HTTP/parsing adapter with `WeatherAdapterError`, `requests.Session` (swappable for tests), 5s/10s timeouts, lat/lon + days-in-1-7 validation, status-code + JSON-shape validation, ISO 8601 strings, WMO weather-code descriptions. 270 LOC.
- **`mcp_server/weather_codes.py`** — WMO code → description map. 50 LOC.
- **`dashboard/`** — Flask app (3 panels: Current / Forecast / Recommendation), vanilla JS, `prefers-color-scheme` dark/light, reuses the Open-Meteo adapter. 686 LOC across `app.py` + `templates/index.html` + `app.yaml` + `requirements.txt`.
- **`tests/`** — 31 mocked tests, no live HTTP, no Databricks auth. Uses `conftest.py` `FakeSession`/`FakeResponse` fixtures.
- **`README.md`** — public source of truth (architecture, setup, deploy, system prompt, demo questions, troubleshooting).
- **`AGENTS.md`** — project DOX (ownership boundaries, stable contracts, what-changes-require-doc-updates, human-gate checklist).
- **`EVIDENCE.md`** — facts-only verification log; VERIFIED rows where the build proves them, `PENDING HUMAN EVIDENCE` rows for Tolu's workspace actions.
- **`EVAL_REPORT.md`** — adversarial evaluator's verdict (ACCEPT, no high bugs).
- **`PLAN.md`** — original builder plan (frozen).
- **`TRANSCRIPT_NOTES.md`** — Day 3 class transcript ↔ build reconciliation.
- **`evidence/`** — empty directory; Tolu drops demo screenshots here.

## What Tolu (the human) Must Do

All gates are documented in `AGENTS.md` § "Databricks Human Gates" + `README.md` § "Databricks Apps deployment". Summary:

1. `sudo chown -R opadmin:opadmin /home/opadmin/agent-stack/volumes/agent-zero/projects/databricks-day3-weather-mcp` — DONE in turn 5.
2. `databricks auth login --host https://<workspace>`
3. `databricks apps create mcp-weather` (UI alternative: Compute → Apps → Create app; name must start with `mcp-`)
4. Sync + deploy: `databricks sync mcp_server/ "/Users/<you>/mcp-weather"` then `databricks apps deploy mcp-weather --source-code-path "/Workspace/Users/<you>/mcp-weather"`
5. Copy the app URL from the Apps UI; the MCP endpoint is `<url>/mcp`.
6. AI Gateway → MCPs → Add MCP, paste endpoint, save.
7. Agents → Agent Bricks → Create agent. Attach the weather MCP. Paste the verbatim system prompt (in `README.md` and `AGENTS.md`).
8. Choose a Databricks-supported open-source / cost-effective FM (Llama 3.x 70B, DBRX, etc.).
9. Grant `CAN USE` to your reviewer on the MCP server app (and on the dashboard app if deployed).
10. Run the three demo questions; capture evidence; populate `EVIDENCE.md`'s `Demo 1/2/3` rows.
11. Package as a ZIP and submit per Tolu's submission channel.

## Operating Rules Carried Over From The Original Brief

1. Inspect git status, remotes, README, file tree, existing modules, app configs, tests before editing.
2. DOX: update affected `AGENTS.md` when contracts change.
3. Minimal focused changes. Preserve useful patterns; avoid unrelated refactors.
4. Cost-effective models only.
5. Hand-hold Tolu through every Databricks UI/OAuth/deploy step.
6. Never invent test results, URLs, deployment status, IDs, screenshots, demo answers.
7. No commit, push, PR, deploy, or permission change without explicit human approval.
8. Never expose tokens, secrets, `.env` contents, private workspace data.

## What Engineer Will Not Do

- ❌ Commit, push, PR.
- ❌ Deploy the MCP server App.
- ❌ Register the external MCP.
- ❌ Create the Agent Bricks agent.
- ❌ Choose the FM.
- ❌ Run the demos.
- ❌ Grant `CAN USE`.
- ❌ Modify workspace permissions.

All of those are Tolu's. `EVIDENCE.md` is explicit about which rows are `PENDING HUMAN EVIDENCE` vs `VERIFIED`.

## Final State (turn 5)

- 31/31 mocked tests green (verified inside this A0 project tree after integration).
- Live Open-Meteo smoke green (Lagos geocode, current, 5-day forecast).
- Live MCP smoke green (`/mcp` returns HTTP 200, valid MCP `initialize` response).
- Live dashboard smoke green (`/healthz` 200, `/api/current_weather?location=Lagos` 200, missing-location 400).
- No secrets, no fabricated URLs, no Alpaca imports.
- Two working trees, both uncommitted:
  - `/home/opadmin/databricks_bootcamp/homework/day3/` (original)
  - `/home/opadmin/agent-stack/volumes/agent-zero/projects/databricks-day3-weather-mcp/` (Agent Zero project, identical contents)

**No commit or push performed.**
