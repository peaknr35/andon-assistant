# backend/evals -- test whether changes make the agent better

One job: two-tier evals -- deterministic checks (offline, no key) + LLM-as-judge
(needs a key) over the agent's turn trace.

## What's here
- `cases/*.jsonl` -- eval cases: `{id, message, expect_tool?}`.
- `deterministic.py` -- offline checks: parsing, tool registry, memory CRUD/recall, file sandbox.
- `judge.py` -- run a case through `run_turn` and score it (tool choice + LLM judge).
- `run.py` -- entrypoint.
- `stages.py` -- workflow run evals (deep research + shift handoff; `check` picks the rules by
  `state.json` `workflow`, `judge` checks a handoff brief against the numbered notes). `check` holds every stage of a run folder to its contract
  (plan has numbered lines; evidence matches the plan; findings and the report cite only URLs
  search returned; all-gaps -> STOP.md; stage order; no API key on disk). `replay` copies a run,
  re-runs it from a stage on the *recorded* search results, checks the copy, and diffs each
  stage's output (`REPLAY.md`). The original run is never touched. `judge` is the semantic
  check: it splits report.md into claims (in code) and asks a model whether evidence.md
  supports each one (supported / partial / unsupported / contradicted / no_claim). FAIL on any
  contradicted claim or > 20% unsupported (`--max-unsupported`). Results: `<runs>/_evals/`.

## Run
- `cd backend && python -m evals.run`                 (deterministic always; judge if `APP_API_KEY`)
- `cd backend && python -m evals.run --deterministic` (offline only)
- `APP_API_KEY=... python -m evals.run --judge`       (LLM-as-judge)
- `cd backend && python -m evals.stages check`        (every run in ~/.assistant/runs; offline)
- `cd backend && python -m evals.stages check <run_dir>`
- `cd backend && python -m evals.stages replay <run_dir> --from 03_report` (needs a key; add
  `--live-search` to search again; `--judge` to score original vs replay with the same judge).
  Output: `<runs>/_replays/<run>__<stage>_<time>/REPLAY.md` (+ `JUDGE.md` with `--judge`)
- `cd backend && python -m evals.stages judge latest` (or a run folder / run id; needs a key; `--provider/--model` to
  judge with a different model than wrote the report). ~1 model call per 25 claims.

## Rules
- Deterministic evals must pass offline (no key, no network); they gate changes.
- `evals.run` uses a temp DB + workspace; it never touches `~/.assistant`. `evals.stages`
  reads your run folders (read-only) and writes replays only under `_replays/`.
- Stage checks: FAIL = contract broken (gates changes); WARN = worth a look (e.g. a file
  edited after the next stage ran). Keep each check tied to a stage CONTEXT.md rule.
- The judge is a model, so it can be wrong: read the per-claim table before trusting a score,
  and prefer a different (or stronger) model than the one that wrote the report.

## Where to add a case
Add a line to `cases/basic.jsonl` (or a new `*.jsonl`): `{id, message, expect_tool?}`.

## Links
- Turn loop: `../app/agent/CONTEXT.md` . Parent: `../CONTEXT.md`
