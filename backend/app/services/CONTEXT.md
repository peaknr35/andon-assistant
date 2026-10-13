# backend/app/services -- business logic

One job: work kept out of the route handlers and tools -- the research pipeline, web
search, and the calendar pull-sync.

## What's here
- `research.py` -- `run_research(req, client)`: the async-generator pipeline
  (plan -> research loop -> streamed report) that yields `ResearchEvent`s. Holds the
  stage prompts and the sub-question JSON parser.
- `search.py` -- `web_search(query, max_results)`: DuckDuckGo via `ddgs` (no key);
  returns `Source[]`; degrades to `[]` on failure.
- `calendar_sync.py` -- `sync_once()`: pulls upcoming events from each enabled cloud
  provider (Google/Outlook) and upserts them into the local store, de-duplicated by the
  provider's event id. `any_enabled()` gates the periodic loop. Best-effort; never raises.
- `__init__.py`

## Reads / Writes
- Reads: the provider client (research); the calendar provider modules + `memory/store`.
- Writes: research yields a stream of events (no persistence); `calendar_sync` upserts
  into the `events` table.

## Rules
- Keep the control flow linear and readable (no framework) -- ICM invariant 9.
- `run_research`: catch provider/other errors at the top; emit exactly one `error` event.
- `calendar_sync`: provider modules swallow their own errors; the loop never dies on one.

## Where to add / change
- A research stage -> `run_research` (prompt + an `EventFactory` method), then update
  `_shared/research-workflow.md` + `_shared/api-contract.md`.
- Calendar pull behaviour -> `calendar_sync.py`, then `_shared/calendar-sync.md`.

## Links
- Workflow: `../../../_shared/research-workflow.md` . Calendar: `../../../_shared/calendar-sync.md`
- API contract: `../../../_shared/api-contract.md` . Parent: `../CONTEXT.md`
