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
| `run.ps1` / `setup.ps1` | One-command Windows launch / first-time setup |
| `_config/` | Factory settings: project, tech stack, conventions, build status |
| `_shared/` | Contracts: agent-turn, memory-schema, tools, api, providers, research-workflow, calendar-sync |
| `_templates/` | Copy-to-create starters: new tool/provider/endpoint/component/skill/decision |
| `planning/` | Specs, architecture, decision records |
| `backend/` | FastAPI app: agent loop, memory (SQLite), tools, providers, services, CLI, scripts, tests |
| `frontend/` | Next.js app: chat dashboard (M2) + the research UI |
| `workflows/` | Stage contracts for staged pipelines (`deep_research/01_plan -> 02_search -> 03_report`); run output goes to `~/.assistant/runs/` |
| `skills/` | (M3) user-editable procedures the agent can follow |
| `docs/` | Setup guide, demo runbook, calendar-sync setup, API docs, changelog |
| `ops/` | Deploy scripts and runbooks |
| `_archive/` | Gitignored holding pen for superseded / one-off artifacts (not read in normal work) |

## Route by intent
| Task | Go to |
|---|---|
| Get oriented / find any file | `FILE-MAP.md` |
| Understand the system | `CONTEXT.md` |
| Work inside any folder | that folder's `CONTEXT.md` |
| Run locally / hand it off | `docs/GETTING-STARTED.md` (`setup.ps1` then `run.ps1`) |
| Change the chat turn / phases | `_shared/agent-turn-contract.md` -> `backend/app/agent/` |
| Add/adjust memory | `_shared/memory-schema.md` -> `backend/app/memory/` |
| Add a tool | `_templates/new-tool.md` -> `backend/app/tools/` |
| Add/adjust a provider | `_shared/providers.md` -> `backend/app/providers/` + `frontend/lib/models.ts` |
| Change calendar sync | `_shared/calendar-sync.md` -> `backend/app/tools/{google,outlook}_calendar.py` + `services/calendar_sync.py` |
| Change the research steps | `_shared/research-workflow.md` + `workflows/deep_research/` -> `backend/app/services/research.py` + `runs.py` |
| Work on the UI | `frontend/CONTEXT.md` |
| Deploy locally | `ops/CONTEXT.md` |
| Check what is done | `_config/status.md` |

## Tech stack (full detail in `_config/tech-stack.md`)
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLite (stdlib), PydanticAI + a manual
  prompt-JSON backend (dual-track tool calling), Rich (terminal TUI).
- Frontend: Next.js 15 (App Router), TypeScript, Tailwind.
- LLM SDKs: openai (OpenAI + Kimi via base_url), anthropic.

## Commands
| Action | Command |
|---|---|
| First-time setup / run (Windows) | `./setup.ps1` then `./run.ps1` |
| Terminal agent | `cd backend && python -m app.cli` (reads `backend/.env`) |
| API server | `cd backend && uvicorn app.main:app --reload --port 8080` |
| Backend tests | `cd backend && pytest` |
| Frontend dev | `cd frontend && npm run dev` |
| Run both (Docker) | `docker compose up --build` |
| Refresh file index | `bash ops/scripts/build-file-map.sh` |
| Check research runs / judge / replay | `cd backend && python -m evals.stages check` / `... judge <run>` / `... replay <run> --from 03_report --judge` |

## The one rule
Secrets stay client-side / local -- the server never persists an API key. Memory is a
single local SQLite file (`~/.assistant/state.db`); file tools are sandboxed to a
workspace dir unless `APP_FILE_UNRESTRICTED=1`.

## Conventions
- Every folder has a `CONTEXT.md` (identity, contents, rules, where to add things);
  the root keeps the only `CLAUDE.md`.
- Folders `kebab-case/`; Python `snake_case.py`; React `PascalCase.tsx`; decisions
  `YYYY-MM-DD_title.md`.
