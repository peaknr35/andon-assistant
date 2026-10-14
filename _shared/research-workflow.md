# Research Workflow

The deep-research pipeline, implemented in `backend/app/services/research.py` as async
generators that yield SSE events. Three stages, **file-backed**: each stage reads the
previous stage's file from the run folder and writes its own, so a person can edit a
stage output and resume from the next stage. Stage contracts (inputs, tools, output,
must-not) live in `workflows/deep_research/NN_<stage>/CONTEXT.md`.

## Run folder (`backend/app/services/runs.py`)
`~/.assistant/runs/<YYYY-MM-DD_HHMMSS>_<slug>_<id>/` (override: `APP_RUNS_DIR`):
`question.md`, `state.json` (query, search on/off, max_subquestions, provider, model,
per-stage status `pending|done|stopped`), `trace.jsonl` (every non-token event), and
`01_plan/`, `02_search/`, `03_report/`, plus `REJECTED.md` if a person rejected the run.
`state.json` also holds `gates`, `awaiting` and the `decisions` log. **The API key is never written here.**

## 01 PLAN  (stage: planning)
- Input: `query` from `state.json`.
- The LLM decomposes the question into at most `max_subquestions` sub-questions,
  returned as strict JSON. Robust parse; on failure, fall back to the question itself.
- Writes `01_plan/plan.md`: `Question: ...` + numbered lines. Stage 02 searches exactly
  the numbered lines (`1. ...` or `1) ...`).
- Emits: `status(planning)`, then `plan` with the sub-question list.

## 02 SEARCH  (stage: researching)  -- loop, one pass per sub-question
Reads the sub-questions from `01_plan/plan.md` on disk. For each sub-question `i`:
1. `status(researching)` with progress = i / N.
2. If `search` is on: web search (`app/services/search.py`, DuckDuckGo, top
   `search_max_results`); emits `sources`.
   - Sources found -> the LLM answers **only from those sources**, citing URLs.
   - No sources -> the block is a `GAP`; no LLM call, nothing filled in.
3. If `search` is off (user's choice): the LLM answers from general knowledge and the
   block is labelled `unsourced (search off; NOT source-backed)`.
4. Emits `finding`.
Writes `02_search/evidence.md` (one `## N.` block per sub-question with status, finding,
source links) and `02_search/sources.json` (raw results).

**Andon STOP:** if search is on and no sub-question found any source, write
`02_search/STOP.md`, mark the stage `stopped`, and emit `error` with code `stop`.
Stage 03 does not run; nothing is guessed.

## 03 REPORT  (stage: report)
- Reads `02_search/evidence.md` from disk (possibly edited) + `query`.
- `status(report)`; the LLM writes a structured markdown report, **streamed** as
  `token` events. GAPs are stated as unanswered; unsourced runs say so up top.
- Writes `03_report/report.md`; emits `report` with the full text + the de-duplicated
  sources from `sources.json`, then `done`.

## Review gates (human in the loop)
With `review_plan: true` the run's `state.json` lists `gates: ["01_plan"]`:
- After `01_plan`, the runner records `awaiting` in `state.json`, emits
  `await_approval` (the plan text included) and `done{status: paused}`, and stops.
- On an andon STOP with gates on, it pauses the same way (`reason: stop`) instead of
  erroring, so the person can retry, reword the plan, or close the run.
- `decide(run_id, req, client)` (`POST /research/runs/{run_id}/decision`) checks the
  run is waiting on that stage, applies approve / edit / reject, appends to
  `state.json` `decisions` (action, note, time, diff for edits), clears `awaiting`,
  and resumes. Without gates, runs behave exactly as before.

## Resume
`resume_research(run_dir, client, from_stage)` re-runs `from_stage` and later stages
from the files on disk (resets their status to `pending`, removes `STOP.md`). The
decision endpoint calls it; it can also be called directly for a run edited by hand.

## Errors
Any exception is caught at the top of the stage runner and emitted as a single
`error` event (code: `auth|provider|search|internal`, or `stop` for the andon stop)
before the stream closes. The process never crashes the request.

## Why no LangGraph
Plain async generators. The sequencing is linear and human-legible, which matches ICM
invariant 9 (the control flow is visible in one file); the filesystem holds the state
between stages. Add a framework only if branching/concurrency is needed later.
