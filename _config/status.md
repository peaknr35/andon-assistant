# Build Status

_Status is derivable from the filesystem: a path existing = that piece is built.
This file is the human-readable summary._

## Current state
Andon Assistant is a local-first agent (terminal + dashboard, one SQLite brain, dual-track
tool calling) with Deep Research Studio as a tool. M1-M3 complete; demo-prep + two-way
calendar sync landed 2026-10-12. Calendar sync ships OFF by default (needs OAuth setup).

## Done -- v0.1 Deep Research Studio (2026-10-05)
- [x] FastAPI SSE research backend (OpenAI/Anthropic/Kimi, BYO key) + provider factory
- [x] web search (DuckDuckGo) + plan->research->report pipeline
- [x] Next.js streaming UI: compare mode, API-key manager, Google Docs export
- [x] Docker + docker-compose + Cloud Run deploy; docs (api/setup/changelog); 19 tests

## Done -- per-folder ICM (2026-10-06)
- [x] A CONTEXT.md in every folder, `_templates/` starters, generated `FILE-MAP.md`

## Done -- M1 local agent core (2026-10-06)
- [x] SQLite memory (facts/turns/tool_runs/calendar/skills) + recall + consolidation gate
- [x] Tool registry: web_search, deep_research, remember/recall, calendar (local), file (sandboxed)
- [x] Dual-track engine (manual prompt-JSON + PydanticAI), visible turn loop
- [x] POST /chat/stream + /memory + /trace; Rich TUI (python -m app.cli)

## Done -- M2 chat dashboard (2026-10-06)
- [x] Chat home with live turn timeline (phases, tool cards, memory) over SSE
- [x] Read-only memory panel; lib/api.ts generalized; ChatContext persistence
- [x] Research moved to /research; nav rebranded; typecheck + build green

## Done -- M3 skills, evals, calendar (2026-10-06)
- [x] skills/ loader (markdown procedures in the system prompt)
- [x] evals/: deterministic (offline) + LLM-as-judge + `python -m evals.run`
- [x] Optional calendar sync (local SQLite stays source of truth); 28 tests

## Done -- demo prep + calendar sync (2026-10-12)
- [x] Rebrand to "Andon Assistant" (header, title, config, docs)
- [x] deep_research sped up (parallel searches + one report, ~60s -> ~12s)
- [x] Anthropic model picker expanded (Opus 4.7-5.5, Sonnet, Haiku, Fable)
- [x] Agent knows today's date; CLI auto-loads backend/.env
- [x] Handoff kit: docs/GETTING-STARTED.md + setup.ps1 / run.ps1 + .env.example
- [x] five-whys-rca skill + seed_demo.py demo data
- [x] Two-way calendar sync: Google + Outlook (push + pull + dedup + periodic), off by default
- [x] Tests: added tests/test_calendar_sync.py

## Done -- ICM workflows step 1: file-backed deep research (2026-10-14)
- [x] `workflows/deep_research/` stage contracts (01_plan, 02_search, 03_report)
- [x] `run_research` writes each stage to `~/.assistant/runs/<run>/`; stages hand off via files
- [x] `resume_research` re-runs from a stage using edited `plan.md` / `evidence.md`
- [x] Andon STOP: no sources anywhere -> `STOP.md` + `error(stop)`; per-question GAPs, no guessing
- [x] Chat `deep_research` tool marks unsourced answers NOT source-backed; 40 tests

## Next / ideas
- [ ] ICM step 2: `await_approval` event + `POST /runs/{id}/decision` (calls `resume_research`)
- [ ] ICM step 3: `memory_candidates/` review step (behind a setting, off by default)
- [ ] ICM step 4: eval that replays a run folder and checks each stage
- [ ] Token-streamed replies (manual backend); agent.iter live streaming (PydanticAI)
- [ ] FTS5 / sqlite-vec recall (swap behind `store.recall`)
- [ ] Calendar: live OAuth setup (user's Google Cloud + Entra apps), then verify two-way
- [ ] Optional page-content fetch / Tavily search backend when a key is provided

## Open
- PydanticAI backend wired + model construction tested; full live-turn validation needs a key.
- Calendar sync code done; cannot be live-tested until the user creates the Google/Azure apps.
