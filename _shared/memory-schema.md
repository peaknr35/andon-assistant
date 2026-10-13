# Memory Schema (single source of truth)

One local SQLite file: `~/.assistant/state.db` (`APP_DB_PATH`). Mirrors
`backend/app/memory/schema.sql`. The three memory types map to Waku's
semantic / episodic / procedural.

| table | holds | type |
|---|---|---|
| `conversations` | thread metadata | episodic |
| `turns` | each user/assistant exchange (+ `trace` JSON) | episodic |
| `facts` | durable facts/preferences (`source`: auto \| explicit) | semantic |
| `skills` | reusable procedures | procedural |
| `tool_runs` | every tool invocation (for evals/debug) | trace |
| `events` | local calendar (+ `google_id` / `outlook_id` cloud ids) | - |

## Calendar sync ledger
The `events` table doubles as the sync ledger: `google_id` / `outlook_id` hold the cloud
event id when an event is mirrored out or pulled in. `store.upsert_event_by_external_id`
de-duplicates pulled events by those ids. `db.connect()` runs an idempotent migration that
adds `outlook_id` to older DBs. See `calendar-sync.md`.

## Gates (the "only save what's worth keeping" rule)
- **Retrieval:** `store.recall(query)` runs before the turn (keyword match today;
  swap to FTS5/sqlite-vec later without changing callers).
- **Consolidation:** after the reply, the model extracts facts worth keeping
  (`source=auto`); the user can force one with the `remember` tool (`source=explicit`).

Change `schema.sql` and this file together.
