# backend/app/memory -- the single local brain (SQLite)

One job: persist and recall what is worth keeping, in one local SQLite file. No
server, no external DB. Mirrors ../../../_shared/memory-schema.md.

## What's here
- `schema.sql` -- the tables: conversations, turns, facts, skills, tool_runs, events
  (events carries `google_id` / `outlook_id` for calendar sync).
- `db.py` -- `connect()` (opens + inits the DB at ~/.assistant/state.db / `APP_DB_PATH`)
  plus an idempotent `_migrate()` that adds `outlook_id` to older DBs.
- `store.py` -- all operations: conversations/turns (episodic), facts + `recall()`
  (semantic), `add_tool_run`/`recent_tool_runs` (trace), calendar events +
  `upsert_event_by_external_id` (sync dedup), skills, `counts()`.
- `candidates.py` -- the readable side (`~/.assistant/memory/`, `APP_MEMORY_DIR`): `propose()`
  writes a candidate file, `decide()` approves (-> `facts`, source=reviewed) or rejects,
  `sync_hand_edits()` applies `status:` edits made in a text editor, `export_facts_md()`
  regenerates the read-only `facts.md` mirror. Active when `APP_MEMORY_REVIEW=1`.

## Rules
- Connections are opened per call; the agent loop wraps store calls in
  `asyncio.to_thread` so SQLite never blocks the event loop.
- `recall()` is simple keyword LIKE matching today; swap to FTS5/sqlite-vec later
  without changing callers.
- Facts are de-duplicated by text; cloud-pulled calendar events by `google_id` / `outlook_id`.
- SQLite is the source of truth for facts; markdown files are a view (`facts.md`) or a
  queue (`candidates/`). Promote through `store.add_fact`, never raw SQL.

## Where to add things
- A new table/column -> `schema.sql` (+ an `ALTER` in `db._migrate` for existing DBs)
  (+ mirror in `_shared/memory-schema.md`) + functions here.
- A new memory query -> a function in `store.py` (keep SQL in this folder only).

## Links
- Schema contract: `../../../_shared/memory-schema.md` . Parent: `../CONTEXT.md`
