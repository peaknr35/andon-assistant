"""The deep-research pipeline: 01 plan -> 02 search -> 03 report, file-backed.

Each stage reads its input from the run folder on disk and writes its output there
(see ``runs.py``), so a person can edit ``plan.md`` or ``evidence.md`` and resume
from the next stage with ``resume_research``. Stage contracts live in
``workflows/deep_research/`` at the repo root; the spec is
``_shared/research-workflow.md``. No framework; the control flow is readable
top-to-bottom on purpose (ICM invariant 9).

Andon rule: with search on, a sub-question with no sources is recorded as a GAP,
never filled in from general knowledge. If no sub-question has any source, stage 02
writes ``STOP.md`` and the run halts with an ``error`` (code ``stop``).
"""
from __future__ import annotations

import difflib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Optional

from ..config import get_settings
from ..models.research import (
    DecisionRequest, EventFactory, ResearchEvent, ResearchRequest, Source,
)
from ..providers.base import LLMClient, ProviderError
from . import runs
from .runs import Run
from .search import web_search

logger = logging.getLogger(__name__)

PLAN_SYSTEM = (
    "You are a meticulous research planner. Given a user's question, break it into "
    "a small set of focused, independently-researchable sub-questions that together "
    "fully answer it. Prefer specific, non-overlapping angles. "
    'Respond with ONLY a JSON array of strings, e.g. ["...", "..."]. No prose.'
)

SYNTH_SYSTEM = (
    "You are a careful research analyst. Using ONLY the provided web search results, "
    "write a concise, factual answer to the sub-question. Ground every claim in the "
    "sources and cite them inline using their URL in parentheses. If the sources do "
    "not answer the sub-question, say exactly what is missing -- do not fill the gap "
    "from general knowledge. Keep it to a few tight paragraphs."
)

# Used only when the user turned search off for the run.
UNSOURCED_SYSTEM = (
    "You are a careful research analyst. Web search is turned off for this run, so "
    "answer the sub-question concisely from general knowledge. Do not cite or invent "
    "URLs. Keep it to a few tight paragraphs."
)

GAP_NOTE = "No usable web sources were found for this sub-question. It is a gap, not an answer."

REPORT_SYSTEM = (
    "You are an expert report writer. Synthesize the research findings into a "
    "clear, well-structured markdown report that answers the original question. "
    "Use: a short executive summary, themed sections with ## headings, and a brief "
    "conclusion. Preserve inline source citations where relevant. Be objective and "
    "do not invent facts beyond the findings. Findings marked GAP had no sources: say "
    "plainly that those points could not be answered, and do not fill them in. If "
    "findings are marked unsourced, state at the top that the report is NOT "
    "source-backed."
)


def _plan_user(query: str, n: int) -> str:
    return f"Question: {query}\n\nProduce at most {n} sub-questions as a JSON array of strings."


def _sources_block(sources: list[Source]) -> str:
    if not sources:
        return "(no web search results were available)"
    lines = []
    for i, s in enumerate(sources, 1):
        lines.append(f"[{i}] {s.title}\nURL: {s.url}\n{s.snippet}")
    return "\n\n".join(lines)


def _synth_user(subquestion: str, sources: list[Source]) -> str:
    return (
        f"Sub-question: {subquestion}\n\n"
        f"Web search results:\n{_sources_block(sources)}\n\n"
        "Write the grounded answer now."
    )


def _report_user(query: str, evidence_md: str) -> str:
    return (
        f"Original question: {query}\n\n"
        f"Research findings (from evidence.md):\n\n{evidence_md}\n\n"
        "Write the final markdown report now."
    )


