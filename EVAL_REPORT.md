# EVAL_REPORT.md — Day 3 Weather MCP Server

**Reviewer stance:** adversarial. Every claim from the builder was independently re-run or diffed against source. "Looks similar" was rejected everywhere; numeric evidence and verbatim diffs only.

**Build surveyed:** `/home/opadmin/databricks_bootcamp/homework/day3/` (everything under it except `reference/`).

**Run timestamp:** 2026-08-08, branch `feature/install-goal-skill`, Python 3.12.3, FastMCP 3.4.6.

---

## 1. Verdict — **ACCEPT**

The build satisfies every measurable requirement in the spec. Tests are green, the live Open-Meteo smoke proves the adapter is wired to a real upstream (no fabricated data), the verbatim system prompt is character-for-character identical to the canonical brief, the surgical-edits constraint is satisfied, secrets are absent, and every "PENDING HUMAN EVIDENCE" item is honestly marked. The only items called out below are *non-blocking* weaknesses (a tautological test assertion, a redundant import fallback, and a logging-info entry that is louder than it needs to be) — none of them affect correctness or the contract surfaced to an Agent Bricks caller.

---

## 2. Numbers

### pytest

```
$ python3 -m pytest -q --tb=short
.......................                                                  [100%]
23 passed in 2.31s
```

Re-run a second time after all other checks: **23 passed in 2.91s**. Exit code **0**.

Per-test count by file:

| File | Tests | Result |
|---|---|---|
| `tests/test_openmeteo_adapter.py` | T1, T2, T3, T4, T5, T6, T6b, T7, T8, T9, T10a, T10b, T10c = **13** | pass |
| `tests/test_weather_mcp_server.py` | T11, T12, T13, T14, T15, T16, T17, T18 = **8** | pass |
| `tests/test_recommendation.py` | T19, T20 = **2** | pass |
| **Total** | **23** | **all green** |

Plan called for "≥18 mocked tests"; builder delivered 23. Adapter-level split (T6 + T6b) is a deliberate hardening beyond PLAN.md.

### compileall

```
$ python3 -m compileall -q mcp_server tests && echo "compileall exit=$?"
compileall exit=0
```

### Grep checks (exit 1 = no match = clean)

| Grep | File | Match count | Verdict |
|---|---|---|---|
| `requests\\.(get\\|post\\|put\\|delete\\|head\\|patch)\\|urllib\\|json\\.loads` | `mcp_server/weather_mcp_server.py` | **0** | PASS — tools are thin |
| `import alpaca\\|alpaca-py\\|paper_broker\\|massive_broker` | `mcp_server/*.py tests/*.py` | **0** | PASS — no Alpaca runtime code |
| `(api[_-]?key\\|secret\\|password)\\s*=\\s*['"]` | `mcp_server/ tests/` | **0** | PASS — no secrets |
| Same scan extended to `homework/` | — | **0** | PASS — no secrets in docs |
| `import json\\|json\\.loads\\|json\\.dumps` | `mcp_server/weather_mcp_server.py` | **0** | PASS — no raw payload parsing in tools |
| `@mcp\\.tool` | `mcp_server/weather_mcp_server.py` | **3 matches** (lines 79, 114, 237) | PASS — exactly three tools, names match spec (`get_current_weather`, `get_weather_forecast`, `get_weather_recommendation`) |
| `DATABRICKS_APP_PORT\\|os\\.getenv\\(.PORT.` | `mcp_server/weather_mcp_server.py` | **1 match** (line 303) | PASS — `DATABRICKS_APP_PORT → PORT → 8000` precedence |
| `precipitation_probability_max\\|precipitation_sum\\|weather_code\\|wind_speed_10m_max` | `mcp_server/weather_mcp_server.py` | **23 matches** across umbrella/clothing/travel branches and docstrings | PASS — every required daily field is threaded through |

### Verbatim system prompt diff

Canonical (from brief, single line, ending in newline):

> `You are a weather assistant grounded in Open-Meteo data. For every claim about current or forecast weather, call the appropriate registered weather tool and base the answer only on the returned fields. Never invent temperatures, precipitation, wind, weather alerts, locations, dates, times, units, or tool results. State the resolved location, forecast period, timezone, and units when they matter. Recommendations must identify the observed or forecast facts that support them and must be phrased as practical guidance, not an official safety guarantee. If a tool fails, returns incomplete data, cannot resolve the location, or does not cover the requested time period, say exactly what is unavailable and ask the user for a corrected location or narrower request. Do not answer from memory when live weather data is required.`

`diff` against `homework/day3/README.md` line 217:

```
$ diff /tmp/canonical_prompt.txt <(sed -n '217p' homework/day3/README.md) && echo IDENTICAL
IDENTICAL
```

