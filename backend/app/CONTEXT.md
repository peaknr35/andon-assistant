# backend/app -- the FastAPI application package

One job: the importable app. `main.py` assembles it; everything else is grouped by
role so each kind of thing has exactly one home.

## What's here
- `main.py` -- FastAPI app: config, logging + CORS, routers, and a lifespan that runs the
  optional periodic calendar sync (only when a provider is enabled).
- `config.py` -- `Settings` (env prefix `APP_`): providers, agent, file/db, calendar sync.
- `logging_config.py` -- logging setup + `redact()` (never log keys).
- `agent/` -- the visible turn loop (`loop.py`), the dual-track engine (`generate.py`),
  prompts, and skill loading.
- `memory/` -- the single SQLite brain: `schema.sql`, `db.py` (connect + migrate),
  `store.py` (facts/turns/tool_runs/calendar + the sync-dedup upsert).
- `tools/` -- the tool registry + web_search, deep_research, calendar (local + 2-way
  Google/Outlook), file I/O, remember/recall.
- `services/` -- business logic: the research pipeline, web search, calendar pull-sync.
- `providers/` -- LLM clients behind the `LLMClient` protocol + `build_client()`.
- `models/` -- Pydantic request + event models (+ `EventFactory`).
- `routes/` -- HTTP/SSE endpoints (thin handlers).
- `cli.py` -- the Rich TUI terminal (`python -m app.cli`; auto-loads `backend/.env`).
- `__init__.py` -- marks the package.

## Layering (one-directional)
routes -> agent (turn loop) -> tools + memory + providers + services; config + logging
are leaf utilities. Handlers stay thin; turn logic in `agent/`, memory SQL in `memory/`.

## Rules
- Never log key-shaped text: pass it through `logging_config.redact()`.
- Settings come from env (prefix `APP_`); no secrets in code or config files.

## Where to add things
- New tool -> `tools/` (`../../_templates/new-tool.md`).
- New endpoint -> `routes/` (`../../_templates/new-endpoint.md`).
- New provider -> `providers/` (`../../_templates/new-provider.md`).
- A turn-loop / phase change -> `agent/` (`../../_shared/agent-turn-contract.md`).

## Links
- Parent: `../CONTEXT.md` . Contracts: `../../_shared/`
