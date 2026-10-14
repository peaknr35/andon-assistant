"""Stage evals for workflow run folders: check each stage, and replay a run.

    python -m evals.stages check [RUN ...]      # offline; default: every run in the runs folder
    python -m evals.stages judge latest         # AI judge: is every report claim in evidence.md?
    python -m evals.stages replay latest --from 03_report [--live-search] [--judge]

RUN is a run folder path, a run id (its folder name), or ``latest``.

``check`` holds each stage's output to its contract in workflows/deep_research/NN_*/CONTEXT.md.
FAIL = the contract is broken; WARN = worth a look (e.g. a file edited after the next stage ran).

``replay`` copies a run, re-runs it from a stage with the same recorded search results
(unless ``--live-search``), checks the copy, and diffs each stage's output against the
original -- so a prompt or model change can be judged on the same evidence.

``judge`` is the semantic check the rules can't do: it splits the report into claims
(in code) and asks a model whether ``evidence.md`` supports each one. Results go to
``<runs>/_evals/``. ``judge`` and ``replay`` need APP_API_KEY (+ APP_PROVIDER /
APP_MODEL, or --provider / --model to judge with a different model). The original run
is never modified.
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


def _key_leaks(run: Run) -> list[str]:
    return [str(f.relative_to(run.dir)) for f in run.dir.rglob("*")
            if f.is_file() and _SECRET.search(f.read_text(encoding="utf-8", errors="replace"))]


def check_handoff_run(run: Run) -> list[Check]:
    """Shift handoff: notes kept verbatim, every bullet cites a real note line, stage order."""
    from app.services import handoff as ho

    st = run.state()
    status = st.get("stage_status", {})
    out: list[Check] = []

    def add(stage, name, ok, detail="", warn=False):
        out.append(Check(stage, name, "PASS" if ok else ("WARN" if warn else "FAIL"), "" if ok else detail))

    leaks = _key_leaks(run)
    add("run", "no API key on disk", not leaks and "api_key" not in st, f"key-like text in: {leaks}")
    for i, s_ in enumerate(ho.STAGES[1:], 1):
        if status.get(s_) in ("done", "rejected"):
            add("run", f"{s_} ran after {ho.STAGES[i - 1]}", status.get(ho.STAGES[i - 1]) == "done",
                f"{s_} is {status.get(s_)} but {ho.STAGES[i - 1]} is {status.get(ho.STAGES[i - 1])}")

    add("01_notes", "notes.md exists", run.path(ho.NOTES_FILE).exists(), "missing")
    if not run.path(ho.NOTES_FILE).exists():
        return out
    n = len(run.read(ho.NOTES_FILE).splitlines())
    if status.get("01_notes") == "stopped":
        add("01_notes", "stop is explained in STOP.md", run.path(ho.STOP_FILE).exists(), "missing")
        add("01_notes", "nothing written after a stop", not run.path(ho.SUMMARY_FILE).exists(), "summary.md exists")

    prev = ho.NOTES_FILE
    for stage, rel in ho.ARTIFACTS.items():
        if status.get(stage) not in ("done", "rejected") and not run.path(rel).exists():
            prev = rel
            continue
        text = run.read(rel) if run.path(rel).exists() else ""
        add(stage, f"{rel.split('/')[-1]} is not empty", bool(text.strip()), "missing or empty")
        warnings = ho.check_citations(text, n)
        bad = [w for w in warnings if w.startswith("Cites")]
        uncited = [w for w in warnings if w.startswith("No note line")]
        add(stage, "cites only note lines that exist", not bad, "; ".join(bad[:3]))
        add(stage, "every bullet cites a note line", not uncited,
            f"{len(uncited)} uncited, e.g. {uncited[0] if uncited else ''}", warn=True)
        if run.path(prev).exists() and run.path(rel).exists():
            newer = run.path(prev).stat().st_mtime > run.path(rel).stat().st_mtime + 1
            add(stage, f"written after {prev.split('/')[-1]} was last changed", not newer,
                f"{prev} was edited after {rel} was written; L-numbers or content may be stale", warn=True)
        prev = rel
    if run.path(ho.SUMMARY_FILE).exists():
        text = run.read(ho.SUMMARY_FILE).lower()
        missing = [h for h in ("safety", "quality", "production", "unclear") if f"## {h}" not in text]
        add("02_summary", "has the required sections", not missing, f"missing: {missing}", warn=True)
    if run.path(ho.BRIEF_FILE).exists():
        add("04_brief", "brief leads with safety", "safety" in run.read(ho.BRIEF_FILE).lower(),
            "no safety section", warn=True)
    return out


def check_run(run_dir: str | Path) -> list[Check]:
    run = runs.open_run(run_dir)
    st = run.state()
    if st.get("workflow") == "shift_handoff":
        return check_handoff_run(run)
    status = st.get("stage_status", {})
    out: list[Check] = []

    def add(stage: str, name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        out.append(Check(stage, name, "PASS" if ok else ("WARN" if warn else "FAIL"), "" if ok else detail))

    def exists(rel: str) -> bool:
        return run.path(rel).exists()

    # --- run-level ---
    leaks = _key_leaks(run)
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


# --- judge: does the evidence support each claim in the report? ---

JUDGE_SYSTEM = (
    "You are a strict fact-checker for a report. You get EVIDENCE (the only allowed source: "
    "research findings in numbered ## blocks, or a supervisor's numbered note lines) and "
    "numbered CLAIMS taken from the report. For each claim choose one verdict:\n"
    "- supported: the evidence states it or directly implies it\n"
    "- partial: part of it is in the evidence, part is not\n"
    "- unsupported: the evidence does not say this (even if it is true in general)\n"
    "- contradicted: the evidence says otherwise\n"
    "- no_claim: no factual content (a heading-like line, transition, or recommendation)\n"
    "A claim that a point could not be answered or lacked sources is supported when the "
    "evidence marks that block as GAP. Sign-off lines, blanks to fill in and section "
    "labels are no_claim. Judge only against the evidence, never your own "
    "knowledge. Respond with ONLY a JSON array, one object per claim: "
    '[{"id": 1, "verdict": "supported", "block": 2, "why": "short reason"}]. '
    "block is the evidence block (or note line) number that decides it, or null."
)
VERDICTS = ("supported", "partial", "unsupported", "contradicted", "no_claim")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(*])")
_SKIP_SECTION = re.compile(r"^#{1,6}\s*(sources|references|bibliography)\b", re.I)


def split_claims(report: str, limit: int = 80) -> list[str]:
    """Report -> checkable sentences. Skips headings, the sources list, link-only lines,
    code, and fragments under five words."""
    claims: list[str] = []
    in_code = skip = False
    for raw in report.splitlines():
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if line.startswith("#"):
            skip = bool(_SKIP_SECTION.match(line))
            continue
        if skip or re.fullmatch(r"(\*\*)?(sources|references)(:)?(\*\*)?:?", line, re.I):
            skip = True
            continue
        line = re.sub(r"^([-*+]|\d+[.)])\s+", "", line).strip()
        if re.fullmatch(r"\[?[^\]]*\]?\(?https?://\S+\)?", line) or set(line) <= set("-*_|: "):
            continue
        for sent in _SENT.split(line):
            sent = sent.strip()
            if len(re.findall(r"[A-Za-z0-9]+", _URL.sub("", sent))) >= 5:
                claims.append(sent)
    return claims[:limit]


def _parse_verdicts(raw: str) -> dict[int, dict]:
    m = re.search(r"\[.*\]", raw or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return {}
    out = {}
    for d in data if isinstance(data, list) else []:
        try:
            cid = int(d.get("id"))
        except (TypeError, ValueError, AttributeError):
            continue
        v = str(d.get("verdict", "")).strip().lower()
        if v in VERDICTS:
            out[cid] = {"verdict": v, "block": d.get("block"), "why": str(d.get("why", ""))[:300]}
    return out


async def judge_report(run_dir: str | Path, client, *, batch: int = 25,
                       max_unsupported: float = 0.2) -> dict:
    """Ask ``client`` whether evidence.md supports each claim in report.md."""
    run = runs.open_run(run_dir)
    if run.state().get("workflow") == "shift_handoff":  # judge the brief against the raw notes
        from app.services import handoff as ho
        evidence_rel, report_rel = ho.NOTES_FILE, ho.BRIEF_FILE
    else:
        evidence_rel, report_rel = runs.EVIDENCE_FILE, runs.REPORT_FILE
    if not run.path(report_rel).exists() or not run.path(evidence_rel).exists():
        raise FileNotFoundError(f"the run needs both {evidence_rel} and {report_rel} to be judged")
    evidence = run.read(evidence_rel)
    if evidence_rel.endswith("notes.md"):
        from app.services.handoff import numbered_notes
        evidence = "NOTES (numbered lines; [L#] in claims refers to these):\n" + numbered_notes(evidence)
    claims = split_claims(run.read(report_rel))
    results: list[dict] = []
    for start in range(0, len(claims), batch):
        chunk = claims[start:start + batch]
        numbered = "\n".join(f"{start + i + 1}. {c}" for i, c in enumerate(chunk))
        raw = await client.complete(
            JUDGE_SYSTEM, f"EVIDENCE:\n{evidence}\n\nCLAIMS:\n{numbered}\n\nReturn the JSON array now.",
            max_tokens=3000,
        )
        verdicts = _parse_verdicts(raw)
        for i, c in enumerate(chunk):
            cid = start + i + 1
            v = verdicts.get(cid, {"verdict": "unjudged", "block": None, "why": "judge gave no verdict"})
            results.append({"id": cid, "claim": c, **v})

    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in (*VERDICTS, "unjudged")}
    factual = len(results) - counts["no_claim"] - counts["unjudged"]
    unsupported_share = (counts["unsupported"] / factual) if factual else 0.0
    score = ((counts["supported"] + 0.5 * counts["partial"]) / factual) if factual else None
    checks = [
        Check("judge", "report has checkable claims", "PASS" if results else "WARN",
              "" if results else "no claims found in report.md"),
        Check("judge", "no claim contradicts the evidence", "PASS" if not counts["contradicted"] else "FAIL",
              "" if not counts["contradicted"] else f"{counts['contradicted']} contradicted"),
        Check("judge", f"unsupported claims <= {max_unsupported:.0%}",
              "FAIL" if unsupported_share > max_unsupported else ("WARN" if counts["unsupported"] else "PASS"),
              "" if not counts["unsupported"] else f"{counts['unsupported']}/{factual} unsupported"),
        Check("judge", "every claim judged", "WARN" if counts["unjudged"] else "PASS",
              "" if not counts["unjudged"] else f"{counts['unjudged']} without a verdict"),
    ]
    return {"run": run.id, "claims": results, "counts": counts, "score": score,
            "unsupported_share": unsupported_share, "checks": checks,
            "judge_model": f"{getattr(client, 'provider', '?')}/{getattr(client, 'model', '?')}"}


def render_judgement(j: dict) -> str:
    score = "n/a" if j["score"] is None else f"{j['score']:.0%}"
    c = j["counts"]
    lines = [f"# Judge: {j['run']}", "",
             f"- judge model: {j['judge_model']}",
             f"- grounded score: {score} (supported + half of partial, over factual claims)",
             f"- {c['supported']} supported, {c['partial']} partial, {c['unsupported']} unsupported, "
             f"{c['contradicted']} contradicted, {c['no_claim']} no claim, {c['unjudged']} unjudged", ""]
    for ch in j["checks"]:
        lines.append(f"- {ch.status} {ch.name}{': ' + ch.detail if ch.detail else ''}")
    lines += ["", "| # | verdict | block | claim | why |", "|---|---|---|---|---|"]
    for r in j["claims"]:
        cell = lambda t: str(t).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r['id']} | {r['verdict']} | {r['block'] if r['block'] is not None else ''} "
                     f"| {cell(r['claim'])} | {cell(r['why'])} |")
    return "\n".join(lines) + "\n"


def _write_judgement(j: dict, folder: Path, stem: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    md = folder / f"{stem}.md"
    md.write_text(render_judgement(j), encoding="utf-8")
    data = {k: v for k, v in j.items() if k != "checks"}
    data["checks"] = [c.__dict__ for c in j["checks"]]
    (folder / f"{stem}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return md


# --- replay ---

_STAGE_FILES = {"01_plan": [runs.PLAN_FILE], "02_search": [runs.EVIDENCE_FILE, runs.STOP_FILE],
                "03_report": [runs.REPORT_FILE]}


async def replay(run_dir: str | Path, client, from_stage: str, out_root: Optional[Path] = None,
                 live_search: bool = False, judge_client=None) -> dict:
    """Copy a run, re-run it from ``from_stage``, check the copy, diff against the original."""
    from app.services import research as research_svc
    from app.models.research import Source

    if from_stage not in runs.STAGES:
        raise ValueError(f"from_stage must be one of {runs.STAGES}")
    src = runs.open_run(run_dir)
    if src.state().get("workflow") != runs.WORKFLOW:
        raise ValueError(f"replay supports deep_research runs only; {src.id} is "
                         f"{src.state().get('workflow')}")
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
    judged = {}
    if judge_client is not None:
        for label, d in (("original", src.dir), ("replay", copy.dir)):
            try:
                judged[label] = await judge_report(d, judge_client)
            except FileNotFoundError:
                continue
        if judged:
            lines += ["", "## Judge (same judge model for both)", "",
                      "| | grounded score | supported | partial | unsupported | contradicted |",
                      "|---|---|---|---|---|---|"]
            for label, j in judged.items():
                c = j["counts"]
                score = "n/a" if j["score"] is None else f"{j['score']:.0%}"
                lines.append(f"| {label} | {score} | {c['supported']} | {c['partial']} | "
                             f"{c['unsupported']} | {c['contradicted']} |")
            if "replay" in judged:
                copy.write("JUDGE.md", render_judgement(judged["replay"]))
    copy.write("REPLAY.md", "\n".join(lines) + "\n")
    return {"dir": copy.dir, "events": events, "diffs": diffs, "checks": checks,
            "search_calls": calls, "judged": judged}


def resolve_run_dir(arg: str) -> Path:
    """A run folder path, a run id (folder name in the runs folder), or ``latest``."""
    root = runs.runs_root()
    if arg == "latest":
        found = sorted((d for d in root.iterdir() if (d / "state.json").exists()),
                       key=lambda d: d.stat().st_mtime)
        if not found:
            raise SystemExit(f"no runs found in {root}")
        return found[-1]
    p = Path(arg).expanduser()
    if not (p / "state.json").exists() and (root / arg / "state.json").exists():
        p = root / arg
    if not (p / "state.json").exists():
        raise SystemExit(f"not a run folder: {arg} (try 'latest', or a folder in {root})")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m evals.stages", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check run folders against the stage contracts (offline)")
    c.add_argument("run_dirs", nargs="*", help="run folders, run ids, or 'latest' (default: every run)")
    r = sub.add_parser("replay", help="re-run a run from a stage and diff the outputs (needs a key)")
    r.add_argument("run_dir", help="run folder, run id, or 'latest'")
    r.add_argument("--from", dest="from_stage", default="03_report", choices=runs.STAGES)
    r.add_argument("--live-search", action="store_true", help="search the web again instead of replaying")
    r.add_argument("--judge", action="store_true", help="also judge the original and the replay")
    j = sub.add_parser("judge", help="AI judge: is each report claim supported by evidence.md? (needs a key)")
    j.add_argument("run_dir", help="run folder, run id, or 'latest'")
    j.add_argument("--max-unsupported", type=float, default=0.2, help="FAIL above this share (default 0.2)")
    for p_ in (r, j):
        p_.add_argument("--provider", help="judge/replay provider (default APP_PROVIDER)")
        p_.add_argument("--model", help="model (default APP_MODEL)")
    args = ap.parse_args(argv)
    from app.cli import _load_dotenv
    from app.config import get_settings
    _load_dotenv()  # same backend/.env as the terminal agent (APP_RUNS_DIR, APP_API_KEY, ...)
    get_settings.cache_clear()

    if args.cmd == "check":
        dirs = [resolve_run_dir(d) for d in args.run_dirs] or sorted(
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
        print(f"{args.cmd} needs APP_API_KEY (+ optional APP_PROVIDER / APP_MODEL) in backend/.env")
        return 2
    from app.providers.base import build_client
    client = build_client(args.provider or os.getenv("APP_PROVIDER", "openai"), key,
                          args.model or os.getenv("APP_MODEL") or None)

    args.run_dir = resolve_run_dir(args.run_dir)
    if args.cmd == "judge":
        j = asyncio.run(judge_report(args.run_dir, client, max_unsupported=args.max_unsupported))
        path = _write_judgement(j, runs.runs_root() / "_evals",
                                f"{j['run']}__judge_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        score = "n/a" if j["score"] is None else f"{j['score']:.0%}"
        print_checks(f"judge {j['run']} (grounded {score}, {len(j['claims'])} claims)", j["checks"])
        for r_ in j["claims"]:
            if r_["verdict"] in ("unsupported", "contradicted"):
                print(f"  {r_['verdict'].upper():12} #{r_['id']} {r_['claim'][:110]}")
        print(f"full table: {path}")
        return 1 if summarize(j["checks"])["FAIL"] else 0

    res = asyncio.run(replay(args.run_dir, client, args.from_stage, live_search=args.live_search,
                             judge_client=client if args.judge else None))
    print_checks(f"replay -> {res['dir']}", res["checks"])
    for label, j_ in res["judged"].items():
        score = "n/a" if j_["score"] is None else f"{j_['score']:.0%}"
        print(f"  judge {label}: grounded {score}  {j_['counts']}")
    print(f"changed: {', '.join(res['diffs']) or 'nothing'}  (full diff in {res['dir'] / 'REPLAY.md'})")
    failed = summarize(res["checks"])["FAIL"] or (
        "replay" in res["judged"] and summarize(res["judged"]["replay"]["checks"])["FAIL"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
