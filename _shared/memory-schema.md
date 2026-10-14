# Memory Schema (single source of truth)

One local SQLite file: `~/.assistant/state.db` (`APP_DB_PATH`). Mirrors
`backend/app/memory/schema.sql`. The three memory types map to Waku's
semantic / episodic / procedural.

| table | holds | type |
|---|---|---|
| `conversations` | thread metadata | episodic |
| `turns` | each user/assistant exchange (+ `trace` JSON) | episodic |
| `facts` | durable facts/preferences (`source`: auto \| explicit \| reviewed) | semantic |
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
- **Review (controlled promotion, `APP_MEMORY_REVIEW=1`, off by default):** consolidation
  *proposes* instead of saving. Each proposal is a markdown file a person can read and edit;
  only approved ones become facts (`source=reviewed`) and only facts are recalled.
  Rejected proposals are kept so the same text is never proposed again. The `remember`
  tool is an explicit request, so it still saves directly.

## Readable files (`~/.assistant/memory/`, `APP_MEMORY_DIR`)
| path | what | editable? |
|---|---|---|
| `facts.md` | mirror of the `facts` table, grouped by kind, with id + source + date | no -- regenerated after every turn and decision |
| `candidates/<id>.md` | a pending proposal: front matter (`id, kind, status, proposed_at, reason`) + the fact text | yes -- edit the text, set `status: approved` or `rejected` |
| `candidates/_done/` | approved (promoted) proposals | record |
| `candidates/_rejected/` | rejected proposals (blocks re-proposal) | record |

Decide from the dashboard memory panel, the CLI (`/review`, `/approve N|all`, `/reject N`),
or by editing the file (picked up at the start of the next turn or on `/review`).
SQLite stays the source of truth for facts; malformed candidate files are skipped, never fatal.

Change `schema.sql` and this file together.
