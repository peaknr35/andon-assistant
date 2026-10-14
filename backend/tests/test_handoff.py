"""Shift handoff workflow: stages, gates, cite-or-abstain checks, run listing, stage evals."""
import json

import app.routes.handoff as handoff_route
from app.services import handoff, runs
from evals import stages

KEY = "sk-secret-handoff-0123456789"
NOTES = """Line 4, night shift, supervisor J. Ramos.
Near miss at station 6: forklift came round the blind corner, no one hurt.
Torque gun T-12 drifting high, 3 parts quarantined in red bin.
Ran 412 of 450 planned.
Conveyor C2 jammed twice, 35 min total down, maintenance ticket 8812 open.
Maria covering for Ken on the press, Ken back tomorrow.
Something odd with the label printer, not sure if it matters.
"""

SUMMARY = """## Safety
- Forklift near miss at station 6 blind corner, no injuries [L2]
## Quality
- Torque gun T-12 drifting high; 3 parts quarantined [L3]
## Production
- 412 of 450 units [L4]
## Downtime & maintenance
- C2 jammed twice, 35 min, ticket 8812 open [L5]
## People & staffing
- Maria covering press for Ken until tomorrow [L6]
## Unclear -- ask the outgoing shift
- Label printer issue, impact unknown [L7]
"""
ISSUES = """## Open issues
| # | Issue | Category | Severity | Evidence | Owner | Next action |
|---|---|---|---|---|---|---|
| 1 | Forklift blind corner | Safety | High | [L2] | unassigned | Add mirror |
| 2 | T-12 torque drift | Quality | High | [L3] | unassigned | Recalibrate |
## Risks for next shift
- C2 may jam again [L5]
"""
BRIEF = """# Next-shift brief -- Line 4, Night
## Safety first
- Watch the station 6 blind corner [L2]
## Top priorities (max 3)
- Recalibrate T-12 before running [L3]
## Handover
Outgoing: ________  Incoming: ________  Time: ________
"""


class FakeLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, summary=SUMMARY):
        self.summary = summary
        self.prompts = []

    async def complete(self, system, user, *, max_tokens=2000):
        return ""

    async def stream(self, system, user, *, max_tokens=4000):
        self.prompts.append((system, user))
        if system.startswith("You turn a production supervisor"):
            text = "```markdown\n" + self.summary + "```"  # fenced, like models often do
        elif system.startswith("You extract open issues"):
            text = ISSUES
        else:
            text = BRIEF
        for i in range(0, len(text), 25):
            yield text[i:i + 25]


def _events(resp):
    out = []
    for line in resp.iter_lines():
        if isinstance(line, bytes):
            line = line.decode()
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    return out


def _start(client, monkeypatch, notes=NOTES, fake=None):
    fake = fake or FakeLLM()
    monkeypatch.setattr(handoff_route, "build_client", lambda *a, **k: fake)
    body = {"notes": notes, "line": "Line 4", "shift": "Night", "supervisor": "J. Ramos",
            "provider": "anthropic", "api_key": KEY}
    with client.stream("POST", "/handoff/stream", json=body) as resp:
        assert resp.status_code == 200
        return _events(resp), fake


def _decide(client, run_id, stage, action, **extra):
    body = {"stage": stage, "action": action, "provider": "anthropic", "api_key": KEY, **extra}
    with client.stream("POST", f"/handoff/runs/{run_id}/decision", json=body) as resp:
        return _events(resp)


def test_full_handoff_with_edits_at_both_gates(client, monkeypatch):
    events, fake = _start(client, monkeypatch)
    types = [e["type"] for e in events]
    assert types[-2:] == ["await_approval", "done"] and events[-1]["data"]["status"] == "paused"
    assert "token" in types and "stage_output" in types
    gate = events[-2]["data"]
    run_id = gate["run_id"]
    assert gate["stage"] == "02_summary" and gate["next_stage"] == "03_issues"
    assert gate["artifact_content"] == SUMMARY  # code fence stripped
    assert gate["citation_warnings"] == []
    assert "L2: Near miss at station 6" in fake.prompts[0][1]  # model saw numbered notes
    assert "Andon" in fake.prompts[0][0]  # plant glossary from workflows/shift_handoff/references

    # Supervisor fixes the summary; the issues stage must read the edited file.
    edited = SUMMARY.replace("Maria covering press for Ken until tomorrow", "Maria on press (Ken off)")
    after = _decide(client, run_id, "02_summary", "edit", edited_content=edited, note="names")
    assert after[-2]["type"] == "await_approval" and after[-2]["data"]["stage"] == "03_issues"
    assert "Maria on press (Ken off)" in fake.prompts[1][1]

    final = _decide(client, run_id, "03_issues", "approve")
    assert final[-1]["type"] == "done" and final[-1]["data"]["status"] == "complete"
    assert final[-1]["data"]["brief"] == BRIEF
    assert ISSUES.strip() in fake.prompts[2][1] and "Maria on press" in fake.prompts[2][1]
    assert "Next-shift brief -- Line 4, Night" in fake.prompts[2][0]  # format.md filled in

    run = runs.open_run_by_id(run_id)
    st = run.state()
    assert st["stage_status"] == {s: "done" for s in handoff.STAGES}
    assert [d["action"] for d in st["decisions"]] == ["edit", "approve"]
    assert "+- Maria on press (Ken off) [L6]" in st["decisions"][0]["diff"]
    assert run.read(handoff.NOTES_FILE) == NOTES  # verbatim
    assert run.path("references/glossary.md").exists() and run.path("references/format.md").exists()
    for f in run.dir.rglob("*"):
        if f.is_file():
            assert KEY not in f.read_text(encoding="utf-8")

    checks = stages.check_run(run.dir)
    assert {c.status for c in checks} == {"PASS"}, [c for c in checks if c.status != "PASS"]


