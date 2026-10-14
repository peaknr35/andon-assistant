# backend/app/agent -- the turn loop (the brain)

One job: run one conversational turn as a visible sequence of phases, calling tools
and memory. Pure functions we own; the model mechanics live behind `generate.py`.

## What's here
- `loop.py` -- `run_turn()`: RECEIVE -> RECALL -> [REASON -> ACT -> OBSERVE]* ->
  REMEMBER -> REPLY. Yields `TurnEvent`s; wraps the middle with memory read/write.
- `generate.py` -- the dual-track engine: `manual_middle` (prompt-JSON, transparent),
  `pydantic_middle` (PydanticAI native function-calling), `run_middle` (selector +
  manual fallback), and `consolidate` (the memory-write gate).
- `prompts.py` -- identity + memory system prompt, the manual tool protocol, the
  consolidation prompt.
- `skills.py` -- (M3) load procedures from the repo-root `skills/` folder.

## Reads / Writes
- Reads: `../providers` (model), `../tools` (registry), `../memory/store` (recall/history).
- Writes: memory (turns, facts, tool_runs) via `../memory/store`; with memory review on,
  proposals via `../memory/candidates` instead of facts. Yields events only.

## Rules
- The loop stays legible top-to-bottom; new control flow goes here, not in a tool.
- Any new event type must be in `../models/chat.py` + `_shared/agent-turn-contract.md`.
- Backend default is `APP_AGENT_BACKEND` (pydantic_ai); it falls back to manual if
  pydantic_ai is missing. Tests use the manual backend with a fake client.

## Where to add things
- A new phase/event -> `models/chat.py` factory + emit it in `loop.py` + the contract.
- A new tool-calling backend -> add a `*_middle` in `generate.py` + a branch in `run_middle`.

## Links
- Turn contract: `../../../_shared/agent-turn-contract.md` . Tools: `../tools/CONTEXT.md`
  . Memory: `../memory/CONTEXT.md` . Parent: `../CONTEXT.md`
