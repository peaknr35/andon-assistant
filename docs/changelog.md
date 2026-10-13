# Changelog

## 2026-10-12 -- demo prep + two-way calendar sync
- Rebrand to "Andon Assistant" (header, page title, config, README, CLAUDE.md).
- `deep_research` tool sped up ~60s -> ~12s (parallel web searches + one tight cited report);
  the full progressive pipeline + `/research` UI unchanged.
- Expanded the Anthropic model picker (Opus 4.7/4.8/5/5.5, Sonnet 5/5.5, Haiku 4.5/5.5, Fable 5.1)
  across `models.ts`, `/providers`, and `_shared/providers.md`.
- Agent is told today's date (relative dates resolve); the CLI auto-loads `backend/.env`.
- Handoff kit: `docs/GETTING-STARTED.md`, `setup.ps1` / `run.ps1`, `backend/.env.example`.
- `skills/five-whys-rca.md` + `backend/scripts/seed_demo.py` (demo data).
- Two-way calendar sync (OFF by default): `outlook_calendar.py` (Microsoft Graph) + extended
  `google_calendar.py` (token refresh + list) + `services/calendar_sync.py` (pull + dedup) +
  `events.outlook_id` + one-time auth scripts; `docs/CALENDAR-SYNC.md`; `tests/test_calendar_sync.py`.
- ICM freshness pass: refreshed the CONTEXT.md files, root CONTEXT/CLAUDE, `_shared` contracts
  (new `calendar-sync.md`), status, regenerated FILE-MAP; archived two stray root files.

## 2026-10-06 -- 0.2.0 (M3: skills, evals, Google calendar)
- `skills/`: user-editable markdown procedures surfaced to the agent (daily-standup,
  summarize-url), loaded by `agent/skills.py`.
- `evals/`: deterministic offline checks (17) + LLM-as-judge over the turn trace;
  `python -m evals.run [--deterministic|--judge]`.
- Optional Google Calendar sync for `calendar_create` (`APP_GOOGLE_CALENDAR=1`); the
  local SQLite calendar stays the source of truth, sync is best-effort.
- Tests: 28 passing.

## 2026-10-06 -- 0.2.0 (M2: chat dashboard)
- Frontend chat home with a live turn timeline (phase badges, tool-call cards,
  recalled/saved memory) streamed over SSE, plus a read-only memory panel.
- `lib/api.ts` generalized (streamResearch + streamChat + fetchMemory/Trace); new
  ChatContext persists chat across navigation. Research moved to `/research`.

## 2026-10-06 -- 0.2.0 (M1: local agent core)
- Evolved Deep Research Studio into a local-first personal agent; the research pipeline
  is now the `deep_research` tool.
- Visible turn loop with dual-track tool calling (PydanticAI + manual prompt-JSON); one
  local SQLite brain with recall + consolidation gate; tools (web_search, deep_research,
  remember/recall, local calendar, sandboxed file I/O); `POST /chat/stream` + a Rich TUI.

## 2026-10-06 -- docs: complete per-folder ICM
- A `CONTEXT.md` in every folder, `_templates/` starters, and a generated `FILE-MAP.md`.

## 2026-10-05 -- 0.1.0 (initial build)
- Deep Research Studio: FastAPI SSE research backend (OpenAI/Anthropic/Kimi, BYO key) +
  Next.js streaming UI (compare mode, key manager, Google Docs export). 19 tests.
