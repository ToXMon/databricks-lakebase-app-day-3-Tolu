# Day 3 Transcript — Verification Notes (from pasted transcript)

Source: Tolu's paste of the Day 3 live session transcript (`docs/...`). The transcript is large; ~125 characters between two markers were hidden in the paste, so the notes below are based on the visible 99%+ of content (intro, lab instructions, and the closing minutes). Workflow signals were extracted from the visible text. Where I cite a moment, the timestamp is from the transcript.

---

## 1. What Day 3 actually is (per Zach, in his own words)

- **"how to give your AI arms"** (≈3:48–3:57). Day 3 is about turning the chat model into an agent that can act — read AND write, place trades, hit external services, etc.
- The **lab** is a "really awesome trading bot" using the vectors + context built in Day 1/2 (≈0:09–0:26).
- **Capstone due Aug 9 11:59 PM Pacific** (≈1:24–1:31, restated ≈1:57:10). This is the deadline for the *capstone* project, NOT the Day 3 MCP homework.
- **MCP homework released "tomorrow morning"** (≈1:57:18). Per Tolu's own prompt to me, the actual MCP homework was released Aug 8 — the same assignment we are building right now (Tolu's "Day 3 Weather MCP" / Open-Meteo server). This is the homework you have until Aug 9 to submit.
- **The MCP homework and the capstone are separate** (Tolu's own turn-2 message: "this is not a replacement for the capstone"). Capstone goes through the DataExpert platform; MCP homework goes through whatever channel Tolu has set up for it (the homework spec asks for a Git repo + Databricks App URLs/screenshots).

## 2. Workflow signals extracted from the transcript (visible content)

### A. App deploy lifecycle (the lab demo) — visible at ≈1:52:00–1:54:39

1. **Build the code** in the dev workspace / notebook.
2. **Deploy as a Databricks App** — Zach shows a deployed agent running.
3. **`/logz` endpoint** — "you can look at log z. So if you if you go to /logz you can also uh see what's going on" (≈1:52:54). He calls it out as a debugging surface, not a required endpoint. **Implication for our build:** a `/logz` endpoint is not a hard requirement, but having structured logs and a `/healthz` is. Our MCP server has `/healthz` only via the MCP transport itself; we should make sure logs stream to Databricks stdout (the App runtime captures them) and that startup messages include the bound port + transport.
4. **Boot on port 8000** — "it just booted up at um port 8000" (≈1:53:03). Confirms Databricks Apps default port is 8000. Our `DATABRICKS_APP_PORT=8000` env in `app.yaml` matches.
5. **Chat-GPT-like experience** is the deployed app's UI (≈1:53:11). This is the Agent Bricks agent surface, NOT the MCP server itself — the MCP server is the *backend* the agent calls. Implication: the MCP server is the Databricks App; the Agent Bricks agent is created in the Agent Bricks UI and is configured to call our MCP server's `/mcp` endpoint.
6. **Multi-turn behavior** — "this is just another like weird bug in the in the the currently deployed settings, right? So that's uh that's the um uh the way to do things" (≈1:54:39). Zach describes a known free-tier limitation where the agent only gets one prompt turn before crashing. **Implication:** when we demo, expect to do single-shot demos and re-init the chat if multi-turn fails. Don't blame our MCP server for that.

### B. Confirmation + risk behavior (the place_trade demo) — visible at ≈1:53:20–1:54:31

- Agent shows reasoning, asks for confirmation, and the user types "Yes. confirm" (≈1:54:27). This is **per-agent prompt design** behavior, not MCP server behavior. Implication: our agent's system prompt should include explicit guardrail language about confirmation if it ever gains write capability. Our MCP server is **read-only** (current weather, forecast, recommendation) so no confirmation logic is needed at the MCP layer.
- "It will only buy a stock. Okay. You see there are several negative news articles about Tesla. So I will not stage a trade for Tesla at this time." (≈1:53:44). This is the **system prompt's job** — guardrails live in the agent's instructions. Our verbatim system prompt in `README.md` does include the "do not answer from memory" + "practical guidance, not official safety guarantee" language. Good.

### C. Model choice guidance — visible at ≈1:50:01

- "Llama 70B is the only one that really works" (≈1:49:54–1:50:01). Zach says without proper evals you can't pick a model objectively. Implication for Agent Bricks model choice: **choose a Databricks-supported open/cost-effective FM** (Llama 3.x 70B, DBRX, etc.) and document it in EVIDENCE.md. We don't pick the FM in code — it's selected in the Agent Bricks UI at deploy time.

### D. Resubmission behavior — visible at ≈1:52:00

- "Resubmission gets a lower score, will that replace my previous higher score? Yes. Yes. It absolutely will." (≈1:50:16–1:50:21), then Andrew says the platform actually keeps the highest (≈1:52:00–1:52:09). There's a discrepancy in Zach's own words. Implication for our submission: **submit only once when ready**, with full evidence. Re-submitting a worse version could hurt. We have everything in `EVIDENCE.md` and `EVIDENCE.md`'s "Demo 1/2/3" rows are explicitly marked `PENDING HUMAN EVIDENCE` until Tolu actually runs the demos — so when Tolu does submit, the evidence is real.

### E. MCP vs. plain functions — visible at ≈1:54:48–1:55:10

- "if you have one agent, right, if you have one agent, then MCP looks really stupid. It looks like you're wasting your time, right? But uh like if you have multiple agents, multiple people, everyone's working, that's going to be the way to do it." (≈1:54:56–1:55:10). Implication: the homework *requires* MCP per its spec, so we honor it. This validates our choice.

### F. Capstone + homework deadlines — visible at ≈1:57:03–1:57:26

- Capstone due Aug 9 11:59 PM Pacific (the *fourth* assignment, separate from MCP homework).
- MCP homework released "tomorrow morning" (≈1:57:18). Today (Aug 8) is when it was released; deadline inferred to be Aug 9 or later.
- Every person submits their own capstone (≈1:55:25). Groups do not submit capstones.

## 3. Reconciliation: does our build match what Zach taught?

| Transcript signal | Our implementation | Match? |
|---|---|---|
| MCP server + Agent Bricks agent + dashboard (Day 3 spec, Tolu's prompt) | `mcp_server/` (FastMCP, 3 tools) + `dashboard/` (Flask, 3 panels) + README steps to register external MCP + create Agent Bricks agent | ✅ |
| App boots on port 8000 (≈1:53:03) | `app.yaml` sets `DATABRICKS_APP_PORT=8000`; `weather_mcp_server.py` resolves port `DATABRICKS_APP_PORT` → `PORT` → `8000` | ✅ |
| Databricks App convention (chat-GPT-like UI after deploy) | MCP server is the backend App; the *Agent Bricks agent* is the chat surface — README documents both | ✅ |
| Verbatim system prompt (Tolu's brief) | Included verbatim in `README.md` and `EVIDENCE.md`, blockquoted, identical character-for-character | ✅ |
| Open-source / cost-effective model (no expensive frontier) | No model calls in our code; README documents Llama 3.x / DBRX as Agent Bricks FM choices | ✅ |
| Confirmation / guardrails at agent layer | Our MCP is read-only; system prompt explicitly forbids inventing weather data + requires citing facts | ✅ |
| "Only one prompt turn" free-tier bug (≈1:54:39) | Documented as expected; demos are single-shot | ✅ (acknowledged) |
| `/logz` (≈1:52:54) for debugging | Not implemented (not a spec requirement); logs go to stdout (Databricks App captures them); `/healthz` is the only non-MCP endpoint | ⚠️ Optional — could add if reviewer wants it |
| Resubmission may overwrite higher score (≈1:50:16) | Our `EVIDENCE.md` distinguishes VERIFIED vs `PENDING HUMAN EVIDENCE`; we recommend single-shot submission | ✅ |
| Multi-agent value of MCP (≈1:54:56) | N/A — homework requires MCP; we honor it | ✅ |

## 4. What Tolu still has to do (human gates, in transcript-aligned order)

These are the steps the transcript implies Tolu performs, mapped to our README:

1. **Build the code** (done by me).
2. **Deploy as a Databricks App** — `Compute → Apps → Create app → Custom` (or `databricks apps create mcp-weather`). README has both.
3. **Find the app URL + `/mcp` endpoint** — copy from Apps UI.
4. **Register as external MCP** — `AI Gateway → MCPs → Add MCP` (or `MCPs → Register external MCP`). README has both.
5. **Build the Agent Bricks agent** — `Agents → Agent Bricks → Create agent`. README has both.
6. **Pick the FM** — open-source / cost-effective (Llama 3.x 70B, DBRX, etc.). README recommends.
7. **Paste the verbatim system prompt** — README has it.
8. **Demo the three questions + screenshot evidence** — README has the questions; EVIDENCE.md has placeholders.
9. **Grant `CAN USE` to the reviewer** — README + AGENTS.md + EVIDENCE.md all mention this.
10. **Submit the ZIP / Git repo** per Tolu's submission channel (separate from the capstone ZIP).

## 5. Items I will NOT do without explicit go

Per Tolu's operating rules + the transcript's resubmission-warning:

- ❌ Commit, push, or PR.
- ❌ Deploy the App (Tolu's workspace, Tolu's OAuth).
- ❌ Register the external MCP.
- ❌ Create the Agent Bricks agent.
- ❌ Choose the FM.
- ❌ Run the three demo questions in the live workspace.
- ❌ Grant `CAN USE` to anyone.
- ❌ Modify workspace permissions.

All of those are gated to Tolu; EVIDENCE.md uses `PENDING HUMAN EVIDENCE` for every such item.

## 6. Discrepancies between my read of the transcript and the task brief

- The transcript describes **Alpaca paper-trading** as the lab demo. The Day 3 *homework* (Tolu's brief + the transcript's "MCP homework released tomorrow" comment) is the **Open-Meteo weather MCP**. **We are not implementing Alpaca at runtime** — the Alpaca pattern is style reference only, as Tolu confirmed ("just use alpaca api is all" → style reference, not runtime dep). The A0 project at `agent-stack/volumes/agent-zero/projects/databricks-day3-weather-mcp/` still contains the Alpaca placeholder files; path A (sudo chown) is what unblocks replacing them with our real Open-Meteo build.
- The hidden ~125 characters in the middle of the transcript paste likely contained the lab walkthrough (model selection screen, tool-attach UI, deploy dialog). Our build is consistent with the standard Databricks custom-MCP docs from Microsoft Learn, so the gap doesn't change the deliverable. **If Tolu has the missing 125 chars and they change anything, paste them and I'll re-verify.**

## 7. Open question for Tolu (path A prep)

Path A (the chown) is safe and reversible:
```bash
sudo chown -R opadmin:opadmin /home/opadmin/agent-stack/volumes/agent-zero/projects/databricks-day3-weather-mcp
```
Once that's done, I will:
1. Remove the stale Alpaca placeholder files (`alpaca_broker.py`, `paper_broker.py`, `lakebase.py`, `massive_broker.py`, `alpaca_mcp_server.py`, `schema_watchlist.sql`, `test_watchlist.py`, `setup_secrets.py`, dashboard's `alpaca_broker.py`/`lakebase.py`/`paper_broker.py`).
2. Copy the real Open-Meteo build (`mcp_server/`, `dashboard/`, `tests/`, `pytest.ini`).
3. Write the project-level `AGENTS.md` (matching the conventions of `space_agent`/`solana_bootcamp`).
4. Replace the placeholder `README.md` + `ADAL_DAY3_WEATHER_MCP_PROMPT.md` with versions describing the Open-Meteo build.
5. Verify all 31 tests still pass inside the A0 project.
6. Hand Tolu the full Databricks step-by-step walkthrough.

Tell me "chown done" and I'll execute steps 1–6 in one shot.