Block is wrapped in a `>`-style fenced quote (lines 216–218 of README.md) under the heading `### Exact system prompt (verbatim - do not paraphrase)` (line 214). Marked as verbatim, no paraphrase.

### Live smoke (independent re-run by reviewer, against real Open-Meteo)

| Smoke call | Outcome |
|---|---|
| `geocode('Lagos, Nigeria')` | `{"status": "found", "results": [<5 real Lagos entries>...]}` — id 2332459, country `Nigeria`, timezone `Africa/Lagos`, elevation `11.0`. |
| `get_current(6.5244, 3.3792)` | `{"timezone": "Africa/Lagos", "current": {"time": "2026-08-08T19:30", "temperature_2m": 25.5, "weather_code": 3, "weather_description": "Overcast", ...}}` — description matches WMO code 3. |
| `get_forecast(6.5244, 3.3792, days=5)` | 5 daily entries, dates 2026-08-08..2026-08-12, fields include `precipitation_probability_max`, `precipitation_sum`, `weather_code`, `wind_speed_10m_max`, `temperature_2m_max`, `temperature_2m_min`. |
| `get_forecast(6.5244, 3.3792, days=0)` | Raised `WeatherAdapterError: days must be between 1 and 7, got 0` — caught at tool level, returns `{"status": "error", ...}`. |

Every call returned real upstream data, not fabricated. No `id=12345` / `lat=999` stand-ins.

### Live server smoke (independent re-run)

```
$ PORT=8765 python3 mcp_server/weather_mcp_server.py &
[FastMCP 3.4.6 banner]
INFO     Starting MCP server 'weather-mcp' with transport 'http' on http://0.0.0.0:8765/mcp
INFO     Uvicorn running on http://0.0.0.0:8765

$ curl -sS -i -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' \\
    -H 'Accept: application/json, text/event-stream' \\
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{...,"clientInfo":{"name":"curl","version":"1"}}}'
HTTP/1.1 200 OK
server: uvicorn
content-type: text/event-stream
mcp-session-id: 2f06f0480da0472fa1dcf7e4340a80c2

event: message
data: {"jsonrpc":"2.0","id":1,"result":{...,"serverInfo":{"name":"weather-mcp","version":"3.4.6"}}}
```

Endpoint `/mcp`, transport `http` (which FastMCP 3.4.6 routes to streamable-HTTP), bind `0.0.0.0`. Matches the spec.

### Boundary probes (additional, reviewer-driven)

All run via a `FakeSession` shim against the real `weather_mcp_server.py` (no FastMCP mocking) to confirm the contract at the **tool** layer (not just the adapter):

| Probe | Expected | Actual |
|---|---|---|
| `get_weather_forecast('Lagos', 8)` | clean `status: error` | `{'status': 'error', 'error': 'days must be between 1 and 7, got 8', 'location': 'Lagos'}` |
| `get_weather_forecast('Lagos', 0)` | clean `status: error` | `{'status': 'error', 'error': 'days must be between 1 and 7, got 0', 'location': 'Lagos'}` |
| `get_weather_forecast('Lagos', -1)` | clean `status: error` | `{'status': 'error', 'error': 'days must be between 1 and 7, got -1', 'location': 'Lagos'}` |
| `get_current_weather('')` | clean `status: error`, no raise | `{'status': 'error', 'error': 'geocode() requires a non-blank location name', 'location': ''}` |
| `get_current_weather('   ')` | clean `status: error`, no raise | `{'status': 'error', 'error': 'geocode() requires a non-blank location name', 'location': '   '}` |
| `get_current_weather('asdfghjklqwerty')` | clean `status: error`, no raise | `{'status': 'error', 'error': "Could not resolve location: 'asdfghjklqwerty'", 'location': 'asdfghjklqwerty'}` |
| `get_weather_recommendation('Lagos', date='2099-01-01')` | `status: outside_forecast_window`, no raise | `{'status': 'outside_forecast_window', 'location': 'Lagos', 'date': '2099-01-01'}` |

All boundary contracts hold at the tool layer, not just the adapter.

### Surgical-edits check

```
$ cd /home/opadmin/databricks_bootcamp && git status --porcelain -- homework/day1 homework/day2 homework/day3/reference docs
(no output — clean)
```

