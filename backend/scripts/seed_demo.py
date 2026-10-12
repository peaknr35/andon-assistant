"""Seed the local memory with realistic shop-floor history for the demo.

Additive and safe to re-run: facts dedupe by text, events dedupe by title.
Run from the backend folder:

    cd backend
    PYTHONPATH=. .venv/Scripts/python.exe scripts/seed_demo.py              # Git Bash
    $env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\seed_demo.py    # PowerShell

To start completely fresh, delete the DB first (~/.assistant/state.db) then re-run.
"""
from __future__ import annotations

import os

os.environ.setdefault("APP_API_KEY", "x")  # store import is key-agnostic

from app.memory import store  # noqa: E402

FACTS = [
    ("Station 7 torque gun fault code E-04 is almost always the air regulator drifting "
     "below 5.5 bar. Fix: reset the regulator to 6.2 bar, bleed the supply line, then run "
     "one calibration cycle before restarting. Part: regulator RG-14 if it will not hold.", "fix"),
    ("Line 2 conveyor jams at the transfer point are usually a worn guide-roller bearing "
     "(part RB-220). Replace it on a 90-day PM cycle to stop the jams recurring.", "fix"),
    ("Paint booth humidity alarm above 65% RH is normally a clogged dehumidifier drain line. "
     "Clear the drain, confirm the trap is sealed, then reset the alarm.", "fix"),
    ("Station 12 stamping press should not run above 55 strokes/min with the current die set; "
     "above that, slug pulling drives the scrap rate up sharply.", "fix"),
    ("Team preference: give answers as short numbered steps, most-likely cause first, and "
     "include the part number whenever a replacement is involved.", "preference"),
]

EVENTS = [
    ("PM check - Station 7 torque gun regulator", "2026-10-13T07:00:00", "2026-10-13T07:30:00",
     "Verify regulator holds 6.2 bar; recal after fault E-04 last week."),
    ("Replace Line 2 guide-roller bearing (RB-220)", "2026-10-20T06:30:00", "2026-10-20T07:15:00",
     "90-day PM cycle to prevent transfer-point jams."),
]


def main() -> None:
    for text, kind in FACTS:
        store.add_fact(text, kind=kind, source="team-log")
    existing = {e["title"] for e in store.list_events()}
    for title, start, end, notes in EVENTS:
        if title not in existing:
            store.add_event(title, start, end, notes=notes)
    print("Seeded. counts:", store.counts())


if __name__ == "__main__":
    main()
