"""Approval gates: await_approval -> POST /research/runs/{id}/decision (approve/edit/reject)."""
import json

import app.routes.research as research_route
import app.services.research as research_svc
from app.models.research import Source
from app.services import runs


class FakeLLMClient:
    provider = "fake"
    model = "fake-model"

    async def complete(self, system, user, *, max_tokens=2000):
        if system == research_svc.PLAN_SYSTEM:
            return '["What is X?", "What is Y?"]'
        return "Grounded answer. (https://example.com)"

    async def stream(self, system, user, *, max_tokens=4000):
        for t in ["# Report\n\n", "Body."]:
            yield t


KEY = "sk-secret-abcdefgh"


def _events(resp):
    out = []
    for line in resp.iter_lines():
        if isinstance(line, bytes):
            line = line.decode()
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def _searcher(seen, hits=True):
    async def search(query, max_results=5):
        seen.append(query)
        return [Source(title="Ex", url=f"https://ex.com/{len(seen)}", snippet="s")] if hits else []
    return search


def _start(client, monkeypatch, *, hits=True, review=True):
    monkeypatch.setattr(research_route, "build_client", lambda *a, **k: FakeLLMClient())
    seen: list[str] = []
    monkeypatch.setattr(research_svc, "web_search", _searcher(seen, hits))
    body = {"query": "What is deep research?", "provider": "openai", "api_key": KEY,
            "max_subquestions": 2, "search": True, "review_plan": review}
    with client.stream("POST", "/research/stream", json=body) as resp:
        return _events(resp), seen


def _decide(client, run_id, **body):
    payload = {"provider": "openai", "api_key": KEY, "stage": "01_plan", **body}
    with client.stream("POST", f"/research/runs/{run_id}/decision", json=payload) as resp:
        assert resp.status_code == 200
        return _events(resp)


def test_review_pauses_after_plan_before_any_search(client, monkeypatch):
    events, seen = _start(client, monkeypatch)
    types = [e["type"] for e in events]
    assert types[-2:] == ["await_approval", "done"]
    assert events[-1]["data"] == {"status": "paused"}
    assert seen == [] and "sources" not in types

    gate = events[-2]["data"]
    assert gate["stage"] == "01_plan" and gate["next_stage"] == "02_search"
    assert gate["reason"] == "review"
    assert gate["allowed_actions"] == ["approve", "edit", "reject"]
    assert "1. What is X?" in gate["artifact_content"]

    run = runs.open_run_by_id(gate["run_id"])
    assert run.state()["awaiting"]["stage"] == "01_plan"
    for f in run.dir.rglob("*"):
        if f.is_file():
            assert KEY not in f.read_text(encoding="utf-8")


def test_approve_resumes_with_the_plan_as_written(client, monkeypatch):
    events, seen = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    after = _decide(client, run_id, action="approve")
    assert after[-1]["type"] == "done" and after[-1]["data"] is None
    assert seen == ["What is X?", "What is Y?"]
    assert any(e["type"] == "report" for e in after)
    assert len({e["research_id"] for e in events + after}) == 1  # one run, one id
    st = runs.open_run_by_id(run_id).state()
    assert st["awaiting"] is None
    assert st["decisions"][0]["action"] == "approve"


def test_edit_replaces_plan_logs_diff_and_searches_the_edit(client, monkeypatch):
    events, seen = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    after = _decide(client, run_id, action="edit", note="tighter",
                    edited_content="# Plan\r\n\r\n1. Andon cord origin\r\n2. Jidoka today\r\n")
    assert after[0]["type"] == "plan"
    assert after[0]["data"]["subquestions"] == ["Andon cord origin", "Jidoka today"]
    assert seen == ["Andon cord origin", "Jidoka today"]
    assert after[-1]["type"] == "done"

    run = runs.open_run_by_id(run_id)
    assert "\r" not in run.read(runs.PLAN_FILE)
    d = run.state()["decisions"][0]
    assert d["action"] == "edit" and d["note"] == "tighter"
    assert "-1. What is X?" in d["diff"] and "+1. Andon cord origin" in d["diff"]


def test_reject_closes_the_run_without_searching(client, monkeypatch):
    events, seen = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    after = _decide(client, run_id, action="reject", note="wrong question")
    assert [e["type"] for e in after] == ["done"]
    assert after[0]["data"] == {"status": "rejected"}
    assert seen == []
    run = runs.open_run_by_id(run_id)
    assert "wrong question" in run.read(runs.REJECTED_FILE)
    assert run.state()["stage_status"]["01_plan"] == "rejected"


def test_second_decision_and_wrong_stage_are_refused(client, monkeypatch):
    events, _ = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    wrong = _decide(client, run_id, action="approve", stage="02_search")
    assert wrong[-1]["data"]["code"] == "stage_mismatch"
    _decide(client, run_id, action="approve")
    again = _decide(client, run_id, action="approve")
    assert again[-1]["type"] == "error" and again[-1]["data"]["code"] == "stage_mismatch"


