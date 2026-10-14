# Andon Assistant -- System Context

One sentence: a local-first personal assistant you reach two ways (terminal TUI or
browser dashboard) off one brain; it runs a visible turn loop, remembers useful things
in a single local SQLite file, and calls tools for real work -- web search, deep research
(the former Deep Research Studio, now a tool), a two-way calendar, and sandboxed files.

## The turn loop (full spec: `_shared/agent-turn-contract.md`)
```
message --> RECEIVE --> RECALL --> [ REASON --> ACT --> OBSERVE ]* --> REMEMBER --> REPLY
                        (memory)    (model)   (tool)   (result)        (consolidate)
```
Each phase emits a `TurnEvent` over SSE so the terminal and the dashboard show the agent
thinking. Tool-calling is dual-track (PydanticAI native + a manual prompt-JSON fallback)
behind one seam in `backend/app/agent/generate.py`. Deep Research is one of the tools.

## Two faces, one brain
```
terminal TUI  (python -m app.cli) ----\
                                        >--- backend/app/agent (turn loop) --- SQLite memory
browser dashboard (/chat/stream)  ----/           |                            (~/.assistant/state.db)
                                               tools: web_search, deep_research,
                                               calendar (local + 2-way Google/Outlook),
                                               file I/O (sandboxed), remember/recall
```
- The browser holds the user's API keys (localStorage) and sends one per request; the
  terminal reads a key from the local env / `.env`. The server never persists a key.
- State IS local: one SQLite file is the brain. Optional calendar sync mirrors events out
  to Google/Outlook and pulls them back in (off by default -- see `_shared/calendar-sync.md`).

## How the two apps agree
Both sides share the event schemas in `_shared/` -- change a contract in one place, then
update both apps: `_shared/api-contract.md` (research SSE) and
`_shared/agent-turn-contract.md` (chat TurnEvents).

## Layer map (ICM)
| Layer | File(s) | Question it answers |
|---|---|---|
| 0 | `CLAUDE.md` | Where am I? |
| 1 | this file | Where do I go? |
| 2 | `backend/CONTEXT.md`, `frontend/CONTEXT.md`, every `*/CONTEXT.md` | What do I do here? |
| 3 | `_config/`, `_shared/`, `planning/`, `docs/`, `ops/`, `workflows/*/NN_*/CONTEXT.md` | What rules apply? |
| 4 | `backend/app/`, `frontend/app/` + `components/`; run folders `~/.assistant/runs/<run>/` | What am I working with? |

## Status
Build status and what is done live in `_config/status.md`.
