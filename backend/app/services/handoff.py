"""Shift handoff: 01 notes -> 02 summary -> 03 issues -> 04 next-shift brief, file-backed.

Each stage reads the previous stage's file from the run folder and writes its own, so
the supervisor can edit ``summary.md`` / ``issues.md`` at the gates and the next stage
uses the edited file. Stage contracts: ``workflows/shift_handoff/``; spec:
``_shared/shift-handoff.md``.

Cite or abstain: every bullet must point at a note line (``[L4]``). Code checks the
citations after each stage and the supervisor sees any problem before approving.
"""
from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional

from ..models.handoff import HandoffDecision, HandoffEvent, HandoffEventFactory, HandoffRequest
from ..providers.base import LLMClient, ProviderError
from . import runs
from .runs import Run

logger = logging.getLogger(__name__)

WORKFLOW = "shift_handoff"
STAGES = ("01_notes", "02_summary", "03_issues", "04_brief")
NOTES_FILE = "01_notes/notes.md"
STOP_FILE = "01_notes/STOP.md"
SUMMARY_FILE = "02_summary/summary.md"
ISSUES_FILE = "03_issues/issues.md"
BRIEF_FILE = "04_brief/brief.md"
REJECTED_FILE = "REJECTED.md"
ARTIFACTS = {"02_summary": SUMMARY_FILE, "03_issues": ISSUES_FILE, "04_brief": BRIEF_FILE}
GATES = ("02_summary", "03_issues")  # "gate: required" in the stage CONTEXT.md files
MIN_WORDS = 15

# Repo-root factory references (Layer 3). Missing (e.g. in the backend Docker image) -> defaults.
REFERENCES_DIR = Path(__file__).resolve().parents[3] / "workflows" / "shift_handoff" / "references"
DEFAULT_REFERENCES = {
    "glossary.md": "# Plant glossary\n\n(No plant glossary configured; use the supervisor's own words.)\n",
    "format.md": (
        "# Next-shift brief -- {line}, {shift}\n\n## Safety first\n## Top priorities (max 3)\n"
        "## Open issues & owners\n## Watch items\n## Handover\n"
        "Outgoing: ________  Incoming: ________  Time: ________\n"
    ),
}

SUMMARY_SYSTEM = (
    "You turn a production supervisor's raw end-of-shift notes into a structured shift "
    "summary for the incoming shift. Use ONLY the notes. The notes are given as numbered "
    "lines (L1, L2, ...). End every bullet with the line(s) it comes from, like [L3] or "
    "[L3, L7]. If something is ambiguous or incomplete, put it under the Unclear section "
    "instead of guessing. Never invent numbers, names, part numbers, times or causes. "
    "Use exactly these sections, in this order, and write '- None noted.' under any that "
    "is empty:\n## Safety\n## Quality\n## Production\n## Downtime & maintenance\n"
    "## People & staffing\n## Unclear -- ask the outgoing shift\n"
    "Output markdown only, no preamble. Plant glossary (use these terms):\n\n{glossary}"
)
ISSUES_SYSTEM = (
    "You extract open issues and next-shift risks from an approved shift summary. Use ONLY "
    "the summary. Output markdown only, no preamble:\n"
    "## Open issues\nA table with columns: # | Issue | Category | Severity | Evidence | Owner | "
    "Next action. Category is one of Safety, Quality, Delivery, Cost, People. Severity is "
    "High, Med or Low. Evidence is the [L#] reference(s) from the summary. Owner is a name "
    "only if the summary names one, otherwise 'unassigned'. Put Safety rows first. If "
    "nothing is open, write 'No open issues.' instead of the table.\n"
    "## Risks for next shift\nBullets, each ending with its [L#] reference(s).\n"
    "Do not add anything that is not in the summary."
)
BRIEF_SYSTEM = (
    "You write the one-page brief the incoming shift reads first. Use ONLY the approved "
    "summary and issues. Keep their [L#] references on every bullet. Safety first, at most "
    "3 top priorities, open issues with owners, watch items, then the handover sign-off "
    "lines. Under 300 words. Output markdown only, following this format:\n\n{format}"
)


# --- helpers ---

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def numbered_notes(notes: str) -> str:
    """The notes as the model sees them: 'L<n>: text' for each non-empty line."""
    return "\n".join(f"L{i}: {line}" for i, line in enumerate(notes.splitlines(), 1) if line.strip())


_REF = re.compile(r"\[(L\s*\d+(?:\s*(?:,|-|–|to)\s*L?\s*\d+)*)\]")
_NONE = re.compile(r"\b(none noted|no open issues|nothing (?:to report|noted|open))\b", re.I)