def test_bad_and_missing_citations_are_shown_at_the_gate(client, monkeypatch):
    bad = SUMMARY.replace("[L4]", "[L40]").replace(" [L6]", "")
    events, _ = _start(client, monkeypatch, fake=FakeLLM(summary=bad))
    warnings = events[-2]["data"]["citation_warnings"]
    assert any("Cites L40 but the notes have 7 lines" in w for w in warnings)
    assert any(w.startswith("No note line cited") and "Maria" in w for w in warnings)
    # The supervisor approves anyway -> the run is still flagged by the stage check.
    run_id = events[-2]["data"]["run_id"]
    _decide(client, run_id, "02_summary", "approve")
    fails = {c.name for c in stages.check_run(runs.open_run_by_id(run_id).dir) if c.status == "FAIL"}
    assert "cites only note lines that exist" in fails


def test_thin_notes_stop_before_any_model_call(client, monkeypatch):
    events, fake = _start(client, monkeypatch, notes="All good, nothing to report.")
    assert events[-1]["type"] == "error" and events[-1]["data"]["code"] == "stop"
    assert fake.prompts == []
    run = max((d for d in runs.runs_root().iterdir() if (d / "state.json").exists()),
              key=lambda d: json.loads((d / "state.json").read_text())["created_at"])
    assert (run / handoff.STOP_FILE).exists()
    assert {c.status for c in stages.check_run(run)} == {"PASS"}


def test_reject_mismatch_and_unknown_runs(client, monkeypatch):
    events, fake = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    assert _decide(client, run_id, "03_issues", "approve")[-1]["data"]["code"] == "stage_mismatch"
    assert _decide(client, run_id, "02_summary", "edit", edited_content="  ")[-1]["data"]["code"] == "validation"
    out = _decide(client, run_id, "02_summary", "reject", note="wrong line")
    assert out[-1]["data"]["status"] == "rejected" and len(fake.prompts) == 1
    assert "wrong line" in runs.open_run_by_id(run_id).read(handoff.REJECTED_FILE)
    assert _decide(client, run_id, "02_summary", "approve")[-1]["data"]["code"] == "stage_mismatch"
    assert _decide(client, "nope", "02_summary", "approve")[-1]["data"]["code"] == "run_not_found"


def test_research_and_handoff_runs_dont_cross(client, monkeypatch):
    events, _ = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    body = {"stage": "02_summary", "action": "approve", "provider": "openai", "api_key": KEY}
    import app.routes.research as research_route
    monkeypatch.setattr(research_route, "build_client", lambda *a, **k: FakeLLM())
    with client.stream("POST", f"/research/runs/{run_id}/decision", json=body) as resp:
        assert _events(resp)[-1]["data"]["code"] == "run_not_found"


def test_list_and_load_runs_for_resuming(client, monkeypatch):
    events, _ = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    listed = client.get("/handoff/runs").json()["runs"]
    assert listed[0]["run_id"] == run_id and listed[0]["status"] == "awaiting 02_summary"
    detail = client.get(f"/handoff/runs/{run_id}").json()
    assert detail["awaiting"]["stage"] == "02_summary"
    assert detail["awaiting"]["artifact_content"] == SUMMARY
    assert detail["files"][handoff.NOTES_FILE] == NOTES
    assert client.get("/handoff/runs/nope").status_code == 404


def test_citation_parser_ranges_and_none_lines():
    md = ("- A thing [L2-L4]\n- Another [L3, L9]\n- None noted.\n| 1 | x | Safety | High | [L1] |\n"
          "|---|---|\n| # | Issue | Category |\n- Uncited item here\n")
    w = handoff.check_citations(md, 8)
    assert w == ['Cites L9 but the notes have 8 lines: "Another [L3, L9]"',
                 'No note line cited: "Uncited item here"']
    assert handoff._refs("[L2-L4]") == [2, 3, 4] and handoff._refs("[L5, L7]") == [5, 7]


def test_failed_stage_after_a_decision_restores_the_gate(client, monkeypatch):
    from app.providers.base import ProviderError

    events, fake = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]

    class BadKey(FakeLLM):
        async def stream(self, system, user, *, max_tokens=4000):
            raise ProviderError("Invalid or unauthorized API key.", code="auth", status=401)
            yield ""

    monkeypatch.setattr(handoff_route, "build_client", lambda *a, **k: BadKey())
    after = _decide(client, run_id, "02_summary", "edit", edited_content=SUMMARY + "- Extra [L1]\n")
    assert [e["type"] for e in after][-2:] == ["await_approval", "error"]
    assert after[-2]["data"]["stage"] == "02_summary" and "- Extra [L1]" in after[-2]["data"]["artifact_content"]
    st = runs.open_run_by_id(run_id).state()
    assert st["awaiting"]["stage"] == "02_summary" and st["decisions"][-1]["failed"]

    monkeypatch.setattr(handoff_route, "build_client", lambda *a, **k: fake)
    again = _decide(client, run_id, "02_summary", "approve")
    assert again[-2]["data"]["stage"] == "03_issues"
