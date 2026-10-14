# Agent Turn Contract (single source of truth)

`POST /chat/stream` runs one turn and streams SSE TurnEvents. Mirrored by
`backend/app/models/chat.py` and `frontend/lib/chatTypes.ts` -- change here first.

## Request body
```json
{ "message": "str 1..8000 (required)",
  "provider": "openai | anthropic | kimi (required)",
  "model": "str, optional (provider default if omitted)",
  "api_key": "str >= 8 (required) -- never stored",
  "conversation_id": "int, optional (continue a thread)",
  "backend": "pydantic_ai | manual, optional (override default)" }
```

## Response: text/event-stream (`data: <json>\n\n`)
Every event:
```json
{ "type": "...", "phase": "...", "name": "...", "message": "...", "data": {...},
  "turn_id": "uuid", "timestamp": "ISO-8601" }
```

| type | phase | meaning | data |
|---|---|---|---|
| `phase` | receive/recall/reason/act/observe/remember/reply/done/error | stage marker | - |
| `memory` | recall / remember | memories read, saved, proposed for review, or promoted | `{items: [str]}` (name = `recall` / `save` / `propose` / `promote`) |
| `tool_call` | act | a tool is being called | `{args}` (name = tool) |
| `tool_result` | observe | a tool returned | `{args, result, ok}` (name = tool) |
| `token` | reply | streamed reply chunk (optional) | `{text}` |
| `final` | reply | the final answer | `message` = answer |
| `error` | error | failure; stream ends | `{code}` (message = text) |
| `done` | done | turn complete | `{conversation_id, turn_id}` |

## Order
`receive -> recall -> (reason -> act -> observe)* -> remember -> final -> done`.
On failure: a single `error` event, then the stream closes.

## Read-only endpoints (dashboard)
`GET /memory -> {facts, counts, review, pending_candidates}` . `GET /trace -> {tool_runs}`.

## Memory review (when `APP_MEMORY_REVIEW=1`)
- REMEMBER: facts the consolidation gate picks become candidates (`memory` event,
  name `propose`), not facts. RECALL first applies decisions made by editing candidate
  files (`memory` event, name `promote`, for any approved).
- `GET /memory/candidates -> {review, candidates: [{id, text, kind, status, proposed_at, reason, file}], folder}`
- `POST /memory/candidates/{id}` body `{action: approve|reject, text?}` -> `{id, status, fact_id?, text?}`;
  404 if it is not pending. See `memory-schema.md`.
