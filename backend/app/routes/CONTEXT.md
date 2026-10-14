# backend/app/routes -- HTTP / SSE endpoints

One job: thin FastAPI handlers that validate input and delegate to the agent/services.

## What's here
- `health.py` -- `GET/HEAD /health` + `GET /providers` (the model catalog).
- `research.py` -- `POST /research/stream`: the research pipeline as SSE;
  `POST /research/runs/{run_id}/decision`: approve / edit / reject a paused run (SSE).
- `handoff.py` -- `POST /handoff/stream`, `POST /handoff/runs/{run_id}/decision` (SSE),
  `GET /handoff/runs`, `GET /handoff/runs/{run_id}`.
- `chat.py` -- `POST /chat/stream` (the agent turn, SSE) + `GET /memory` and `GET /trace`
  for the dashboard + the memory review step: `GET /memory/candidates`,
  `POST /memory/candidates/{id}` (approve / reject).
- `__init__.py`

## Reads / Writes
- Reads: `../models/` (requests), `../agent/loop.run_turn`, `../providers/base`,
  `../services/research`, `../memory/store`.
- Writes: HTTP responses (JSON or SSE). No persistence here (memory writes happen
  inside the turn loop).

## Rules
- Handlers stay thin -- turn logic in `../agent/`, research logic in `../services/`.
- Pydantic rejects bad input as 422 before streaming; in-stream failures become a
  single SSE `error` event, never a 500 mid-stream.
- A new router module must be registered in `../main.py` (`include_router`).

## Where to add an endpoint
See `../../../_templates/new-endpoint.md`.

## Links
- Contracts: `../../../_shared/agent-turn-contract.md`, `../../../_shared/api-contract.md`
  . Parent: `../CONTEXT.md`
