# shift_handoff -- end-of-shift notes in, next-shift brief out

One job: turn a supervisor's raw end-of-shift notes into a reviewed, cited brief for the
incoming shift. Every stage hands off through a file a person can edit.

## Stages
| # | Folder | Reads (run folder) | Writes (run folder) | Model | Gate |
|---|---|---|---|---|---|
| 01 | `01_notes/` | the pasted notes | `01_notes/notes.md` (verbatim; lines numbered L1..Ln) | none | STOP if too thin |
| 02 | `02_summary/` | `notes.md` + `references/glossary.md` | `02_summary/summary.md` | 1 (streamed) | required |
| 03 | `03_issues/` | `summary.md` | `03_issues/issues.md` | 1 (streamed) | required |
| 04 | `04_brief/` | `summary.md` + `issues.md` + `references/format.md` | `04_brief/brief.md` | 1 (streamed) | final |

## The rule that matters: cite or abstain
Every bullet traces back to a numbered note line (`[L4]`, `[L4, L9]`). If the model cannot
point to a line, the item goes under "Unclear -- ask the outgoing shift"; it is never
filled in. Code checks every citation after each stage and shows the supervisor any
bullet with no citation or a citation to a line that does not exist, before they approve.

## Run folder
`~/.assistant/runs/<date>_<line>-<shift>_<id>/` (or `$APP_RUNS_DIR`): `state.json`
(`workflow: shift_handoff`, line, shift, supervisor, per-stage status, decisions log with
diffs), `trace.jsonl`, `references/` (a snapshot of the glossary and format used), and
one folder per stage. The API key is never written here.

## Factory (configure once)
`references/glossary.md` (your plant's terms) and `references/format.md` (how your brief
should look). Edit them in the repo; every new run snapshots them.

## Run it
Dashboard: **Handoff** tab. API: `POST /handoff/stream`, then
`POST /handoff/runs/{run_id}/decision` at each gate (see `_shared/shift-handoff.md`).
Check runs: `cd backend && python -m evals.stages check`.

## Links
- Parent: `../CONTEXT.md` . Spec: `../../_shared/shift-handoff.md`
- Runner: `../../backend/app/services/handoff.py`