def _refs(text: str) -> list[int]:
    out: list[int] = []
    for group in _REF.findall(text):
        nums = [int(n) for n in re.findall(r"\d+", group)]
        if re.search(r"-|–|to", group) and len(nums) == 2 and nums[0] <= nums[1] <= nums[0] + 50:
            out += list(range(nums[0], nums[1] + 1))
        else:
            out += nums
    return out


def check_citations(markdown: str, note_lines: int) -> list[str]:
    """Warnings for bullets / table rows with no [L#] or a [L#] past the end of the notes."""
    warnings: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        is_bullet = bool(re.match(r"^([-*+]|\d+[.)])\s+\S", line))
        is_row = line.startswith("|") and not re.fullmatch(r"\|[\s:|-]+\|?", line) \
            and not re.search(r"\|\s*Issue\s*\|", line, re.I)
        if not (is_bullet or is_row) or _NONE.search(line):
            continue
        item = re.sub(r"^([-*+]|\d+[.)])\s+", "", line)[:90]
        refs = _refs(line)
        if not refs:
            warnings.append(f"No note line cited: \"{item}\"")
        bad = sorted({n for n in refs if n < 1 or n > note_lines})
        if bad:
            warnings.append(f"Cites L{', L'.join(map(str, bad))} but the notes have {note_lines} lines: \"{item}\"")
    return warnings


def _clean(text: str) -> str:
    t = (text or "").strip()
    m = re.fullmatch(r"```[a-zA-Z]*\n(.*?)\n```", t, re.S)  # model wrapped it in a fence
    return (m.group(1) if m else t).strip() + "\n"


def _is_handoff(run: Run) -> bool:
    return run.state().get("workflow") == WORKFLOW


# --- run folder ---

def create_handoff_run(req: HandoffRequest, run_id: str) -> Run:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run = Run(runs.runs_root() / f"{stamp}_{runs._slug(f'{req.line}-{req.shift}')}_{run_id[:6]}")
    run.dir.mkdir(parents=True, exist_ok=False)
    notes = req.notes.replace("\r\n", "\n").replace("\r", "\n")
    run.write(NOTES_FILE, notes if notes.endswith("\n") else notes + "\n")
    for name, default in DEFAULT_REFERENCES.items():  # snapshot the factory for this run
        src = REFERENCES_DIR / name
        run.write(f"references/{name}", src.read_text(encoding="utf-8") if src.exists() else default)
    run.save_state({
        "run_id": run.id, "workflow": WORKFLOW, "event_id": run_id,
        "line": req.line, "shift": req.shift, "supervisor": req.supervisor or "",
        "provider": req.provider.value, "model": req.model,
        "created_at": _now(), "updated_at": _now(),
        "stage_status": {s: "pending" for s in STAGES},
        "gates": list(GATES), "awaiting": None, "decisions": [], "citation_warnings": {},
    })
    return run


def _note_count(run: Run) -> int:
    return len(run.read(NOTES_FILE).splitlines())


# --- stages ---

async def _stream_to_file(run: Run, client: LLMClient, ev: HandoffEventFactory, stage: str,
                          system: str, user: str, sink: list[HandoffEvent]) -> AsyncIterator[HandoffEvent]:
    chunks: list[str] = []
    async for chunk in client.stream(system, user, max_tokens=3000):
        chunks.append(chunk)
        yield ev.token(stage, chunk)
    text = _clean("".join(chunks))
    rel = ARTIFACTS[stage]
    run.write(rel, text)
    warnings = check_citations(text, _note_count(run))
    st = run.state()
    st["citation_warnings"][stage] = warnings
    run.save_state(st)
    run.set_stage(stage, "done")
    sink.append(ev.stage_output(stage, rel, text, warnings))


async def _stage_notes(run, client, ev):
    notes = run.read(NOTES_FILE)
    words = len(re.findall(r"\w+", notes))
    yield ev.status("01_notes", f"Notes saved ({_note_count(run)} lines, {words} words)")
    if words < MIN_WORDS:
        run.write(STOP_FILE, (
            "# STOP: not enough notes\n\n"
            f"The notes have {words} words; at least {MIN_WORDS} are needed to write a handoff "
            "that cites what happened. Nothing was summarized rather than guessed.\n\n"
            "## What to do\n- Add what happened this shift (safety, quality, output, downtime, "
            "people) and start a new handoff.\n"
        ))
        run.set_stage("01_notes", "stopped")
        return
    run.set_stage("01_notes", "done")


