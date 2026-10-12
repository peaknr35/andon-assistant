# Andon Assistant (with Deep Research Studio inside)

A local-first personal AI assistant: talk to it in the terminal or a browser
dashboard off one brain; it remembers useful things in a single local SQLite file
and calls tools for practical work. Deep Research Studio -- plan -> web search ->
cited report -- is now one of its tools (`deep_research`). Bring your own model key
(OpenAI, Anthropic, Kimi K2); nothing is stored on a server.

## Where things live
| Path | What it holds |
|---|---|
| `FILE-MAP.md` | Generated index of every file (refresh: `ops/scripts/build-file-map.sh`) |
| `_config/` | Factory settings: project, tech stack, conventions, build status |
| `_shared/` | Contracts: agent-turn, memory-schema, tools, api, providers, research-workflow |
| `_templates/` | Copy-to-create starters: new tool/provider/endpoint/component/skill/decision |
| `planning/` | Specs, architecture, decision records |
| `backend/` | FastAPI app: agent loop, memory (SQLite), tools, providers, research, CLI, tests |
| `frontend/` | Next.js app: chat dashboard (M2) + the research UI |
| `skills/` | (M3) user-editable procedures the agent can follow |
| `docs/` | API docs, setup guide, changelog |
| `ops/` | Deploy scripts and runbooks |

## Route by intent
| Task | Go to |
|---|---|
| Get oriented / find any file | `FILE-MAP.md` |
| Understand the system | `CONTEXT.md` |
| Work inside any folder | that folder's `CONTEXT.md` |
| Change the chat turn / phases | `_shared/agent-turn-contract.md` -> `backend/app/agent/` |
| Add/adjust memory | `_shared/memory-schema.md` -> `backend/app/memory/` |
| Add a tool | `_templates/new-tool.md` -> `backend/app/tools/` |
| Add/adjust a provider | `_shared/providers.md` -> `backend/app/providers/` + `frontend/lib/models.ts` |
| Change the research steps | `_shared/research-workflow.md` -> `backend/app/services/research.py` |
| Work on the UI | `frontend/CONTEXT.md` |
| Deploy or run locally | `ops/CONTEXT.md` |
| Check what is done | `_config/status.md` |

## Tech stack (full detail in `_config/tech-stack.md`)
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLite (stdlib), PydanticAI + a manual
  prompt-JSON backend (dual-track tool calling), Rich (terminal TUI).
- Frontend: Next.js 15 (App Router), TypeScript, Tailwind.
- LLM SDKs: openai (OpenAI + Kimi via base_url), anthropic.

## Commands
| Action | Command |
|---|---|
| Terminal agent | `cd backend && APP_API_KEY=... python -m app.cli` |
| API server | `cd backend && uvicorn app.main:app --reload --port 8080` |
| Backend tests | `cd backend && pytest` |
| Frontend dev | `cd frontend && npm run dev` |
| Run both (Docker) | `docker compose up --build` |
| Refresh file index | `bash ops/scripts/build-file-map.sh` |

## The one rule
Secrets stay client-side / local -- the server never persists an API key. Memory is a
single local SQLite file (`~/.assistant/state.db`); file tools are sandboxed to a
workspace dir unless `APP_FILE_UNRESTRICTED=1`.

## Conventions
- Every folder has a `CONTEXT.md` (identity, contents, rules, where to add things);
  the root keeps the only `CLAUDE.md`.
- Folders `kebab-case/`; Python `snake_case.py`; React `PascalCase.tsx`; decisions
  `YYYY-MM-DD_title.md`.
