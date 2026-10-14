"""Run folders: the on-disk hand-off between workflow stages (ICM layer 4).

Every research run gets its own folder (default ``~/.assistant/runs/<run_id>/``):

    question.md                 the user's question (read-only record)
    state.json                  run settings + per-stage status (never holds an API key)
    trace.jsonl                 one JSON line per pipeline event (token events skipped)
    01_plan/plan.md             numbered sub-questions  -> read by stage 02
    02_search/evidence.md       one block per sub-question -> read by stage 03
    02_search/sources.json      raw search results (feeds the UI source list)
    02_search/STOP.md           written only when no evidence was found (andon stop)
    03_report/report.md         the final cited report

Each stage reads the previous stage's file from disk, so a person can edit
``plan.md`` or ``evidence.md`` and resume from the next stage. Stage contracts live
in ``workflows/deep_research/`` at the repo root.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..models.research import Source

WORKFLOW = "deep_research"
STAGES = ("01_plan", "02_search", "03_report")

PLAN_FILE = "01_plan/plan.md"
EVIDENCE_FILE = "02_search/evidence.md"
SOURCES_FILE = "02_search/sources.json"
STOP_FILE = "02_search/STOP.md"
REPORT_FILE = "03_report/report.md"
REJECTED_FILE = "REJECTED.md"

# Stages whose output a person reviews before the next stage runs (when the run
# was started with review on). Mirrors "gate: required" in the stage CONTEXT.md.
REVIEW_GATES = ("01_plan",)

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")


def runs_root() -> Path:
    s = get_settings()
    root = Path(s.runs_dir).expanduser() if s.runs_dir else Path.home() / ".assistant" / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].rstrip("-")) or "run"


@dataclass
class Run:
    dir: Path

    @property
    def id(self) -> str:
        return self.dir.name

    def path(self, rel: str) -> Path:
        return self.dir / rel

    def read(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> Path:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    # --- state.json ---
    def state(self) -> dict[str, Any]:
        return json.loads(self.read("state.json"))

    def save_state(self, state: dict[str, Any]) -> None:
        self.write("state.json", json.dumps(state, indent=2) + "\n")

    def set_stage(self, stage: str, status: str) -> None:
        st = self.state()
        st["stage_status"][stage] = status
        st["updated_at"] = _now()
        self.save_state(st)

    # --- trace.jsonl ---
    def trace(self, event: Any) -> None:
        with self.path("trace.jsonl").open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")


def create_run(query: str, *, search: bool, max_subquestions: int,
               provider: str, model: str | None, research_id: str,
               review: bool = False) -> Run:
    """Make a fresh run folder. Never pass the API key in here."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run = Run(runs_root() / f"{stamp}_{_slug(query)}_{research_id[:6]}")
    run.dir.mkdir(parents=True, exist_ok=False)
    run.write("question.md", f"# Question\n\n{query}\n")
    run.save_state({
        "run_id": run.id,
        "workflow": WORKFLOW,
        "research_id": research_id,
        "query": query,
        "search": search,
        "max_subquestions": max_subquestions,
        "provider": provider,
        "model": model,
        "created_at": _now(),
        "updated_at": _now(),
        "stage_status": {s: "pending" for s in STAGES},
        "gates": list(REVIEW_GATES) if review else [],
        "awaiting": None,     # set while paused: what a person must decide on
        "decisions": [],      # audit log: stage, action, at, note, diff
    })
    return run


def open_run(run_dir: str | Path) -> Run:
    run = Run(Path(run_dir))
    if not run.path("state.json").exists():
        raise FileNotFoundError(f"not a run folder (no state.json): {run.dir}")
    return run


def open_run_by_id(run_id: str) -> Run:
    """Open a run from an id that came over HTTP; refuses anything outside runs_root."""
    if not _RUN_ID.match(run_id or ""):
        raise FileNotFoundError("bad run id")
    root = runs_root().resolve()
    d = (root / run_id).resolve()
    if d.parent != root:
        raise FileNotFoundError("bad run id")
    return open_run(d)


# --- 01_plan/plan.md ---

def render_plan(query: str, subquestions: list[str]) -> str:
    lines = [
        "# Plan", "",
        f"Question: {query}", "",
        "<!-- Edit, reword, add or delete the numbered sub-questions. "
        "Stage 02 searches exactly the numbered lines below. -->", "",
    ]
    lines += [f"{i}. {q}" for i, q in enumerate(subquestions, 1)]
    return "\n".join(lines) + "\n"


_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")


def parse_plan(text: str) -> list[str]:
    """Sub-questions are the numbered lines (``1. ...`` or ``1) ...``)."""
    out = []
    for line in text.splitlines():
        m = _NUMBERED.match(line)
        if m:
            out.append(m.group(1))
    return out


# --- 02_search/evidence.md ---

def render_evidence(blocks: list[dict]) -> str:
    """blocks: {subquestion, status, summary, sources: list[Source]}"""
    out = [
        "# Evidence", "",
        "<!-- Stage 03 writes the report from this file. Edit or delete blocks to "
        "change what the report may claim. -->", "",
    ]
    for i, b in enumerate(blocks, 1):
        out += [f"## {i}. {b['subquestion']}", "", f"**Status:** {b['status']}", "",
                b["summary"].strip(), ""]
        if b["sources"]:
            out.append("Sources:")
            out += [f"- [{s.title or s.url}]({s.url})" for s in b["sources"] if s.url]
            out.append("")
    return "\n".join(out)


_BLOCK = re.compile(r"^## (\d+)\. (.+?)\s*$", re.M)


def parse_evidence(text: str) -> list[dict]:
    """Inverse of render_evidence (tolerant of hand edits): one dict per ``## N.`` block
    with ``subquestion``, ``status`` ('' if missing), ``finding`` and ``source_urls``."""
    heads = list(_BLOCK.finditer(text))
    out = []
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        status = re.search(r"^\*\*Status:\*\*\s*(.+?)\s*$", body, re.M)
        finding, _, src = body.partition("\nSources:")
        if status:
            finding = finding.replace(status.group(0), "", 1)
        out.append({
            "subquestion": h.group(2),
            "status": status.group(1) if status else "",
            "finding": finding.strip(),
            "source_urls": re.findall(r"^- \[.*?\]\((\S+?)\)\s*$", src, re.M),
        })
    return out


def write_sources(run: Run, blocks: list[dict]) -> None:
    data = [{"subquestion": b["subquestion"],
             "sources": [s.model_dump() for s in b["sources"]]} for b in blocks]
    run.write(SOURCES_FILE, json.dumps(data, indent=2) + "\n")


def read_sources(run: Run) -> list[Source]:
    """De-duplicated union of every source the search stage found."""
    if not run.path(SOURCES_FILE).exists():
        return []
    seen: set[str] = set()
    out: list[Source] = []
    for block in json.loads(run.read(SOURCES_FILE)):
        for raw in block.get("sources", []):
            s = Source(**raw)
            if s.url and s.url not in seen:
                seen.add(s.url)
                out.append(s)
    return out
