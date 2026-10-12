# Andon Assistant

A **local-first personal AI assistant** you can read end to end. Talk to it in a
terminal TUI or a browser dashboard off **one brain**; it remembers useful things in
a single local **SQLite** file and calls **tools** for real work. **Deep Research
Studio** -- plan -> web search -> cited report -- is now one of its tools
(`deep_research`). Bring your own model key (**OpenAI, Anthropic, Kimi K2**); nothing
is stored on a server.

Organized as an **ICM workspace**: every folder documents itself. Start at
[`CLAUDE.md`](CLAUDE.md) (routing), [`CONTEXT.md`](CONTEXT.md) (how it fits), and
[`FILE-MAP.md`](FILE-MAP.md) (every file).

> **New here, or handing this off?** See [`docs/GETTING-STARTED.md`](docs/GETTING-STARTED.md) for a 10-minute setup from a fresh machine. On Windows: run `setup.ps1` once, then `run.ps1` to launch both servers and open the dashboard.

## What it does
- **Visible turn loop:** RECEIVE -> RECALL -> (REASON -> ACT -> OBSERVE)* -> REMEMBER
  -> REPLY, streamed live in the terminal and the dashboard.
- **Dual-track tool calling:** PydanticAI (native function-calling, normalized across
  providers) by default, with a manual prompt-JSON backend as a transparent fallback.
- **One SQLite brain** (`~/.assistant/state.db`): facts, conversations, tool traces,
  a local calendar, skills -- with a recall gate before each turn and a consolidation
  gate that saves only what's worth keeping (plus explicit "remember that...").
- **Tools:** `web_search`, `deep_research`, `remember`/`recall`, `calendar_*` (local,
  optional Google sync), `file_read`/`file_write` (sandboxed to a workspace).
- **Skills:** drop a markdown procedure in [`skills/`](skills/) and the agent can follow it.
- **Built-in evals:** deterministic (offline) + LLM-as-judge, to test if a change helps.

## Quick start -- terminal
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows; macOS/Linux: . .venv/bin/activate
pip install -r requirements.txt
APP_PROVIDER=openai APP_API_KEY=sk-...  python -m app.cli
```
Type to chat; `/mem` shows memory; `/exit` quits. Your memory persists in
`~/.assistant/state.db`.

## Quick start -- dashboard (both faces, one backend)
```bash
docker compose up --build
```
- Dashboard: http://localhost:3000  (Assistant chat home; Research at `/research`)
- Backend:   http://localhost:8080  (`/health`, `/docs`)

Click **Keys**, paste a provider key, and chat -- watch the turn loop + memory panel live.

## Providers & keys
| Provider | Default model | Key |
|---|---|---|
| OpenAI | `gpt-5.1` | https://platform.openai.com/api-keys |
| Anthropic | `claude-opus-5-5` | https://console.anthropic.com/settings/keys |
| Kimi K2 | `kimi-k2-0905-preview` | https://platform.moonshot.ai |

Keys are per-request (dashboard) or from the local environment (terminal) -- never
stored on a server.

## Tests & evals
```bash
cd backend
pip install -r requirements-dev.txt
pytest                          # 28 tests (agent loop, tools, sandbox, providers, research)
python -m evals.run             # deterministic always; LLM-as-judge if APP_API_KEY is set
```

## Project layout
```
CLAUDE.md / CONTEXT.md / FILE-MAP.md   ICM entry, router, generated index
_shared/     contracts (agent-turn, memory-schema, tools, api, providers, research-workflow)
_config/ _templates/ planning/          factory settings, copy-to-create starters, specs/decisions
backend/     FastAPI app: agent/ memory/ tools/ providers/ services/ routes/ cli.py + evals/ + tests/
frontend/    Next.js app: chat dashboard + research UI
skills/      user-editable procedures
docs/ ops/   docs + deploy/runbooks
```

## Safety & local-first notes
- `file_write` is sandboxed to `APP_FILE_ROOT` (`~/.assistant/workspace`); set
  `APP_FILE_UNRESTRICTED=1` to widen (path-escape check still applies otherwise).
- Windows E: drive: local `next build` fails (a `readlink` quirk) -- build the frontend
  via Docker or a C: path. `npm run dev` (Turbopack) and `pytest` run fine on E:.

## References
Agent shape informed by [waku-agent](https://github.com/ShenSeanChen/waku-agent);
research engine from ShenSeanChen's launch-DeepResearch
[backend](https://github.com/ShenSeanChen/launch-DeepResearch-Backend) /
[frontend](https://github.com/ShenSeanChen/launch-DeepResearch-Frontend). Built as an ICM
(Van Clief & McDermott, arXiv:2603.16021).