def _parse_subquestions(raw: str, fallback_query: str, n: int) -> list[str]:
    """Extract a JSON array of strings from the model output, robustly."""
    text = (raw or "").strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    candidate = match.group(0) if match else text
    try:
        data = json.loads(candidate)
        if isinstance(data, list):
            subs = [str(x).strip() for x in data if str(x).strip()]
            if subs:
                return subs[:n]
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: split numbered/bulleted lines, else use the question itself.
    lines = [
        re.sub(r"^\s*(?:[-*\d.)]+)\s*", "", ln).strip()
        for ln in text.splitlines()
        if ln.strip()
    ]
    lines = [ln for ln in lines if len(ln) > 8]
    return (lines[:n] if lines else [fallback_query])


# --- stages: each reads the previous stage's file and writes its own ---

async def _stage_plan(run: Run, client: LLMClient, ev: EventFactory) -> AsyncIterator[ResearchEvent]:
    st = run.state()
    yield ev.status("planning", "Planning the research...", 0.0)
    raw_plan = await client.complete(
        PLAN_SYSTEM, _plan_user(st["query"], st["max_subquestions"]), max_tokens=700
    )
    subquestions = _parse_subquestions(raw_plan, st["query"], st["max_subquestions"])
    run.write(runs.PLAN_FILE, runs.render_plan(st["query"], subquestions))
    run.set_stage("01_plan", "done")
    yield ev.plan(subquestions)


async def _stage_search(run: Run, client: LLMClient, ev: EventFactory) -> AsyncIterator[ResearchEvent]:
    st = run.state()
    subquestions = runs.parse_plan(run.read(runs.PLAN_FILE))
    if not subquestions:
        raise ValueError(f"{runs.PLAN_FILE} has no numbered sub-questions")
    settings = get_settings()
    blocks: list[dict] = []
    total = len(subquestions)
    for i, subq in enumerate(subquestions):
        yield ev.status("researching", f"Researching: {subq}", i / max(total, 1))
        sources: list[Source] = []
        if st["search"]:
            sources = await web_search(subq, settings.search_max_results)
            yield ev.sources(i, subq, sources)
            if sources:
                status = "sourced"
                summary = await client.complete(
                    SYNTH_SYSTEM, _synth_user(subq, sources), max_tokens=900
                )
            else:
                status, summary = "GAP (no usable sources)", GAP_NOTE
        else:
            status = "unsourced (search off; NOT source-backed)"
            summary = await client.complete(UNSOURCED_SYSTEM, f"Sub-question: {subq}", max_tokens=900)
        blocks.append({"subquestion": subq, "status": status, "summary": summary, "sources": sources})
        yield ev.finding(i, subq, summary, sources)

    run.write(runs.EVIDENCE_FILE, runs.render_evidence(blocks))
    runs.write_sources(run, blocks)
    if st["search"] and not any(b["sources"] for b in blocks):
        run.write(runs.STOP_FILE, (
            "# STOP: no evidence\n\n"
            f"Web search returned no usable sources for any of the {total} sub-questions "
            f"in `{runs.PLAN_FILE}`, so there is nothing to cite. The report was not "
            "written rather than guessed.\n\n"
            "## What to do\n"
            "- Retry later (the search backend may be rate-limited), or\n"
            f"- Reword the sub-questions in `{runs.PLAN_FILE}` and resume from 02_search, or\n"
            f"- Add evidence to `{runs.EVIDENCE_FILE}` by hand and resume from 03_report.\n"
        ))
        run.set_stage("02_search", "stopped")
        return
    run.set_stage("02_search", "done")


async def _stage_report(run: Run, client: LLMClient, ev: EventFactory) -> AsyncIterator[ResearchEvent]:
    st = run.state()
    evidence_md = run.read(runs.EVIDENCE_FILE)
    yield ev.status("report", "Writing the final report...", 1.0)
    chunks: list[str] = []
    async for chunk in client.stream(
        REPORT_SYSTEM, _report_user(st["query"], evidence_md), max_tokens=8000
    ):
        chunks.append(chunk)
        yield ev.token(chunk)
    report_text = "".join(chunks).strip()
    run.write(runs.REPORT_FILE, report_text + "\n")
    run.set_stage("03_report", "done")
    yield ev.report(report_text, runs.read_sources(run))


