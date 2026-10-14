# backend/app/models -- request & event models

One job: define and validate the data crossing the API boundary. The event models
here are the server side of the SSE contracts.

## What's here
- `research.py` -- `Provider` enum; `ResearchRequest` (+ `review_plan`); `DecisionRequest`; `Source`; `ResearchEvent`
- `handoff.py` -- `HandoffRequest`, `HandoffDecision`, `HandoffEvent` + factory (shift handoff SSE).
  (+ `EventFactory`). Mirrors `_shared/api-contract.md`.
- `chat.py` -- `ChatRequest`; `TurnEvent` (+ `TurnEventFactory`) with the phase/
  event types. Mirrors `_shared/agent-turn-contract.md`.
- `__init__.py`

## Rules
- Validation lives in Pydantic field validators.
- `api_key` is `repr=False` so it never prints in logs or tracebacks.
- Change an event shape in the `_shared/` contract first, then here, then the
  frontend's `lib/types.ts` / `lib/chatTypes.ts`.

## Where to add things
- New request field -> the request model + a validator.
- New event type -> the `*EventType` Literal + a factory method + the contract + the frontend.

## Links
- Contracts: `../../../_shared/agent-turn-contract.md`, `../../../_shared/api-contract.md`
  . Parent: `../CONTEXT.md`
