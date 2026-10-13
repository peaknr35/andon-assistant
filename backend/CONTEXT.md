# Backend (FastAPI) -- contract

One job: the local-first assistant brain + the deep-research pipeline. Exposes a
streaming chat turn (`/chat/stream`), read-only memory/trace, the research stream,
a health check, and a provider catalog. A terminal TUI runs the same turn loop.

## Inputs
- Reference (every change): `../_shared/agent-turn-contract.md`,
  `../_shared/memory-schema.md`, `../_shared/tools.md`, `../_shared/calendar-sync.md`,
  `../_shared/api-contract.md`, `../_shared/providers.md`,
  `../_shared/research-workflow.md`, `../_config/conventions.md`.
Do NOT load: the frontend. The only coupling is the SSE contracts above.

## Structure
```
app/
  main.py            FastAPI app, CORS, routers, lifespan (optional calendar-sync loop)
  config.py          Settings (env APP_*) + provider/agent/file/db/calendar settings
  logging_config.py  logging + redact() (never log keys)
  agent/             the turn loop (loop.py), dual-track engine (generate.py), prompts, skills
  memory/            SQLite brain: schema.sql, db.py (connect+migrate), store.py
  tools/             registry + web_search, deep_research, calendar (local+2-way
                     Google/Outlook), file, memory tools
  providers/         LLM clients behind the LLMClient protocol (+ build_client)
  services/          research pipeline (the deep_research tool) + web search + calendar_sync
  models/            Pydantic models: research.py, chat.py (TurnEvent)
  routes/            health.py (/health,/providers), research.py (/research/stream),
                     chat.py (/chat/stream, /memory, /trace)
  cli.py             Rich TUI terminal: python -m app.cli (auto-loads .env)
evals/               (M3) deterministic + LLM-as-judge eval runner
scripts/             one-off: seed_demo.py, google_auth.py, outlook_auth.py
tests/               pytest: health, auth, providers, research stream, agent, calendar sync
```

## Flow (a chat turn)
`routes/chat.py` -> `agent/loop.run_turn()` yields TurnEvents (RECEIVE -> RECALL ->
REASON/ACT/OBSERVE via `agent/generate.run_middle` -> REMEMBER -> REPLY). Tools come
from `tools/registry.build_registry(client)`; memory from `memory/store`.

## Run / test
- Terminal: set `APP_API_KEY` (or fill `backend/.env`), then `python -m app.cli`.
- API: `uvicorn app.main:app --reload --port 8080`.
- Tests: `pip install -r requirements-dev.txt && pytest`.

## Human check
`pytest` green; `python -m app.cli` shows the banner; a chat turn streams phases and a
fact survives a restart. `GET /health` -> ok.

## Avoid
- Logging anything key-shaped (use `redact()`).
- Business logic in routes/tools -- put turn logic in `agent/`, memory SQL in `memory/`.
- File writes outside `APP_FILE_ROOT` unless `APP_FILE_UNRESTRICTED=1`.
