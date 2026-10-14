# Shift Handoff Workflow (contract)

End-of-shift notes in, reviewed next-shift brief out. Implemented in
`backend/app/services/handoff.py`; stage contracts in `workflows/shift_handoff/NN_*/CONTEXT.md`;
UI at `/handoff` (`frontend/components/HandoffInterface.tsx`). Same pattern as
`research-workflow.md`: file-backed stages, human gates, andon stop.

## Stages
| # | Reads | Writes | Gate |
|---|---|---|---|
| 01_notes | the pasted notes | `01_notes/notes.md` (verbatim; line N = `[LN]`) | STOP if < 15 words |
| 02_summary | `notes.md` (as `L<n>: text`) + `references/glossary.md` | `02_summary/summary.md` | required |
| 03_issues | `summary.md` | `03_issues/issues.md` | required |
| 04_brief | `summary.md` + `issues.md` + `references/format.md` | `04_brief/brief.md` | final |

**Cite or abstain.** Every bullet / table row ends with `[L#]` (`[L3, L7]`, `[L2-L4]`).
Uncertain items go under "Unclear -- ask the outgoing shift". After each model stage,
`check_citations()` lists bullets with no citation or a citation past the end of the notes;
they are stored in `state.json` and shown at the gate. Approving with problems is the
supervisor's call; `evals.stages check` still FAILs a citation to a line that does not exist.

## Run folder
`~/.assistant/runs/<date>_<line>-<shift>_<id>/`: `state.json` (`workflow: shift_handoff`,
line, shift, supervisor, provider, model, `stage_status`, `gates`, `awaiting`, `decisions`
with diffs, `citation_warnings`), `trace.jsonl`, `references/` (snapshot of the factory
references), stage folders, `REJECTED.md` if rejected. Never the API key.

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/handoff/stream` | start: `{notes, line, shift, supervisor?, provider, model?, api_key}` -> SSE |
| POST | `/handoff/runs/{run_id}/decision` | `{stage, action: approve\|edit\|reject, edited_content?, note?, provider, model?, api_key}` -> SSE |
| GET | `/handoff/runs` | `{runs: [{run_id, line, shift, supervisor, created_at, status}]}` (newest first) |
| GET | `/handoff/runs/{run_id}` | state + stage files + `awaiting` (to resume a paused handoff) |

SSE events: `{type, stage, message, data, run_id, timestamp}` with `type` one of
`status`, `token` (`{text}`, the stage output streaming), `stage_output`
(`{artifact, content, citation_warnings}`), `await_approval` (`{run_id, stage, next_stage,
artifact, artifact_content, citation_warnings, notes, allowed_actions}`), `done`
(`{status: complete|paused|rejected, brief?}`), `error` (`{code}`: `stop | run_not_found |
stage_mismatch | validation | auth | provider | internal`).

Order: `status(01) -> status(02) -> token* -> stage_output -> await_approval -> done(paused)`;
decision -> `status(next) -> token* -> stage_output -> (await_approval -> done(paused) | done(complete))`.

## Evals
- `python -m evals.stages check` -- handoff runs get their own checks: notes kept, stage
  order, every artifact cites only existing note lines (FAIL), uncited bullets (WARN),
  a file edited after the next stage ran (WARN), summary sections, brief leads with safety.
- `python -m evals.stages judge <run>` -- judges `brief.md` claims against the numbered notes.
- `replay` is research-only for now.
