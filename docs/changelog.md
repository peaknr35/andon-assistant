# Changelog

## 2026-10-14 -- Shift handoff workflow
- `workflows/shift_handoff/`: 01 notes -> 02 summary -> 03 issues & risks -> 04 next-shift brief,
  with stage contracts and plant references (`references/glossary.md`, `format.md`; snapshotted
  into each run).
- Cite or abstain: notes are kept verbatim and numbered; every bullet must cite `[L#]`.
  `check_citations()` flags uncited bullets and citations past the end of the notes; shown at
  the gate and kept in `state.json`. Thin notes (< 15 words) -> `STOP.md`, no model call.
- Gates at summary and issues: approve / edit (diff logged) / reject; the next stage reads the
  edited file. `GET /handoff/runs` + `/handoff/runs/{id}` list and reopen paused handoffs.
- `/handoff` page (nav: **Handoff**): notes form, streamed stage output, review panel with
  citation warnings and numbered notes, final brief with copy / download.
- `evals.stages check` has handoff rules; `judge` checks a brief against the notes; research
  and handoff decision endpoints refuse each other's runs.
- A decision whose next stage fails (bad key, provider down) restores the gate, as in research.
- Tests: `tests/test_handoff.py` (8).

## 2026-10-14 -- review fixes (PR #1, CodeRabbit)
- Research: a decision whose resumed stages fail (bad key, provider down) restores the same
  gate and reports the error, instead of leaving the run stuck on `stage_mismatch`.
- Memory review: non-UTF-8 candidate files are skipped; one failing hand edit no longer stops
  the sync; `_finish` records the decision before promoting; a disk error while proposing never
  breaks a turn; CLI `/approve` survives a candidate decided from the dashboard.
- Tests pick the newest run deterministically (not by `iterdir()` order); 6 regression tests.

## 2026-10-14 -- ICM workflows step 4: stage evals
- `backend/evals/stages.py`:
  - `check`: offline contract checks for every stage of a run folder. Plan has numbered
    sub-questions; evidence matches the plan (catches a plan edited after the search);
    findings and the report cite only URLs search returned; all-gaps -> STOP.md; stage
    order; no API key on disk; WARN when a file was edited after the next stage ran.
  - `replay`: copy a run, re-run from a stage on the recorded sources, check the copy,
    diff each stage file; writes `_replays/.../REPLAY.md`. The original is never modified.
- `runs.parse_evidence()` (inverse of `render_evidence`).
- Tests: `tests/test_stage_evals.py` (8).
- `judge`: AI judge -- splits report.md into claims and asks a model whether evidence.md
  supports each (supported / partial / unsupported / contradicted / no_claim). FAIL on any
  contradicted claim or > 20% unsupported (`--max-unsupported`); writes `_evals/`. `replay
  --judge` scores original vs replay with the same judge; `--provider/--model` pick the judge.
- Tests: `tests/test_stage_judge.py` (8), incl. replay + judge through the real OpenAI and
  Anthropic SDK clients with only the HTTP layer mocked.

## 2026-10-14 -- ICM workflows step 3: memory review (controlled promotion)
- `APP_MEMORY_REVIEW=1` (off by default): facts the consolidation gate picks are written as
  markdown candidates in `~/.assistant/memory/candidates/` (`APP_MEMORY_DIR`) instead of saved.
  Pending candidates are not recalled. The `remember` tool still saves directly.
- Decide from the dashboard memory panel (edit / approve / reject), the CLI (`/review`,
  `/approve N|all`, `/reject N`), or by setting `status: approved|rejected` in the file.
  Approved -> `facts` via `store.add_fact` (dedup) with the new `source=reviewed`.
  Rejected texts are never proposed again.
- `facts.md`: read-only markdown mirror of the facts table, regenerated every turn.
- API: `GET /memory/candidates`, `POST /memory/candidates/{id}`; `GET /memory` adds `review`
  and `pending_candidates`. Turn events: `memory` names `propose` and `promote`.
- Tests: `tests/test_memory_review.py` (9); conftest isolates `APP_MEMORY_DIR`.

## 2026-10-14 -- ICM workflows step 2: approval gates
- `/research/stream` takes `review_plan` (default false; the page sends true by default):
  the run pauses after 01_plan with `await_approval` (plan text included), then
  `done{status: paused}`.
- New `POST /research/runs/{run_id}/decision`: `approve` resumes; `edit` writes the new
  `plan.md` (must keep numbered lines), logs a diff in `state.json`, and searches the edit;
  `reject` writes `REJECTED.md`. Errors: `run_not_found`, `stage_mismatch`.
