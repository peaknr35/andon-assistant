"""Stage evals for workflow run folders: check each stage, and replay a run.

    python -m evals.stages check [RUN_DIR ...]      # offline; default: every run in the runs folder
    python -m evals.stages replay RUN_DIR --from 03_report [--live-search]

``check`` holds each stage's output to its contract in workflows/deep_research/NN_*/CONTEXT.md.
FAIL = the contract is broken; WARN = worth a look (e.g. a file edited after the next stage ran).

``replay`` copies a run, re-runs it from a stage with the same recorded search results
(unless ``--live-search``), checks the copy, and diffs each stage's output against the
original -- so a prompt or model change can be judged on the same evidence. Needs
APP_API_KEY (+ APP_PROVIDER / APP_MODEL). The original run is never modified.
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.services import runs
from app.services.runs import Run

_URL = re.compile(r"https?://[^\s)\]>\"'`]+")
_SECRET = re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,})")


@dataclass
class Check:
    stage: str
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str = ""


def _urls(text: str) -> set[str]:
    return {u.rstrip(".,;:").rstrip("/") for u in _URL.findall(text or "")}


def _recorded_sources(run: Run) -> dict[str, list[dict]]:
    if not run.path(runs.SOURCES_FILE).exists():
        return {}
    return {b["subquestion"]: b.get("sources", []) for b in json.loads(run.read(runs.SOURCES_FILE))}


def check_run(run_dir: str | Path) -> list[Check]:
    run = runs.open_run(run_dir)
    st = run.state()
    status = st.get("stage_status", {})
    out: list[Check] = []

    def add(stage: str, name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        out.append(Check(stage, name, "PASS" if ok else ("WARN" if warn else "FAIL"), "" if ok else detail))

    def exists(rel: str) -> bool:
        return run.path(rel).exists()

    # --- run-level ---
    leaks = []
    for f in run.dir.rglob("*"):
        if f.is_file() and _SECRET.search(f.read_text(encoding="utf-8", errors="replace")):
            leaks.append(str(f.relative_to(run.dir)))
    add("run", "no API key on disk", not leaks and "api_key" not in st, f"key-like text in: {leaks}")
    order = list(runs.STAGES)
    for i, s in enumerate(order[1:], 1):
        if status.get(s) in ("done", "stopped"):
            add("run", f"{s} ran after {order[i - 1]}", status.get(order[i - 1]) == "done",
                f"{s} is {status.get(s)} but {order[i - 1]} is {status.get(order[i - 1])}")

    # --- 01_plan ---
    plan: list[str] = []
    if status.get("01_plan") in ("done", "rejected"):
        add("01_plan", "plan.md exists", exists(runs.PLAN_FILE), "missing")
        if exists(runs.PLAN_FILE):
            plan = runs.parse_plan(run.read(runs.PLAN_FILE))
            add("01_plan", "has numbered sub-questions", bool(plan), "no numbered lines")
            dupes = sorted({q for q in plan if plan.count(q) > 1})
            add("01_plan", "no duplicate sub-questions", not dupes, f"{dupes}", warn=True)
            limit = st.get("max_subquestions", 8)
            add("01_plan", f"at most {limit} sub-questions (unless a person added more)",
                len(plan) <= limit or any(d.get("action") == "edit" for d in st.get("decisions", [])),
                f"{len(plan)} sub-questions", warn=True)

    # --- 02_search ---
    blocks: list[dict] = []
    recorded = _recorded_sources(run)
    found = {u for srcs in recorded.values() for u in _urls(" ".join(s.get("url", "") for s in srcs))}
    if status.get("02_search") in ("done", "stopped", "rejected") and exists(runs.EVIDENCE_FILE):
        blocks = runs.parse_evidence(run.read(runs.EVIDENCE_FILE))
        got = [b["subquestion"] for b in blocks]
        add("02_search", "evidence matches the plan (same sub-questions, same order)", got == plan,
            "plan.md was changed after the search ran; resume from 02_search. "
            f"plan={plan} evidence={got}")
        for i, b in enumerate(blocks, 1):
            tag = f"#{i}"
            add("02_search", f"{tag} has a status", bool(b["status"]), "no **Status:** line")
            if b["status"].startswith("sourced"):
                add("02_search", f"{tag} sourced block lists its sources", bool(b["source_urls"]), "no source links")
                invented = _urls(b["finding"]) - _urls(" ".join(b["source_urls"])) - found
                add("02_search", f"{tag} cites only URLs that search returned", not invented,
                    f"not found by search: {sorted(invented)}")
            elif b["status"].startswith("GAP"):
                add("02_search", f"{tag} gap is not filled in", not _urls(b["finding"]),
                    "a GAP block cites URLs", warn=True)
        if st.get("search"):
            all_gaps = blocks and all(b["status"].startswith("GAP") for b in blocks)
            add("02_search", "all gaps -> STOP.md (andon)", not all_gaps or exists(runs.STOP_FILE),
                "every sub-question is a GAP but there is no STOP.md")
    if status.get("02_search") == "done":
        add("02_search", "evidence.md + sources.json exist",
            exists(runs.EVIDENCE_FILE) and exists(runs.SOURCES_FILE), "missing")
        add("02_search", "no stale STOP.md", not exists(runs.STOP_FILE), "STOP.md left behind")
    if status.get("02_search") == "stopped":
        add("02_search", "stop is explained in STOP.md", exists(runs.STOP_FILE), "missing")
        add("02_search", "no report after a stop", not exists(runs.REPORT_FILE), "report.md exists")

    # --- 03_report ---
    if status.get("03_report") == "done":
        text = run.read(runs.REPORT_FILE) if exists(runs.REPORT_FILE) else ""
        add("03_report", "report.md is not empty", bool(text.strip()), "missing or empty")
        allowed = found | _urls(run.read(runs.EVIDENCE_FILE) if exists(runs.EVIDENCE_FILE) else "")
        invented = _urls(text) - allowed
        add("03_report", "cites only URLs from the evidence", not invented, f"not in evidence: {sorted(invented)}")
        if blocks and any("NOT source-backed" in b["status"] for b in blocks):
            add("03_report", "unsourced run says NOT source-backed",
                "source-backed" in text.lower(), "report doesn't flag that it is unsourced", warn=True)
        if exists(runs.EVIDENCE_FILE) and exists(runs.REPORT_FILE):
            newer = run.path(runs.EVIDENCE_FILE).stat().st_mtime > run.path(runs.REPORT_FILE).stat().st_mtime + 1
            add("03_report", "report is newer than evidence.md", not newer,
                "evidence.md was edited after the report; resume from 03_report", warn=True)
    return out


def summarize(checks: list[Check]) -> dict:
    return {k: sum(1 for c in checks if c.status == k) for k in ("PASS", "WARN", "FAIL")}


def print_checks(name: str, checks: list[Check]) -> None:
    s = summarize(checks)
    print(f"{name}: {s['PASS']} pass, {s['WARN']} warn, {s['FAIL']} fail")
    for c in checks:
        if c.status != "PASS":
            print(f"  {c.status}  [{c.stage}] {c.name}: {c.detail}")


# --- replay ---

_STAGE_FILES = {"01_plan": [runs.PLAN_FILE], "02_search": [runs.EVIDENCE_FILE, runs.STOP_FILE],
                "03_report": [runs.REPORT_FILE]}


async def replay(run_dir: str | Path, client, from_stage: str, out_root: Optional[Path] = None,
                 live_search: bool = False) -> dict:
    """Copy a run, re-run it from ``from_stage``, check the copy, diff against the original."""
    from app.services import research as research_svc
    from app.models.research import Source

    if from_stage not in runs.STAGES:
        raise ValueError(f"from_stage must be one of {runs.STAGES}")
    src = runs.open_run(run_dir)
    out_root = Path(out_root or src.dir.parent / "_replays")
    dest = out_root / f"{src.id}__{from_stage}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(src.dir, dest)
    copy = runs.open_run(dest)
    if copy.path("trace.jsonl").exists():
        copy.path("trace.jsonl").rename(copy.path("trace.original.jsonl"))
    copy.path(runs.REJECTED_FILE).unlink(missing_ok=True)
    st = copy.state()
    st.update(gates=[], awaiting=None, replay_of=src.id)  # replays never pause
    copy.save_state(st)

    recorded = _recorded_sources(src)
    calls: list[str] = []

    async def recorded_search(query: str, max_results: int = 5):
        calls.append(query)
        return [Source(**s) for s in recorded.get(query, [])][:max_results]

    original_search = research_svc.web_search
    if not live_search:
        research_svc.web_search = recorded_search
    try:
        events = [e async for e in research_svc.resume_research(copy.dir, client, from_stage)]
    finally:
        research_svc.web_search = original_search

    diffs = {}
    for stage in runs.STAGES[runs.STAGES.index(from_stage):]:
        for rel in _STAGE_FILES[stage]:
            a = src.read(rel) if src.path(rel).exists() else ""
            b = copy.read(rel) if copy.path(rel).exists() else ""
            if a != b:
                diffs[rel] = "".join(difflib.unified_diff(
                    a.splitlines(keepends=True), b.splitlines(keepends=True),
                    fromfile=f"original/{rel}", tofile=f"replay/{rel}"))
    checks = check_run(copy.dir)
    summary = summarize(checks)
    lines = [f"# Replay of {src.id} from {from_stage}", "",
             f"- search: {'live' if live_search else 'recorded (same sources as the original)'}",
             f"- ended with: {events[-1].type if events else 'nothing'}"
             + (f" ({events[-1].message})" if events and events[-1].type == "error" else ""),
             f"- checks: {summary['PASS']} pass, {summary['WARN']} warn, {summary['FAIL']} fail",
             f"- changed files: {', '.join(diffs) or 'none'}", ""]
    for c in checks:
        if c.status != "PASS":
            lines.append(f"- {c.status} [{c.stage}] {c.name}: {c.detail}")
    for rel, d in diffs.items():
        lines += ["", f"## {rel}", "", "```diff", d.rstrip(), "```"]
    copy.write("REPLAY.md", "\n".join(lines) + "\n")
    return {"dir": copy.dir, "events": events, "diffs": diffs, "checks": checks,
            "search_calls": calls}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.stages", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check run folders against the stage contracts (offline)")
    c.add_argument("run_dirs", nargs="*", help="default: every run in the runs folder")
    r = sub.add_parser("replay", help="re-run a run from a stage and diff the outputs (needs a key)")
    r.add_argument("run_dir")
    r.add_argument("--from", dest="from_stage", default="03_report", choices=runs.STAGES)
    r.add_argument("--live-search", action="store_true", help="search the web again instead of replaying")
    args = ap.parse_args(argv)
    from app.cli import _load_dotenv
    from app.config import get_settings
    _load_dotenv()  # same backend/.env as the terminal agent (APP_RUNS_DIR, APP_API_KEY, ...)
    get_settings.cache_clear()

    if args.cmd == "check":
        dirs = [Path(d) for d in args.run_dirs] or sorted(
            d for d in runs.runs_root().iterdir() if (d / "state.json").exists())
        if not dirs:
            print(f"no runs found in {runs.runs_root()}")
            return 0
        failed = 0
        for d in dirs:
            checks = check_run(d)
            print_checks(d.name, checks)
            failed += summarize(checks)["FAIL"] > 0
        print(f"\n{len(dirs) - failed}/{len(dirs)} runs pass")
        return 1 if failed else 0

    key = os.getenv("APP_API_KEY", "")
    if not key:
        print("replay needs APP_API_KEY (+ optional APP_PROVIDER / APP_MODEL) in backend/.env")
        return 2
    from app.providers.base import build_client
    client = build_client(os.getenv("APP_PROVIDER", "openai"), key, os.getenv("APP_MODEL") or None)
    res = asyncio.run(replay(args.run_dir, client, args.from_stage, live_search=args.live_search))
    print_checks(f"replay -> {res['dir']}", res["checks"])
    print(f"changed: {', '.join(res['diffs']) or 'nothing'}  (full diff in {res['dir'] / 'REPLAY.md'})")
    return 1 if summarize(res["checks"])["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
