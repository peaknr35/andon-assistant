# deep_research -- question in, cited report out

One job: route a research question through three stages, each handing off through a file
in the run folder.

## Stages
| # | Folder | Reads (run folder) | Writes (run folder) | Model calls |
|---|---|---|---|---|
| 01 | `01_plan/` | `question.md` | `01_plan/plan.md` | 1 |
| 02 | `02_search/` | `01_plan/plan.md` | `02_search/evidence.md`, `sources.json` (or `STOP.md`) | 1 per sourced sub-question |
| 03 | `03_report/` | `02_search/evidence.md` | `03_report/report.md` | 1 (streamed) |

## Run folder
`~/.assistant/runs/<YYYY-MM-DD_HHMMSS>_<slug>_<id>/` (or `$APP_RUNS_DIR/...`):
`question.md`, `state.json` (settings + per-stage status), `trace.jsonl` (one line per
event), and one subfolder per stage. The API key is never written to the run folder.

## Editing and resuming
Edit `plan.md` (or `evidence.md`), then resume from the next stage:

```python
from app.services.research import resume_research
async for event in resume_research(run_dir, client, "02_search"): ...
```

Resuming resets that stage and later ones to `pending` and removes any `STOP.md`.
With review on, the `/research` page does this for you: it pauses after 01_plan and
`POST /research/runs/{run_id}/decision` applies approve / edit / reject and resumes.

## Links
- Parent: `../CONTEXT.md` . Spec: `../../_shared/research-workflow.md`