- With review on, an andon STOP pauses for the person (retry / reword / close) instead of erroring.
- Frontend: "Review plan first" toggle + `ApprovalPanel`; `streamDecision()`; reducer handles
  `await_approval` and paused/rejected `done`; a new plan clears stale findings. The key is read
  from the key manager at click time, never stored in run state.
- Tests: `tests/test_research_approval.py` (9). Compare mode does not gate.

## 2026-10-14 -- ICM workflows step 1: file-backed deep research
- `workflows/deep_research/{01_plan,02_search,03_report}/CONTEXT.md`: stage contracts.
- `services/runs.py`: per-run folders at `~/.assistant/runs/<run>/` (`APP_RUNS_DIR`) with
  `question.md`, `state.json`, `trace.jsonl`, and each stage's file. No API key on disk.
- `services/research.py`: stages read the previous stage's file (`plan.md`, `evidence.md`),
  so edits change what runs next; new `resume_research(run_dir, client, from_stage)`.
- Andon rule: with search on, a sub-question with no sources is a GAP (not guessed); no
  sources at all -> `02_search/STOP.md` + `error` code `stop`. Search-off runs are labelled
  NOT source-backed.
- Chat `deep_research` tool: unsourced answers get a NOT source-backed banner (added in
  code) and an escalate line. `/research` SSE events are unchanged.
- Tests: `tests/test_research_runs.py` (8 tests); conftest isolates `APP_RUNS_DIR`.

## 2026-10-12 -- demo prep + two-way calendar sync
- Rebrand to "Andon Assistant" (header, page title, config, README, CLAUDE.md).
- `deep_research` tool sped up ~60s -> ~12s (parallel web searches + one tight cited report);
  the full progressive pipeline + `/research` UI unchanged.
- Expanded the Anthropic model picker (Opus 4.7/4.8/5/5.5, Sonnet 5/5.5, Haiku 4.5/5.5, Fable 5.1)
  across `models.ts`, `/providers`, and `_shared/providers.md`.
- Agent is told today's date (relative dates resolve); the CLI auto-loads `backend/.env`.
- Handoff kit: `docs/GETTING-STARTED.md`, `setup.ps1` / `run.ps1`, `backend/.env.example`.
- `skills/five-whys-rca.md` + `backend/scripts/seed_demo.py` (demo data).
- Two-way calendar sync (OFF by default): `outlook_calendar.py` (Microsoft Graph) + extended
  `google_calendar.py` (token refresh + list) + `services/calendar_sync.py` (pull + dedup) +
  `events.outlook_id` + one-time auth scripts; `docs/CALENDAR-SYNC.md`; `tests/test_calendar_sync.py`.
- ICM freshness pass: refreshed the CONTEXT.md files, root CONTEXT/CLAUDE, `_shared` contracts
  (new `calendar-sync.md`), status, regenerated FILE-MAP; archived two stray root files.

## 2026-10-06 -- 0.2.0 (M3: skills, evals, Google calendar)
- `skills/`: user-editable markdown procedures surfaced to the agent (daily-standup,
  summarize-url), loaded by `agent/skills.py`.
- `evals/`: deterministic offline checks (17) + LLM-as-judge over the turn trace;
  `python -m evals.run [--deterministic|--judge]`.
- Optional Google Calendar sync for `calendar_create` (`APP_GOOGLE_CALENDAR=1`); the
  local SQLite calendar stays the source of truth, sync is best-effort.
- Tests: 28 passing.

## 2026-10-06 -- 0.2.0 (M2: chat dashboard)
- Frontend chat home with a live turn timeline (phase badges, tool-call cards,
  recalled/saved memory) streamed over SSE, plus a read-only memory panel.
- `lib/api.ts` generalized (streamResearch + streamChat + fetchMemory/Trace); new
  ChatContext persists chat across navigation. Research moved to `/research`.

## 2026-10-06 -- 0.2.0 (M1: local agent core)
- Evolved Deep Research Studio into a local-first personal agent; the research pipeline
  is now the `deep_research` tool.
- Visible turn loop with dual-track tool calling (PydanticAI + manual prompt-JSON); one
  local SQLite brain with recall + consolidation gate; tools (web_search, deep_research,
  remember/recall, local calendar, sandboxed file I/O); `POST /chat/stream` + a Rich TUI.

## 2026-10-06 -- docs: complete per-folder ICM
- A `CONTEXT.md` in every folder, `_templates/` starters, and a generated `FILE-MAP.md`.

## 2026-10-05 -- 0.1.0 (initial build)
- Deep Research Studio: FastAPI SSE research backend (OpenAI/Anthropic/Kimi, BYO key) +
  Next.js streaming UI (compare mode, key manager, Google Docs export). 19 tests.