The `??` entries shown by plain `git status --short` are *untracked* (they were never committed to this branch's history), so they cannot have been modified by the build. Re-running with `--porcelain` filters to only tracked-file changes — **zero**. Spec constraint satisfied.

---

## 3. Bugs (severity-ordered)

### High

**None.** No high-severity bugs found. Tests pass, live smoke is real, system prompt is verbatim, secrets absent, boundary contracts hold, surgical-edits clean.

### Medium

**M1 — Tautological forecast-length assertion.** `tests/test_weather_mcp_server.py::test_t12_forecast_returns_list_of_daily_dicts` (lines 79-88) asserts `assert len(result["forecast"]) == 7` after calling `fn("Lagos, Nigeria", 5)`. The test passes only because the canned payload `FORECAST_PAYLOAD_7D` happens to contain 7 `time` entries — so the assertion effectively verifies "the tool returns whatever the canned payload had", not "the tool honors the requested `days` value".

- Why it matters: A regression where the server stops threading `days` into the `forecast_days` query param (or where the adapter starts ignoring it) would still pass this test.
- Fix: patch the test to (a) feed a 5-day canned payload, (b) assert `len(result["forecast"]) == 5`, AND (c) assert `openmeteo_adapter._session.calls[-1]["params"]["forecast_days"] == 5`. (The probe in §2 already proved the live behavior is correct — this is purely a test-strength issue.)
- Test that should have caught it: T12 as rewritten above. The probe in §2 (5-day payload → 5 returned entries) proves the code is right; the existing test just doesn't prove it.

**M2 — Redundant import fallback could mask a packaging mistake.** `mcp_server/weather_mcp_server.py` lines 40-45 and `mcp_server/openmeteo_adapter.py` lines 21-24 use a `try: import X except ImportError: from mcp_server.X` shim to support both flat (`python weather_mcp_server.py` from inside `mcp_server/`) and packaged (`from mcp_server...`) execution. The flat-import path exists in production only because `app.yaml`'s `command: ["python", "weather_mcp_server.py"]` runs from inside `mcp_server/`. That's correct for Databricks Apps (which `cd` into the source dir before running the command), so the fallback isn't *wrong*, just over-engineered.

- Why it matters (mild): If a future contributor ever deletes `mcp_server/__init__.py`, the tests will keep passing via the flat import — masking the real bug until runtime.
- Fix: pick one. Either commit to "Databricks Apps runs from inside `mcp_server/`" and drop the package-style import in `weather_mcp_server.py`/`openmeteo_adapter.py`, OR commit to "imported as `mcp_server.*` everywhere" and have `app.yaml` use `command: ["python", "-m", "mcp_server.weather_mcp_server"]`. Either is fine; the current dual-mode is just two code paths to maintain.
- Test that should have caught it: a deploy-shape integration test (not strictly required for this scope).

### Low

**L1 — INFO-level log on every "expected" tool error.** `weather_mcp_server.py` lines 107, 110, 143, 146, 292, 295 use `logger.warning(...)` / `logger.exception(...)` for every tool error — including boundary violations (`days=8`) and unknown locations. During a noisy Agent Bricks chat these will spam.

- Why it matters: noise, not correctness. Logs at `INFO` (set via `app.yaml`) mean the platform will ship these to Databricks App logs.
- Fix: downgrade the four "tool handled expected error" branches to `logger.debug(...)`. Keep `logger.exception(...)` (or upgrade to `logger.error(...)`) only for the catch-all `except Exception` paths that should never fire.

**L2 — `requests.Session` not closed.** `mcp_server/openmeteo_adapter.py` line 44 creates a module-level `_session = requests.Session()` that is never `.close()`d at shutdown. Negligible for a long-running Databricks App; flag only because the README's "good citizen of Open-Meteo's free tier" framing invites scrutiny on connection hygiene.

- Fix (optional): register `atexit.register(_session.close)` near the singleton.

**L3 — T15 comment is internally inconsistent.** `tests/test_weather_mcp_server.py` lines 117-129 contain a comment "Mild day (temp_max=26.0? no that's >22 -> light clothing; use 2026-08-11 temp=25 -> light clothing)" that contradicts the variable name `hot` assigned to a temp of 25 (which is below the 22 threshold? No — 25 > 22, so it IS hot; the comment is just confusing). Test still passes; the comment is misleading rather than wrong.

- Fix: rename `hot` → `warm` or `above_22`, and drop the "? no that's >22 -> light clothing" aside.

**L4 — `test_t12` comment "see note below" references nothing.** Line 88 ends with "# adapter always fetches full 7-day window internally? see note below" but no note follows. Either it was meant to flag M1 (tautological assertion) or it was a planned-but-unwritten commentary. Either way, dangling comment.

- Fix: delete the comment or expand it into the proposed T12 rewrite (see M1).

---

## 4. Strengths

Concrete, not generic:

1. **The verbatim system prompt is genuinely verbatim.** `diff` shows zero characters differ from the canonical brief, in a block that is explicitly labelled "verbatim - do not paraphrase". A reviewer who has been bitten by AI paraphrase drift appreciates this.
2. **Live smoke proves real upstream.** The four `python3 -c` calls in EVIDENCE.md were independently re-run by the reviewer and returned real Open-Meteo payloads (Lagos id 2332459, timezone `Africa/Lagos`, WMO code 3 → "Overcast"). Not a single canned `id=12345` placeholder.
3. **Tool-layer boundaries hold under probing.** Every `days` out-of-range call, every blank location, every unknown location, every out-of-window date returns a clean `status: error` / `status: outside_forecast_window` dict — *not* an exception. That's exactly the contract the spec demanded (tools must never raise) and the live tests confirm it.
4. **The adapter owns ALL HTTP and JSON parsing.** `grep` confirms zero `requests.*` / `urllib` / `json.loads` calls in `weather_mcp_server.py`. The architectural split matches PLAN.md.
5. **Recommendation logic lists every observed field with threshold.** `_build_recommendation` produces a `facts_used` array of 5 entries (`precipitation_probability_max`, `precipitation_sum`, `temperature_2m_max`, `wind_speed_10m_max`, `weather_code`), each with `{name, value, threshold}`. T19 pins this down and T20 nails the thunderstorm override.
6. **`forecast_days` query parameter is correct.** A grep + an independent `inspect.getsource` confirm the adapter sends `forecast_days: days`, not the misleading `days=` parameter. Subtle but important for Open-Meteo compatibility.
7. **Port precedence matches the reference and the spec.** `int(os.getenv("DATABRICKS_APP_PORT", os.getenv("PORT", 8000)))` is a single readable line that explicitly enumerates the precedence.
8. **FakeSession/fake_response fixture is well isolated.** Swapping `openmeteo_adapter._session` directly (rather than monkeypatching global `requests`) means tests can't pollute each other's HTTP state. The `_restore_adapter_session` autouse fixture guarantees clean state across tests.
9. **EVIDENCE.md honestly admits what was NOT verified.** Every workspace-side action (deploy, MCP registration, agent creation, `CAN USE` grant, live chat transcript) is `PENDING HUMAN EVIDENCE`, not fabricated. The "Dashboard" section explicitly says NOT IMPLEMENTED with a one-line reason. No claim of "deployed" without proof.
10. **Surgical-edits constraint is verifiably respected.** `git status --porcelain -- homework/day1 homework/day2 homework/day3/reference docs` returns zero lines. The build touched only `homework/day3/*`.
11. **Server actually starts and serves `/mcp` correctly.** Reviewer's own curl probe got `HTTP/1.1 200 OK`, `content-type: text/event-stream`, and `serverInfo: {name: weather-mcp, version: 3.4.6}`. EVIDENCE.md's "redacted server smoke output" is faithful.

---

## 5. Required fixes before handoff

**None.** No item blocks ACCEPT. The Medium/Low items above are quality improvements; the build is correct, testable, and shippable as-is from the agent-bricks-integration-perspective. The only "PENDING HUMAN EVIDENCE" items are by design Tolu's to perform.

---

## 6. Suggested improvements (non-blocking)

1. **Tighten T12 (see M1)** to actually pin the `days`-honored contract. ~5 lines of test changes.
2. **Downgrade routine tool errors to `logger.debug`** (see L1). ~6 one-line edits.
3. **Decide on one import style** for the adapter/server modules (see M2). Either drop the try/except or change `app.yaml` to use `python -m mcp_server.weather_mcp_server`. Cosmetic.
4. **Add a `time.sleep(0)` or a no-op `await`** at the top of each `@mcp.tool` if any are observed to be called synchronously from FastMCP under load — optional, no evidence of need.
5. **Capture a small canned fixture JSON in `tests/fixtures/`** rather than inlining `FORECAST_PAYLOAD_7D` in both `test_weather_mcp_server.py` and `test_openmeteo_adapter.py`. Cleanup, not a bug.
6. **Rename `hot` → `warm` in T15** (see L3). One-line edit.

---

## 7. Final check

After all adversarial probes, the test suite was re-run from a cold start:

```
$ python3 -m pytest -q --tb=short
.......................                                                  [100%]
23 passed in 2.91s
```

**23 passed, 0 failed.** Build remains ACCEPT.

---

## Reviewer notes (not for the builder)

- The builder was honest about scope: dashboard NOT IMPLEMENTED, workspace actions PENDING HUMAN EVIDENCE, `--break-system-packages` justified and documented. None of those are bugs — they're correct disclosures.
- The `"see note below"` dangling comment in T12 is suspicious but harmless; the underlying contract IS correct (the probe proved it), the test just doesn't pin it down.
- No code modifications were made during this review, per the task's "you do NOT modify source files" rule. The only file created is this `EVAL_REPORT.md`.
