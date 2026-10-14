# workflows -- staged pipelines the agent runs (the factory)

One job: hold the stage contracts for multi-step workflows. Numbered folders are the
stages; each stage's `CONTEXT.md` says what it reads, what it writes, and what it must not do.

## What's here
- `deep_research/` -- 01 plan -> 02 search -> 03 report (powers the `/research` page).
- `shift_handoff/` -- 01 notes -> 02 summary -> 03 issues -> 04 brief (the `/handoff` page);
  plant glossary + brief format in `shift_handoff/references/`.

## Factory vs product
These folders are the **factory**: committed, edited rarely. Each run's **product** goes
to its own run folder outside the repo (default `~/.assistant/runs/<run_id>/`, override with
`APP_RUNS_DIR`). Never write run output in here -- concurrent runs would overwrite each
other and private research would end up in git.

## Rules
- One stage = one job. If a stage's job needs "and", split it.
- A stage reads only the files its `Inputs` table lists, and hands off through a file.
  A person may edit that file before the next stage runs.
- Andon rule: a stage that cannot meet its output contract with evidence writes `STOP.md`
  and halts. It never guesses to fill the gap.
- Stage prompts currently live in code (`backend/app/services/research.py`,
  `handoff.py`) because the backend Docker image ships only `backend/app`. Keep the
  contract here and the prompt there in sync. Reference material (`references/`) is read
  at run time and snapshotted into each run; code falls back to defaults if it is missing.

## Where to add a new workflow
1. `workflows/<name>/CONTEXT.md` (routing: the stage list) + one `NN_<stage>/CONTEXT.md` each.
2. Run-folder helpers in `backend/app/services/runs.py`; the stage functions in a service.
3. Spec in `_shared/`, tests in `backend/tests/`.

## Links
- Parent: `../CONTEXT.md` . Runner: `../backend/app/services/research.py` + `runs.py`
- Spec: `../_shared/research-workflow.md`
