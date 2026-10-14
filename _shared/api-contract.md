# API Contract (single source of truth)

Both apps obey this. Change it here first, then update
`backend/app/models/research.py` and `frontend/lib/types.ts` together.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe -> `{"status":"ok","version":"..."}` |
| HEAD | `/health` | Same, for Cloud Run |
| GET | `/providers` | Static provider/model catalog (no key needed) |
| POST | `/research/stream` | Run research, stream SSE events |

## POST /research/stream -- request body
```json
{
  "query": "string, 3..2000 chars (required)",
  "provider": "openai | anthropic | kimi (required)",
  "model": "string, optional (defaults per provider, see _shared/providers.md)",
  "api_key": "string, >= 8 chars (required) -- the user's key, never stored",
  "max_subquestions": "int 1..8, optional (default 4)",
  "search": "bool, optional (default true) -- do live web search"
}
```

## Response: Server-Sent Events
`Content-Type: text/event-stream`. Each event is one line:
```
data: <json>\n\n
```
Every event JSON has this shape:
```json
{
  "type": "status|plan|sources|finding|token|report|done|error",
  "stage": "planning|researching|report|done|error|null",
  "message": "human-readable string or null",
  "data": { ... } | null,
  "research_id": "uuid string",
  "timestamp": "ISO-8601 string"
}
```

### Event types and their `data`
| type | stage | meaning | `data` payload |
|---|---|---|---|
| `status` | planning/researching/report | stage change / progress note | `{ "progress": 0.0..1.0 }` (optional) |
| `plan` | planning | the research plan | `{ "subquestions": ["...", ...] }` |
| `sources` | researching | sources found for a sub-question | `{ "index": int, "subquestion": str, "sources": [Source] }` |
| `finding` | researching | synthesized answer for a sub-question | `{ "index": int, "subquestion": str, "summary": str(md), "sources": [Source] }` |
| `token` | report | one streamed chunk of the final report | `{ "text": "..." }` |
| `report` | report | the complete final report | `{ "report": str(md), "sources": [Source] }` |
| `done` | done | research finished successfully | `null` |
| `error` | error | something failed; stream ends | `{ "code": "validation|auth|provider|search|internal|stop" }` (`stop` = no web sources found; see `research-workflow.md`) (message in `message`) |

`Source` object:
```json
{ "title": "string", "url": "string", "snippet": "string" }
```

## Ordering guarantee
`status(planning)` -> `plan` -> for each sub-question: `status(researching)` ->
`sources` -> `finding` -> `status(report)` -> many `token` -> `report` -> `done`.
On failure at any point: a single `error` event, then the stream closes.

## Auth model
- The `api_key` is the user's own provider key. It is used only to construct the
  provider client for this one request and is never written to disk, a database,
  or logs.
- Missing/short key -> `error` with code `validation` (HTTP request still 200; the
  error is carried in the stream) OR HTTP 422 if it fails Pydantic before streaming.
- Provider rejects the key (401/403) -> `error` with code `auth`.
