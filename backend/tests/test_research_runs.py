"""File-backed research stages: run folders, edit-then-resume, and the andon STOP."""
import asyncio
import json

import app.services.research as research_svc
import app.tools.deep_research as deep_research_tool
from app.models.research import ResearchRequest, Source
from app.services import runs


class FakeLLMClient:
    provider = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system, user, *, max_tokens=2000):
        self.calls.append((system, user))
        if system == research_svc.PLAN_SYSTEM:
            return '["What is X?", "What is Y?"]'
        return f"Grounded answer #{len(self.calls)}. (https://example.com)"

    async def stream(self, system, user, *, max_tokens=4000):
        self.calls.append((system, user))
        for t in ["# Report\n\n", "Body."]:
            yield t


def _req(**kw):
    body = {"query": "What is deep research?", "provider": "openai",
            "api_key": "sk-secret-abcdefgh", "max_subquestions": 2, "search": True}
    body.update(kw)
    return ResearchRequest(**body)


def _drain(agen):
    async def go():
        return [e async for e in agen]
    return asyncio.run(go())


def _only_run():
    dirs = [d for d in runs.runs_root().iterdir() if d.is_dir()]
    assert len(dirs) == 1
    return runs.open_run(dirs[0])


def _recording_search(seen: list[str], hits: bool = True):
    async def search(query, max_results=5):
        seen.append(query)
        if not hits:
            return []
        return [Source(title="Ex", url=f"https://example.com/{len(seen)}", snippet="s")]
    return search


def test_run_writes_every_stage_file(monkeypatch):
    monkeypatch.setattr(research_svc, "web_search", _recording_search([]))
    events = _drain(research_svc.run_research(_req(), FakeLLMClient()))
    assert events[-1].type == "done"

    run = _only_run()
    st = run.state()
    assert st["stage_status"] == {"01_plan": "done", "02_search": "done", "03_report": "done"}
    assert runs.parse_plan(run.read(runs.PLAN_FILE)) == ["What is X?", "What is Y?"]
    assert "**Status:** sourced" in run.read(runs.EVIDENCE_FILE)
    assert run.read(runs.REPORT_FILE).startswith("# Report")
    assert "What is deep research?" in run.read("question.md")

    # The API key never touches disk.
    for f in run.dir.rglob("*"):
        if f.is_file():
            assert "sk-secret" not in f.read_text(encoding="utf-8")
    # Trace has one line per non-token event.
    trace = [json.loads(l) for l in run.read("trace.jsonl").splitlines()]
    assert [t["type"] for t in trace] == [e.type for e in events if e.type != "token"]


def test_edited_plan_changes_what_gets_searched(monkeypatch):
    monkeypatch.setattr(research_svc, "web_search", _recording_search([]))
    _drain(research_svc.run_research(_req(), FakeLLMClient()))
    run = _only_run()

    # A human rewrites the plan: drops both model questions, adds three of their own.
    run.write(runs.PLAN_FILE, "# Plan\n\n1. Torque spec for M8 bolts?\n"
                              "2) Andon cord history\n3. Takt time formula\n")
    seen: list[str] = []
    monkeypatch.setattr(research_svc, "web_search", _recording_search(seen))
    client = FakeLLMClient()
    events = _drain(research_svc.resume_research(run.dir, client, "02_search"))

    assert seen == ["Torque spec for M8 bolts?", "Andon cord history", "Takt time formula"]
    assert not any(s == research_svc.PLAN_SYSTEM for s, _ in client.calls)  # no re-plan
    assert [e.data["subquestion"] for e in events if e.type == "finding"] == seen
    assert "Takt time formula" in run.read(runs.EVIDENCE_FILE)
    assert events[-1].type == "done"


def test_edited_evidence_is_what_the_report_sees(monkeypatch):
    monkeypatch.setattr(research_svc, "web_search", _recording_search([]))
    _drain(research_svc.run_research(_req(), FakeLLMClient()))
    run = _only_run()

    run.write(runs.EVIDENCE_FILE, "# Evidence\n\n## 1. Hand-checked\n\nSUPERVISOR NOTE 42\n")
    client = FakeLLMClient()
    _drain(research_svc.resume_research(run.dir, client, "03_report"))
    report_system, report_user = client.calls[-1]
    assert report_system == research_svc.REPORT_SYSTEM
    assert "SUPERVISOR NOTE 42" in report_user


def test_no_sources_anywhere_writes_stop_and_halts(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(research_svc, "web_search", _recording_search(seen, hits=False))
    client = FakeLLMClient()
    events = _drain(research_svc.run_research(_req(), client))

    assert events[-1].type == "error" and events[-1].data["code"] == "stop"
    assert not any(e.type in ("report", "done", "token") for e in events)
    # Only the planner was called: nothing was synthesized from general knowledge.
    assert [s for s, _ in client.calls] == [research_svc.PLAN_SYSTEM]
    run = _only_run()
    assert run.path(runs.STOP_FILE).exists()
    assert not run.path(runs.REPORT_FILE).exists()
    assert run.state()["stage_status"]["02_search"] == "stopped"

    # Once search works again, resuming clears the stop and finishes.
    monkeypatch.setattr(research_svc, "web_search", _recording_search([]))
    events = _drain(research_svc.resume_research(run.dir, FakeLLMClient(), "02_search"))
    assert events[-1].type == "done"
    assert not run.path(runs.STOP_FILE).exists()


def test_partial_gap_is_marked_not_guessed(monkeypatch):
    async def search(query, max_results=5):
        return [Source(title="Ex", url="https://example.com", snippet="s")] if "X" in query else []
    monkeypatch.setattr(research_svc, "web_search", search)
    client = FakeLLMClient()
    events = _drain(research_svc.run_research(_req(), client))

    assert events[-1].type == "done"
    assert sum(1 for s, _ in client.calls if s == research_svc.SYNTH_SYSTEM) == 1
    evidence = _only_run().read(runs.EVIDENCE_FILE)
    assert "GAP (no usable sources)" in evidence


def test_search_off_is_labelled_unsourced(monkeypatch):
    monkeypatch.setattr(research_svc, "web_search", _recording_search([]))
    events = _drain(research_svc.run_research(_req(search=False), FakeLLMClient()))
    assert events[-1].type == "done"
    assert "NOT source-backed" in _only_run().read(runs.EVIDENCE_FILE)


def test_parse_plan_reads_numbered_lines_only():
    text = "# Plan\n\nQuestion: 3 things?\n<!-- note -->\n1. A\n 2) B\n- not this\n10. C\n"
    assert runs.parse_plan(text) == ["A", "B", "C"]


def test_chat_tool_labels_unsourced_answers(monkeypatch):
    async def no_results(query, max_results=5):
        return []
    monkeypatch.setattr("app.services.search.web_search", no_results)
    spec = deep_research_tool.make_deep_research(FakeLLMClient())
    out = asyncio.run(spec.func(query="conveyor E42 fault"))
    assert out.startswith(deep_research_tool.UNSOURCED_BANNER)
