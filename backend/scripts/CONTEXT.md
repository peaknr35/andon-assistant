# scripts/

**Identity.** One-off and maintenance scripts for the backend — run by hand, not imported by the app.

**Contents.**
| File | What it does |
|---|---|
| `seed_demo.py` | Loads realistic shop-floor fixes + PM events into the local memory DB for demos. Additive, safe to re-run. |

**Rules.**
- Scripts import the app as a package, so run them with the backend on the path:
  `cd backend && PYTHONPATH=. .venv/Scripts/python.exe scripts/<name>.py`.
- Never commit secrets or a real API key. Scripts that touch memory go through `app.memory.store`, never raw SQL that deletes data.

**Where to add things.** New maintenance/demo script → a new `*.py` here + a row in the table above.