async def _stage_summary(run, client, ev):
    st = run.state()
    yield ev.status("02_summary", "Writing the shift summary...")
    sink: list[HandoffEvent] = []
    user = (f"Line: {st['line']}\nShift: {st['shift']}\n\nNOTES (numbered):\n"
            f"{numbered_notes(run.read(NOTES_FILE))}\n\nWrite the summary now.")
    system = SUMMARY_SYSTEM.replace("{glossary}", run.read("references/glossary.md"))
    async for e in _stream_to_file(run, client, ev, "02_summary", system, user, sink):
        yield e
    yield sink[0]


async def _stage_issues(run, client, ev):
    yield ev.status("03_issues", "Pulling out open issues and risks...")
    sink: list[HandoffEvent] = []
    user = f"APPROVED SHIFT SUMMARY:\n\n{run.read(SUMMARY_FILE)}\n\nWrite the issues and risks now."
    async for e in _stream_to_file(run, client, ev, "03_issues", ISSUES_SYSTEM, user, sink):
        yield e
    yield sink[0]


async def _stage_brief(run, client, ev):
    st = run.state()
    yield ev.status("04_brief", "Writing the next-shift brief...")
    sink: list[HandoffEvent] = []
    fmt = run.read("references/format.md").replace("{line}", st["line"]).replace("{shift}", st["shift"])
    user = (f"Line: {st['line']}\nShift: {st['shift']}\n\nAPPROVED SUMMARY:\n\n{run.read(SUMMARY_FILE)}\n\n"
            f"APPROVED ISSUES:\n\n{run.read(ISSUES_FILE)}\n\nWrite the brief now.")
    async for e in _stream_to_file(run, client, ev, "04_brief", BRIEF_SYSTEM.replace("{format}", fmt),
                                   user, sink):
        yield e
    yield sink[0]


_STAGE_FNS = {"01_notes": _stage_notes, "02_summary": _stage_summary,
              "03_issues": _stage_issues, "04_brief": _stage_brief}


def _next(stage: str) -> Optional[str]:
    i = STAGES.index(stage)
    return STAGES[i + 1] if i + 1 < len(STAGES) else None


def _pause(run: Run, ev: HandoffEventFactory, stage: str) -> HandoffEvent:
    st = run.state()
    awaiting = {"stage": stage, "artifact": ARTIFACTS[stage], "next_stage": _next(stage),
                "allowed_actions": ["approve", "edit", "reject"]}
    st["awaiting"] = awaiting
    run.save_state(st)
    return ev.await_approval({
        "run_id": run.id, **awaiting,
        "artifact_content": run.read(ARTIFACTS[stage]),
        "citation_warnings": st["citation_warnings"].get(stage, []),
        "notes": run.read(NOTES_FILE),
    })


async def _run_stages(run: Run, client: LLMClient, ev: HandoffEventFactory,
                      from_stage: str) -> AsyncIterator[HandoffEvent]:
    def emit(e: HandoffEvent) -> HandoffEvent:
        run.trace(e)
        return e

    try:
        for stage in STAGES[STAGES.index(from_stage):]:
            async for e in _STAGE_FNS[stage](run, client, ev):
                if e.type != "token":
                    run.trace(e)
                yield e
            if run.state()["stage_status"][stage] == "stopped":
                yield emit(ev.error(
                    "Stopped: the notes are too short to write a cited handoff. See STOP.md; "
                    "add what happened this shift and start again.", code="stop"))
                return
            if stage in run.state().get("gates", []):
                yield emit(_pause(run, ev, stage))
                yield emit(ev.done("paused"))
                return
        yield emit(ev.done("complete", {"brief": run.read(BRIEF_FILE), "artifact": BRIEF_FILE}))
    except ProviderError as exc:
        logger.warning("provider error during handoff: %s", exc.message)
        yield emit(ev.error(exc.message, code=exc.code))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("handoff failed")
        yield ev.error(f"Internal error: {exc}", code="internal")


# --- public entry points ---

async def run_handoff(req: HandoffRequest, client: LLMClient) -> AsyncIterator[HandoffEvent]:
    ev = HandoffEventFactory()
    try:
        run = create_handoff_run(req, ev.run_id)
    except OSError as exc:
        yield ev.error(f"Could not create the run folder: {exc}", code="internal")
        return
    ev = HandoffEventFactory(run.id)  # events carry the run folder name -> decisions use it
    async for e in _run_stages(run, client, ev, "01_notes"):
        yield e


