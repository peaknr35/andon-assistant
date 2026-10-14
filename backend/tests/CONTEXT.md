# backend/tests -- pytest suite

One job: prove the API, auth flow, provider wiring, the agent turn loop, and calendar
sync work -- with no real keys or network (providers + search are mocked).

## What's here
- `conftest.py` -- the `client` fixture (FastAPI `TestClient`); an autouse fixture points
  `APP_RUNS_DIR` at `tmp_path` so research runs never write to `~/.assistant`.
- `test_health.py` -- `/health`, `/`, `/providers`.
- `test_auth.py` -- request validation (422s) + invalid key -> SSE `error` (auth).
- `test_providers.py` -- factory builds the right client; OpenAI happy path +
  auth-error mapping + stream chunking (all mocked).
- `test_research_stream.py` -- full research pipeline event order (fake LLM + fake search).
- `test_research_runs.py` -- run folders: every stage file written, no key on disk, an edited
  `plan.md` changes the searches, an edited `evidence.md` feeds the report, andon STOP + resume,
  GAP / unsourced labelling, chat tool's NOT-source-backed banner.
- `test_research_approval.py` -- review gates over HTTP: pause before search, approve, edit
  (diff logged, edited plan searched), reject, stale/second decisions, run-id escapes, bad
  edits, andon stop handed to the person then retried.
- `test_agent.py` -- the turn loop on the manual backend with a fake client (temp DB).
- `test_m3.py` -- skills load, calendar disabled-by-default, deterministic evals.
- `test_calendar_sync.py` -- providers disabled by default, dedup upsert, pull sync with a
  fake provider, local-only create (temp DB).
- `__init__.py`

## Run
`cd backend && pip install -r requirements-dev.txt && pytest`
(`asyncio_mode=auto` and `testpaths` are set in `../pyproject.toml`).

## Rules
- Never use a real key or hit the network. Patch `build_client` / `web_search` /
  calendar provider `is_enabled`+`list_events` at the import site the code uses.
- Isolate the DB with `APP_DB_PATH` -> `tmp_path` + `get_settings.cache_clear()`.
- Add a test with every new endpoint, provider, tool, or event type.

## Links
- Parent: `../CONTEXT.md` . App: `../app/CONTEXT.md`
