# docs/ -- human-facing documentation

One job: guides a person reads to run, demo, extend, or integrate the app. (Contracts the
AGENT follows live in `_shared/`; these are for humans.)

## What's here
- `GETTING-STARTED.md` -- clone -> setup -> run -> use -> reset -> troubleshoot (handoff guide).
- `DEMO-RUNBOOK.md` -- the script for presenting it live (prompts, talk track, fallbacks).
- `DEMO-SCENARIOS.md` -- a bigger prompt bank / scenarios for when you are unsure what to ask next.
- `CALENDAR-SYNC.md` -- step-by-step Google + Outlook OAuth setup, then the env vars to flip on.
- `api.md` -- the HTTP/SSE API (mirrors `_shared/api-contract.md` for integrators).
- `setup.md` -- run locally, environment variables, getting provider keys.
- `changelog.md` -- running log of notable changes (YYYY-MM-DD).

## Rules
- When the API shape changes in `_shared/api-contract.md`, update `api.md`.
- These are human docs; machine contracts stay in `_shared/` (one home per fact -- link,
  don't copy).

## Where to add things
A new human guide -> a new `*.md` here + a row above. A changed API/behaviour -> update the
matching `_shared/` contract first, then reflect it here.

## Links
- Contracts: `../_shared/` . Parent: `../CONTEXT.md`