async def decide(run_id: str, req: HandoffDecision, client: LLMClient) -> AsyncIterator[HandoffEvent]:
    """approve -> run the next stage; edit -> save the supervisor's version (diff logged),
    then run the next stage; reject -> write REJECTED.md and close the run."""
    ev = HandoffEventFactory(run_id)
    try:
        run = runs.open_run_by_id(run_id)
        if not _is_handoff(run):
            raise FileNotFoundError
    except FileNotFoundError:
        yield ev.error(f"No shift handoff run '{run_id}'.", code="run_not_found")
        return
    st = run.state()
    awaiting = st.get("awaiting")
    if not awaiting or awaiting["stage"] != req.stage:
        current = awaiting["stage"] if awaiting else "none"
        yield ev.error(f"This handoff is not waiting on {req.stage} (waiting on: {current}).",
                       code="stage_mismatch")
        return

    entry = {"stage": req.stage, "action": req.action, "at": _now(), "note": req.note or ""}
    if req.action == "edit":
        new = (req.edited_content or "").replace("\r\n", "\n").strip()
        if not new:
            yield ev.error("The edited text is empty. Nothing was changed.", code="validation")
            return
        old = run.read(awaiting["artifact"])
        entry["diff"] = "".join(difflib.unified_diff(
            old.splitlines(keepends=True), (new + "\n").splitlines(keepends=True),
            fromfile=f"{awaiting['artifact']} (model)", tofile=f"{awaiting['artifact']} (supervisor)"))
        run.write(awaiting["artifact"], new + "\n")
        st = run.state()
        st["citation_warnings"][req.stage] = check_citations(new, _note_count(run))

    st["awaiting"] = None
    st["decisions"].append(entry)
    run.save_state(st)

    if req.action == "reject":
        run.write(REJECTED_FILE, f"# Rejected at {req.stage}\n\n- at: {entry['at']}\n\n{req.note or '(no note)'}\n")
        run.set_stage(req.stage, "rejected")
        done = ev.done("rejected")
        run.trace(done)
        yield done
        return

    nxt = awaiting["next_stage"]
    for s in STAGES[STAGES.index(nxt):]:
        run.set_stage(s, "pending")
    failed: Optional[HandoffEvent] = None
    async for e in _run_stages(run, client, ev, nxt):
        if e.type == "error":  # e.g. a rejected key or a provider outage
            failed = e
            break
        yield e
    if failed is not None:
        # Same as research: put the gate back so the supervisor can retry (gate, then error).
        st = run.state()
        st["decisions"][-1]["failed"] = failed.message
        run.save_state(st)
        run.set_stage(req.stage, "done")
        gate = _pause(run, ev, req.stage)
        run.trace(gate)
        yield gate
        yield failed


def _summary_status(st: dict) -> str:
    ss = st.get("stage_status", {})
    if st.get("awaiting"):
        return f"awaiting {st['awaiting']['stage']}"
    for label in ("rejected", "stopped"):
        if label in ss.values():
            return label
    return "complete" if ss.get("04_brief") == "done" else "in progress"


def list_runs(limit: int = 20) -> list[dict]:
    out = []
    for d in runs.runs_root().iterdir():
        try:
            run = runs.open_run(d)
            st = run.state()
        except (FileNotFoundError, ValueError, OSError):
            continue
        if st.get("workflow") != WORKFLOW:
            continue
        out.append({"run_id": run.id, "line": st["line"], "shift": st["shift"],
                    "supervisor": st.get("supervisor", ""), "created_at": st["created_at"],
                    "status": _summary_status(st)})
    return sorted(out, key=lambda r: r["created_at"], reverse=True)[:limit]


def get_run(run_id: str) -> Optional[dict]:
    """Everything the dashboard needs to show (or resume) one handoff."""
    try:
        run = runs.open_run_by_id(run_id)
    except FileNotFoundError:
        return None
    if not _is_handoff(run):
        return None
    st = run.state()
    files = {rel: run.read(rel) for rel in (NOTES_FILE, STOP_FILE, *ARTIFACTS.values(), REJECTED_FILE)
             if run.path(rel).exists()}
    awaiting = None
    if st.get("awaiting"):
        a = st["awaiting"]
        awaiting = {"run_id": run.id, **a, "artifact_content": run.read(a["artifact"]),
                    "citation_warnings": st["citation_warnings"].get(a["stage"], []),
                    "notes": run.read(NOTES_FILE)}
    return {"run_id": run.id, "line": st["line"], "shift": st["shift"],
            "supervisor": st.get("supervisor", ""), "created_at": st["created_at"],
            "provider": st.get("provider"), "model": st.get("model"),
            "status": _summary_status(st), "stage_status": st["stage_status"],
            "citation_warnings": st["citation_warnings"], "decisions": st["decisions"],
            "awaiting": awaiting, "files": files}