_STAGE_FNS = {"01_plan": _stage_plan, "02_search": _stage_search, "03_report": _stage_report}


def _pause(run: Run, ev: EventFactory, *, stage: str, reason: str,
           allowed: list[str]) -> ResearchEvent:
    """Record what a person must decide on, and build the await_approval event.
    In both cases the person reviews the plan and work resumes at 02_search."""
    awaiting = {
        "stage": stage,
        "reason": reason,                       # review | stop
        "artifact": runs.PLAN_FILE,
        "resume_from": "02_search",
        "allowed_actions": allowed,
    }
    st = run.state()
    st["awaiting"] = awaiting
    run.save_state(st)
    data = {
        "run_id": run.id,
        **awaiting,
        "next_stage": awaiting["resume_from"],
        "artifact_content": run.read(runs.PLAN_FILE),
        "stop_reason": (run.read(runs.STOP_FILE)
                        if reason == "stop" and run.path(runs.STOP_FILE).exists() else None),
    }
    return ev.await_approval(data)


async def _run_stages(run: Run, client: LLMClient, ev: EventFactory,
                      from_stage: str) -> AsyncIterator[ResearchEvent]:
    """Run stages from ``from_stage`` to the end, pausing at review gates; one
    ``error`` event on failure."""

    def emit(event: ResearchEvent) -> ResearchEvent:
        run.trace(event)
        return event

    try:
        gates = run.state().get("gates", [])
        for stage in runs.STAGES[runs.STAGES.index(from_stage):]:
            async for event in _STAGE_FNS[stage](run, client, ev):
                if event.type != "token":
                    run.trace(event)
                yield event
            if run.state()["stage_status"][stage] == "stopped":
                if gates:  # a person is in the loop: hand the stop to them
                    yield emit(_pause(run, ev, stage=stage, reason="stop",
                                      allowed=["approve", "edit", "reject"]))
                    yield emit(ev.done("paused"))
                    return
                yield emit(ev.error(
                    f"Research stopped at {stage}: no usable web sources were found, so "
                    "nothing was guessed. See STOP.md in the run folder. Retry later or "
                    "reword the plan.",
                    code="stop",
                ))
                return
            if stage in gates:
                yield emit(_pause(run, ev, stage=stage, reason="review",
                                  allowed=["approve", "edit", "reject"]))
                yield emit(ev.done("paused"))
                return
        yield emit(ev.done())
    except ProviderError as exc:
        logger.warning("provider error during research: %s", exc.message)
        yield ev.error(exc.message, code=exc.code)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("research pipeline failed")
        yield ev.error(f"Internal error: {exc}", code="internal")


async def run_research(req: ResearchRequest, client: LLMClient) -> AsyncIterator[ResearchEvent]:
    """Start a new run folder and run all three stages."""
    ev = EventFactory()
    try:
        run = runs.create_run(
            req.query, search=req.search, max_subquestions=req.max_subquestions,
            provider=req.provider.value, model=req.model, research_id=ev.research_id,
            review=req.review_plan,
        )
    except OSError as exc:
        logger.exception("could not create run folder")
        yield ev.error(f"Could not create the run folder: {exc}", code="internal")
        return
    logger.info("research run folder: %s", run.dir)
    async for event in _run_stages(run, client, ev, "01_plan"):
        yield event


async def resume_research(run_dir: str | Path, client: LLMClient, from_stage: str,
                          research_id: Optional[str] = None) -> AsyncIterator[ResearchEvent]:
    """Re-run an existing run from ``from_stage``, reading the (possibly edited)
    files the earlier stages left on disk. Approval gates build on this."""
    if from_stage not in runs.STAGES:
        raise ValueError(f"unknown stage {from_stage!r}; expected one of {runs.STAGES}")
    run = runs.open_run(run_dir)
    ev = EventFactory(research_id or run.state().get("research_id"))
    for stage in runs.STAGES[runs.STAGES.index(from_stage):]:
        run.set_stage(stage, "pending")
    run.path(runs.STOP_FILE).unlink(missing_ok=True)  # the human has acted on it
    async for event in _run_stages(run, client, ev, from_stage):
        yield event


