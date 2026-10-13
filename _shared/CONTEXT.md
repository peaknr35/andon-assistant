# _shared -- cross-cutting contracts (ICM Layer 3, the single source of truth)

One job: the facts BOTH apps (and the terminal) must agree on. This is the
authoritative home; the backend and frontend mirror these.

## What's here
- `agent-turn-contract.md` -- the chat turn SSE schema. Mirrored by
  `backend/app/models/chat.py` and `frontend/lib/chatTypes.ts`.
- `memory-schema.md` -- the SQLite tables + the calendar sync ledger. Mirrors
  `backend/app/memory/schema.sql`.
- `tools.md` -- the tool registry + how a tool node is shaped (both backends).
- `calendar-sync.md` -- the two-way calendar sync subsystem (provider shape, push/pull,
  dedup, env flags). Mirrored by `tools/{google,outlook}_calendar.py` + `services/calendar_sync.py`.
- `api-contract.md` -- the research endpoints + SSE event schema. Mirrored by
  `backend/app/models/research.py` and `frontend/lib/types.ts`.
- `providers.md` -- the provider/model matrix. Mirrored by `backend/app/config.py`
  + `routes/health.py` and `frontend/lib/models.ts`.
- `research-workflow.md` -- the plan->research->report pipeline (the `deep_research` tool).

## Rules
- Change a contract HERE FIRST, then update every mirror in the same change.
- One home per fact: defined here -> others link, never re-state.

## Links
- Backend: `../backend/CONTEXT.md` . Frontend: `../frontend/CONTEXT.md` . Root: `../CLAUDE.md`
