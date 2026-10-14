"""Stage evals: check_run holds each stage to its contract; replay re-runs on recorded evidence."""
import asyncio
import json
import os

import app.services.research as research_svc
from app.models.research import ResearchRequest, Source
from app.services import runs
from evals import stages


class FakeLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, report="# Report\n\nX is a thing (https://ex.com/1).\n"):
        self.report = report

    async def complete(self, system, user, *, max_tokens=2000):
        if system == research_svc.PLAN_SYSTEM:
            return '["What is X?", "What is Y?"]'
        return "Grounded answer (https://ex.com/1)."

    async def stream(self, system, user, *, max_tokens=4000):
        yield self.report


def _run(monkeypatch, hits=True, review=False, client=None):
    async def search(q, max_results=5):
        return [Source(title="Ex", url="https://ex.com/1", snippet="s")] if hits else []
    monkeypatch.setattr(research_svc, "web_search", search)
    req = ResearchRequest(query="What is deep research?", provider="openai",
                          api_key="sk-secret-abcdefgh-0123456789", max_subquestions=2,
                          review_plan=review)

    async def go():
        return [e async for e in research_svc.run_research(req, client or FakeLLM())]
    asyncio.run(go())
    # newest run by creation time (iterdir() order is undefined)
    return max((d for d in runs.runs_root().iterdir() if (d / "state.json").exists()),
               key=lambda d: json.loads((d / "state.json").read_text())["created_at"])


def _fails(checks):
    return {c.name for c in checks if c.status == "FAIL"}


def _warns(checks):
    return {c.name for c in checks if c.status == "WARN"}


def test_clean_run_passes_every_check(monkeypatch):
    checks = stages.check_run(_run(monkeypatch))
    assert _fails(checks) == set() and _warns(checks) == set()
    assert {c.stage for c in checks} == {"run", "01_plan", "02_search", "03_report"}


def test_stopped_and_paused_runs_pass(monkeypatch):
    assert _fails(stages.check_run(_run(monkeypatch, hits=False))) == set()
    assert _fails(stages.check_run(_run(monkeypatch, review=True))) == set()


def test_plan_edited_after_search_is_caught(monkeypatch):
    d = _run(monkeypatch)
    run = runs.open_run(d)
    run.write(runs.PLAN_FILE, "# Plan\n\n1. Something else entirely\n")
    assert "evidence matches the plan (same sub-questions, same order)" in _fails(stages.check_run(d))


def test_invented_citations_are_caught(monkeypatch):
    d = _run(monkeypatch, client=FakeLLM(report="# R\n\nSee https://made-up.example/paper.\n"))
    assert "cites only URLs from the evidence" in _fails(stages.check_run(d))

    run = runs.open_run(d)
    ev = run.read(runs.EVIDENCE_FILE).replace("(https://ex.com/1).", "(https://ghost.example/x).", 1)
    run.write(runs.EVIDENCE_FILE, ev)
    assert "#1 cites only URLs that search returned" in _fails(stages.check_run(d))


def test_key_on_disk_and_stage_order_are_caught(monkeypatch):
    d = _run(monkeypatch)
    run = runs.open_run(d)
    with run.path("trace.jsonl").open("a") as f:
        f.write('{"leak": "sk-proj-ABCDEFGHIJKLMNOPQRST"}\n')
    st = run.state()
    st["stage_status"]["01_plan"] = "pending"
    run.save_state(st)
    fails = _fails(stages.check_run(d))
    assert "no API key on disk" in fails
    assert "02_search ran after 01_plan" in fails


def test_all_gaps_without_stop_and_stale_report(monkeypatch):
    d = _run(monkeypatch)
    run = runs.open_run(d)
    run.write(runs.EVIDENCE_FILE, run.read(runs.EVIDENCE_FILE).replace("**Status:** sourced", "**Status:** GAP (no usable sources)"))
    later = run.path(runs.REPORT_FILE).stat().st_mtime + 10
    os.utime(run.path(runs.EVIDENCE_FILE), (later, later))
    checks = stages.check_run(d)
    assert "all gaps -> STOP.md (andon)" in _fails(checks)
    assert "report is newer than evidence.md" in _warns(checks)


def test_replay_uses_recorded_search_and_diffs_without_touching_original(monkeypatch):
    d = _run(monkeypatch)
    before = {p.name: p.read_bytes() for p in d.rglob("*") if p.is_file()}

    async def no_network(*a, **k):
        raise AssertionError("replay must not hit live search")
    monkeypatch.setattr(research_svc, "web_search", no_network)

    new = FakeLLM(report="# Report v2\n\nTighter (https://ex.com/1).\n")
    res = asyncio.run(stages.replay(d, new, "02_search"))

    assert res["search_calls"] == ["What is X?", "What is Y?"]
    assert list(res["diffs"]) == [runs.REPORT_FILE]
    assert "+# Report v2" in res["diffs"][runs.REPORT_FILE]
    assert _fails(res["checks"]) == set()
    replay_dir = res["dir"]
    assert replay_dir.parent.name == "_replays"
    assert "Replay of" in (replay_dir / "REPLAY.md").read_text()
    assert json.loads((replay_dir / "state.json").read_text())["replay_of"] == d.name
    assert {p.name: p.read_bytes() for p in d.rglob("*") if p.is_file()} == before  # original untouched


def test_cli_check_exit_codes(monkeypatch, capsys):
    # main() reads backend/.env like the CLI; don't let a developer's .env leak into other tests.
    monkeypatch.setattr("app.cli._load_dotenv", lambda: None)
    d = _run(monkeypatch)
    assert stages.main(["check"]) == 0
    runs.open_run(d).write(runs.PLAN_FILE, "# Plan\n\n1. Changed\n")
    assert stages.main(["check", str(d)]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_run_dir_accepts_latest_id_or_path(monkeypatch):
    import time
    first = _run(monkeypatch)
    time.sleep(1.1)
    second = _run(monkeypatch)
    os.utime(second, None)
    assert stages.resolve_run_dir("latest") == second
    assert stages.resolve_run_dir(first.name) == runs.runs_root() / first.name
    assert stages.resolve_run_dir(str(first)) == first
    import pytest
    with pytest.raises(SystemExit):
        stages.resolve_run_dir("no-such-run")
