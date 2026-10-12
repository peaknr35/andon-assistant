# scripts/

**Identity.** One-off and maintenance scripts for the backend — run by hand, not imported by the app.

**Contents.**
| File | What it does |
|---|---|
| `seed_demo.py` | Loads realistic shop-floor fixes + PM events into the local memory DB for demos. Additive, safe to re-run. |
| `google_auth.py` | One-time Google OAuth: turns a downloaded `credentials.json` into `token.json` for calendar sync. |
| `outlook_auth.py` | One-time Microsoft (Outlook) device-code sign-in: writes `outlook_token.json` for calendar sync. |

**Rules.**
- Scripts import the app as a package, so run them with the backend on the path:
  `cd backend && PYTHONPATH=. .venv/Scripts/python.exe scripts/<name>.py`.
- Never commit secrets or a real API key. The auth scripts write token files that are gitignored
  (`token.json`, `outlook_token.json`, `credentials.json`). Scripts that touch memory go through
  `app.memory.store`, never raw SQL that deletes data.

**Where to add things.** New maintenance/demo/auth script → a new `*.py` here + a row in the table above.
