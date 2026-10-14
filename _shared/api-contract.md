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
| POST | `/research/runs/{run_id}/decision` | Approve / edit / reject a paused run; streams the rest of it |

## POST /research/stream -- request body
```json
{
  "query": "string, 3..2000 chars (required)",
  "provider": "openai | anthropic | kimi (required)",
  "model": "string, optional (defaults per provider, see _shared/providers.md)",
  "api_key": "string, >= 8 chars (required) -- the user's key, never stored",
  "max_subquestions": "int 1..8, optional (default 4)",
  "search": "bool, optional (default true) -- do live web search",
  "review_plan": "bool, optional (default false) -- pause after 01_plan (and on an andon stop) for a person"
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
  "type": "status|plan|sources|finding|token|report|await_approval|done|error",
  "stage": "planning|researching|report|approval|done|error|null",
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
| `await_approval` | approval | the run paused; a person must decide (see Approval gates) | see below |
| `done` | done | the stream ends cleanly | `null` = complete; `{ "status": "paused" }` after `await_approval`; `{ "status": "rejected" }` after a reject |
| `error` | error | something failed; stream ends | `{ "code": "validation|auth|provider|search|internal|stop|run_not_found|stage_mismatch" }` (`stop` = no web sources found; see `research-workflow.md`) (message in `message`) |

`Source` object:
```json
{ "title": "string", "url": "string", "snippet": "string" }
```

## Approval gates
Started with `review_plan: true`, a run pauses after `01_plan`, and on an andon STOP at
`02_search` (no sources for any sub-question), instead of continuing or erroring:
`... plan -> await_approval -> done{status: paused}`, then the stream closes. Nothing
is held open while the person edits; the run's state lives in its run folder.

`await_approval.data`:
```json
{
  "run_id": "run folder name, e.g. 2026-10-14_120000_how-does-andon-work_ab12cd",
  "stage": "01_plan | 02_search (stop)",
  "reason": "review | stop",
  "artifact": "01_plan/plan.md (relative to the run folder)",
  "artifact_content": "the file's current text",
  "resume_from": "02_search", "next_stage": "02_search",
  "allowed_actions": ["approve", "edit", "reject"],
  "stop_reason": "STOP.md text when reason = stop, else null"
}
```

### POST /research/runs/{run_id}/decision -- request body
```json
{
  "stage": "must equal await_approval.data.stage",
  "action": "approve | edit | reject",
  "edited_content": "full new text of the artifact (required for edit)",
  "note": "optional, kept in state.json",
  "provider": "openai | anthropic | kimi", "model": "optional",
  "api_key": "the user's key, used for this request only, never stored"
}
```
- `approve` -> streams the run from `resume_from` (for a stop: retries the search).
- `edit` -> must still contain numbered sub-questions (else `error: validation`, nothing
  changed, still paused); writes the file, logs a unified diff in `state.json`
  `decisions`, emits `plan` with the edited list, then streams from `resume_from`.
- `reject` -> writes `REJECTED.md`, emits `done{status: rejected}`.
- The response is SSE in the same shape as `/research/stream`, with the same `research_id`.
- Errors: `run_not_found` (unknown id, or one outside the runs folder), `stage_mismatch`
  (the run is not waiting on that stage -- including a second decision on the same gate).

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