def test_unknown_or_escaping_run_id_is_not_found(client, monkeypatch, tmp_path):
    monkeypatch.setattr(research_route, "build_client", lambda *a, **k: FakeLLMClient())
    for bad in ["nope", ".hidden"]:
        out = _decide(client, bad, action="approve")
        assert out[-1]["data"]["code"] == "run_not_found", bad

    # Ids that try to leave the runs folder never resolve, even if a state.json exists there.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "state.json").write_text("{}")
    for bad in ["..", "../outside", "..\\outside", str(outside), "a/../../outside", ""]:
        try:
            runs.open_run_by_id(bad)
        except FileNotFoundError:
            continue
        raise AssertionError(f"escaped: {bad!r}")


def test_edit_without_numbered_lines_changes_nothing(client, monkeypatch):
    events, seen = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]
    before = runs.open_run_by_id(run_id).read(runs.PLAN_FILE)
    out = _decide(client, run_id, action="edit", edited_content="just some prose")
    assert out[-1]["data"]["code"] == "validation"
    run = runs.open_run_by_id(run_id)
    assert run.read(runs.PLAN_FILE) == before
    assert run.state()["awaiting"]["stage"] == "01_plan"  # still paused, can try again
    assert seen == []


def test_stop_under_review_pauses_instead_of_erroring_then_retry(client, monkeypatch):
    # Approve the plan, but search finds nothing -> andon stop handed to the person.
    events, _ = _start(client, monkeypatch, hits=False)
    run_id = events[-2]["data"]["run_id"]
    after = _decide(client, run_id, action="approve")
    gate = after[-2]
    assert gate["type"] == "await_approval" and after[-1]["data"] == {"status": "paused"}
    assert gate["data"]["reason"] == "stop" and gate["data"]["stage"] == "02_search"
    assert "STOP: no evidence" in gate["data"]["stop_reason"]
    assert not any(e["type"] == "error" for e in after)

    # Search recovers; the person retries (approve) -> the run finishes.
    seen: list[str] = []
    monkeypatch.setattr(research_svc, "web_search", _searcher(seen))
    final = _decide(client, run_id, action="approve", stage="02_search")
    assert final[-1]["type"] == "done" and final[-1]["data"] is None
    assert seen == ["What is X?", "What is Y?"]
    assert not runs.open_run_by_id(run_id).path(runs.STOP_FILE).exists()


def test_without_review_nothing_pauses(client, monkeypatch):
    events, seen = _start(client, monkeypatch, review=False)
    assert "await_approval" not in [e["type"] for e in events]
    assert events[-1]["type"] == "done" and seen


def test_failed_resume_restores_the_gate_so_it_can_be_retried(client, monkeypatch):
    from app.providers.base import ProviderError

    events, seen = _start(client, monkeypatch)
    run_id = events[-2]["data"]["run_id"]

    class BadKey(FakeLLMClient):
        async def complete(self, system, user, *, max_tokens=2000):
            raise ProviderError("Invalid or unauthorized API key.", code="auth", status=401)

    monkeypatch.setattr(research_route, "build_client", lambda *a, **k: BadKey())
    after = _decide(client, run_id, action="edit",
                    edited_content="# Plan\n\n1. Andon cord origin\n")
    assert [e["type"] for e in after][-2:] == ["await_approval", "error"]
    assert after[-1]["data"]["code"] == "auth"
    gate = after[-2]["data"]
    assert gate["stage"] == "01_plan" and "1. Andon cord origin" in gate["artifact_content"]
    st = runs.open_run_by_id(run_id).state()
    assert st["awaiting"]["stage"] == "01_plan"
    assert st["decisions"][-1]["failed"] == "Invalid or unauthorized API key."

    # Fixed key: the same gate accepts a retry and the run finishes on the edited plan.
    monkeypatch.setattr(research_route, "build_client", lambda *a, **k: FakeLLMClient())
    final = _decide(client, run_id, action="approve")
    assert final[-1]["type"] == "done" and "Andon cord origin" in seen


def test_failed_retry_after_a_stop_restores_the_stop_gate(client, monkeypatch):
    from app.providers.base import ProviderError

    events, _ = _start(client, monkeypatch, hits=False)
    run_id = events[-2]["data"]["run_id"]
    _decide(client, run_id, action="approve")  # -> andon stop gate at 02_search
    monkeypatch.setattr(research_svc, "web_search", _searcher([]))

    class Down(FakeLLMClient):
        async def complete(self, system, user, *, max_tokens=2000):
            raise ProviderError("Could not reach the provider.", code="provider")

    monkeypatch.setattr(research_route, "build_client", lambda *a, **k: Down())
    after = _decide(client, run_id, action="approve", stage="02_search")
    assert after[-2]["type"] == "await_approval" and after[-2]["data"]["reason"] == "stop"
    assert after[-1]["data"]["code"] == "provider"
    assert runs.open_run_by_id(run_id).state()["awaiting"]["stage"] == "02_search"