async def decide(run_id: str, req: DecisionRequest, client: LLMClient) -> AsyncIterator[ResearchEvent]:
    """Apply a person's decision on a paused run, then stream the rest of it.

    approve -> resume; edit -> write ``edited_content`` to the artifact (diff logged
    in state.json), then resume; reject -> write REJECTED.md and close the run.
    """
    ev = EventFactory()
    try:
        run = runs.open_run_by_id(run_id)
    except FileNotFoundError:
        yield ev.error(f"No research run '{run_id}'.", code="run_not_found")
        return
    st = run.state()
    ev = EventFactory(st.get("research_id"))
    awaiting = st.get("awaiting")
    if not awaiting or awaiting["stage"] != req.stage:
        current = awaiting["stage"] if awaiting else "none"
        yield ev.error(f"This run is not waiting on {req.stage} (waiting on: {current}).",
                       code="stage_mismatch")
        return
    if req.action not in awaiting["allowed_actions"]:
        yield ev.error(f"'{req.action}' is not allowed here.", code="validation")
        return

    entry = {"stage": req.stage, "action": req.action, "reason": awaiting["reason"],
             "at": datetime.now(timezone.utc).isoformat(), "note": req.note or ""}

    if req.action == "edit":
        new = (req.edited_content or "").replace("\r\n", "\n")
        if awaiting["artifact"] == runs.PLAN_FILE and not runs.parse_plan(new):
            yield ev.error("The edited plan has no numbered sub-questions (e.g. '1. ...'). "
                           "Nothing was changed.", code="validation")
            return
        old = run.read(awaiting["artifact"])
        entry["diff"] = "".join(difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True),
            fromfile=f"{awaiting['artifact']} (before)", tofile=f"{awaiting['artifact']} (after)",
        ))
        run.write(awaiting["artifact"], new if new.endswith("\n") else new + "\n")

    # Clear the pause before doing anything slow, so a second click gets stage_mismatch.
    st = run.state()
    st["awaiting"] = None
    st["decisions"].append(entry)
    run.save_state(st)

    if req.action == "reject":
        run.write(runs.REJECTED_FILE, (
            f"# Rejected at {req.stage}\n\n"
            f"- at: {entry['at']}\n- reason shown: {awaiting['reason']}\n\n"
            f"{req.note or '(no note)'}\n"
        ))
        run.set_stage(req.stage, "rejected")
        run.trace(done := ev.done("rejected"))
        yield done
        return

    if req.action == "edit" and awaiting["artifact"] == runs.PLAN_FILE:
        plan_event = ev.plan(runs.parse_plan(run.read(runs.PLAN_FILE)))
        run.trace(plan_event)
        yield plan_event
    failed: Optional[ResearchEvent] = None
    async for event in resume_research(run.dir, client, awaiting["resume_from"]):
        if event.type == "error":  # e.g. a rejected key or a provider outage
            failed = event
            break
        yield event
    if failed is not None:
        # Put the same gate back so the person can retry; otherwise every later decision
        # would get stage_mismatch and the run would be stuck. Gate first, then the error,
        # so the UI keeps the review panel open and shows what went wrong.
        st = run.state()
        st["decisions"][-1]["failed"] = failed.message
        run.save_state(st)
        gate = _pause(run, ev, stage=awaiting["stage"], reason=awaiting["reason"],
                      allowed=awaiting["allowed_actions"])
        run.trace(gate)
        yield gate
        run.trace(failed)
        yield failed
