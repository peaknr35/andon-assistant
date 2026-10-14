# Andon Assistant — Getting Started (Handoff Guide)

A local-first troubleshooting assistant for the shop floor. Talk to it in a browser
dashboard (or a terminal); it **remembers past fixes**, **researches new faults with
sources**, keeps a **local calendar** and **writes standard-work sheets** — all running on
one laptop, with your own model key. Nothing is stored on anyone's server.

This guide takes a fresh machine to a running app in about 10 minutes.

---

## What you need first (prerequisites)

| Tool | Version | Get it |
|---|---|---|
| **Python** | 3.12+ | https://www.python.org/downloads/ (tick "Add to PATH") |
| **Node.js** | 18+ | https://nodejs.org/ (LTS) |
| **Git** | any | https://git-scm.com/downloads |
| **An API key** | — | one of: [Anthropic](https://console.anthropic.com/settings/keys), [OpenAI](https://platform.openai.com/api-keys), [Kimi](https://platform.moonshot.ai/console/api-keys) |

> **About the API key:** the app is "bring your own key." For **Anthropic**, the key needs
> **API credit** on the account — that is **separate** from any Claude.ai subscription. Add a
> few dollars at console.anthropic.com → Plans & Billing, or use an OpenAI/Kimi key with billing.

Check they're installed (any terminal):
```bash
python --version
node --version
git --version
```

---

## 1. Get the code
```bash
git clone https://github.com/peaknr35/troubleshooting-system.git
cd troubleshooting-system
```

---

## 2. One-time setup

### Windows (easiest)
From the project folder, in **PowerShell**:
```powershell
.\setup.ps1
```
That creates the Python environment, installs everything, makes a `backend\.env`, and seeds
sample data. If PowerShell blocks the script, run once:
`Set-ExecutionPolicy -Scope Process -Bypass` then `.\setup.ps1` again.

### Any OS (manual)
```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt     # Windows
# source .venv/bin/activate && pip install -r requirements.txt   # macOS/Linux
cp .env.example .env
cd ..
# frontend
cd frontend && npm install && cd ..
```

---

## 3. Add your API key
Open **`backend/.env`** and paste your key after `APP_API_KEY=`. Pick the matching provider/model:
```
APP_PROVIDER=anthropic
APP_MODEL=claude-sonnet-5-5
APP_API_KEY=sk-ant-your-key-here
```
(You can also skip this and just paste the key in the dashboard's **Keys** panel — the `.env`
is only needed for the terminal agent.)

---

## 4. Run it

### Windows (one command)
```powershell
.\run.ps1
```
Two windows open (backend + frontend) and your browser opens to the dashboard. To stop,
close those two windows.

### Any OS (manual — two terminals)
```bash
# terminal 1 - backend
cd backend && APP_CORS_ORIGINS="*" .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```
```bash
# terminal 2 - frontend
cd frontend && npm run dev
```
Then open **http://localhost:3000**.

---

## 5. Use it
1. Open **http://localhost:3000**.
2. Click **Keys** (top right), paste your API key, **Done**. The orange "no key" badge turns green.
3. Pick a **provider** and **model** (top left). Cheapest = `claude-haiku-5-5`; best balance = `claude-sonnet-5-5`.
4. Type a question and **Send**. Watch it recall, reason, call tools, and reply — with the live
   Memory panel on the right.

**Try these:**
- `Station 7 torque gun is throwing fault E-04 again — what do I check first?` → recalls a known fix
- `Remember this: <your fix>` → it keeps it for next time
- `Research how to clear a Fanuc SRVO-062 BZAL alarm, with sources` → cited web research
- `Schedule a PM check for next Monday at 7am` → local calendar
- `Write a standard-work sheet for <task> and save it as task.md` → writes to the safe workspace folder

**Terminal instead of browser** (uses `backend/.env`):
```bash
cd backend && .venv/Scripts/python.exe -m app.cli     # Windows
```

---

## 6. Reset / re-seed the demo memory
The memory lives in a single file at `~/.assistant/state.db`. To reset to the clean sample set:
```bash
# stop the backend first (Ctrl+C), then:
rm -f ~/.assistant/state.db ~/.assistant/state.db-wal ~/.assistant/state.db-shm
cd backend && PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_demo.py
```
Re-running `scripts/seed_demo.py` is always safe — it only adds the sample fixes/events if missing.

---

## 7. If something's off

| Symptom | Fix |
|---|---|
| Red "credit balance too low" | The key's account has no API credit. Add credit, or switch to a funded provider/key. |
| "no key" badge stays orange | Paste a key under **Keys**, or set `APP_API_KEY` in `backend/.env`. |
| Dashboard won't load | Make sure both terminals are running. Check http://localhost:8080/health returns `{"status":"ok"...}`. |
| Replies are slow | Switch the model to `claude-haiku-5-5` (fastest/cheapest). |
| Research returns no sources | Web search (DuckDuckGo) may be rate-limited. The `/research` page stops with a "no usable web sources" error instead of guessing (see `STOP.md` in the run folder under `~/.assistant/runs/`); the chat `deep_research` tool still answers but marks it **NOT source-backed**. Retry in a bit. |
| `npm run build` fails on an external drive | Known issue on some drives (readlink). Use `npm run dev` (what `run.ps1` uses), or build on the C: drive / via Docker. |
| PowerShell won't run the script | `Set-ExecutionPolicy -Scope Process -Bypass`, then run it again. |

---

## Where things live (for whoever extends it)
- **`CLAUDE.md`** — the map: what every folder is and where to add things.
- **`FILE-MAP.md`** — index of every file.
- **`backend/`** — the agent (FastAPI): turn loop, SQLite memory, tools, providers, CLI.
- **`frontend/`** — the dashboard (Next.js).
- **`skills/`** — plain-English procedures the agent follows (e.g. `five-whys-rca.md`).
- **`docs/DEMO-RUNBOOK.md`** — the script for presenting it live.

**The one rule:** API keys stay client-side/local — the server never stores a key. Memory is a
single local SQLite file; file tools are sandboxed to `~/.assistant/workspace` unless you set
`APP_FILE_UNRESTRICTED=1`.
