"""Controlled memory promotion: candidates/ review step + the facts.md mirror."""
import pytest

import app.agent.loop as loop_mod
from app import cli
from app.config import get_settings
from app.memory import candidates, store


class FakeClient:
    """Answers directly; the consolidation gate picks two facts."""
    provider = "openai"
    model = "fake-model"

    def __init__(self, picks='["Prefers metric units", "Works the night shift on line 4"]'):
        self.picks = picks

    async def complete(self, system, user, *, max_tokens=2000):
        if "worth remembering" in system:
            return self.picks
        return '{"final": "Noted."}'

    async def stream(self, system, user, *, max_tokens=4000):
        yield "x"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "state.db"))
    monkeypatch.setenv("APP_AGENT_BACKEND", "manual")
    monkeypatch.setenv("APP_MEMORY_REVIEW", "1")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


async def _turn(monkeypatch, client=None, message="I work nights and use metric"):
    monkeypatch.setattr(loop_mod, "build_client", lambda *a, **k: client or FakeClient())
    return [e async for e in loop_mod.run_turn(message=message, provider="openai", api_key="x" * 8)]


def _mem(events, name):
    return [e.data["items"] for e in events if e.type == "memory" and e.name == name]


async def test_review_off_saves_directly_and_mirrors(env):
    env.setenv("APP_MEMORY_REVIEW", "0")
    get_settings.cache_clear()
    events = await _turn(env)
    assert _mem(events, "save") == [["Prefers metric units", "Works the night shift on line 4"]]
    assert {f["source"] for f in store.all_facts()} == {"auto"}
    mirror = (candidates.memory_dir() / "facts.md").read_text(encoding="utf-8")
    assert "Prefers metric units" in mirror and "(auto," in mirror
    assert not list(candidates.candidates_dir().glob("*.md"))


async def test_review_on_proposes_instead_of_saving(env):
    events = await _turn(env)
    assert _mem(events, "propose") == [["Prefers metric units", "Works the night shift on line 4"]]
    assert not _mem(events, "save")
    assert store.all_facts() == []           # nothing saved...
    assert store.recall("metric") == []      # ...so nothing recalled
    pend = candidates.pending()
    assert [c.text for c in pend] == ["Prefers metric units", "Works the night shift on line 4"]
    assert pend[0].reason.startswith("from: I work nights")
    assert "status: pending" in pend[0].path.read_text(encoding="utf-8")
    assert events[-1].type == "done"


async def test_approve_with_edit_and_reject_over_http(env, client):
    await _turn(env)
    listed = client.get("/memory/candidates").json()
    assert listed["review"] is True and len(listed["candidates"]) == 2
    a, b = listed["candidates"]

    r = client.post(f"/memory/candidates/{a['id']}", json={"action": "approve", "text": "Uses metric units"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r = client.post(f"/memory/candidates/{b['id']}", json={"action": "reject"})
    assert r.json()["status"] == "rejected"

    facts = store.all_facts()
    assert [(f["text"], f["source"]) for f in facts] == [("Uses metric units", "reviewed")]
    assert store.recall("metric")
    d = candidates.candidates_dir()
    assert (d / "_done" / f"{a['id']}.md").exists() and (d / "_rejected" / f"{b['id']}.md").exists()
    assert "Uses metric units" in (candidates.memory_dir() / "facts.md").read_text(encoding="utf-8")
    assert client.get("/memory").json()["pending_candidates"] == 0

    # Deciding twice, or on an unknown / malformed id, is a 404.
    assert client.post(f"/memory/candidates/{a['id']}", json={"action": "approve"}).status_code == 404
    assert client.post("/memory/candidates/nope", json={"action": "reject"}).status_code == 404


async def test_rejected_or_known_facts_are_not_proposed_again(env):
    await _turn(env)
    first, second = candidates.pending()
    candidates.decide(first.id, "reject")
    candidates.decide(second.id, "approve")
    events = await _turn(env)  # the model picks the same two facts again
    assert not _mem(events, "propose")
    assert candidates.pending() == []


async def test_hand_edited_file_is_promoted_next_turn(env):
    await _turn(env)
    c = candidates.pending()[0]
    raw = c.path.read_text(encoding="utf-8")
    edited = raw.replace("status: pending", "status: approved").replace(
        "Prefers metric units", "Prefers metric units (mm, N·m)")
    c.path.write_bytes(edited.replace("\n", "\r\n").encode("utf-8"))  # Windows editor

    events = await _turn(env, FakeClient(picks="[]"))
    assert _mem(events, "promote") == [["Prefers metric units (mm, N·m)"]]
    assert [f["text"] for f in store.all_facts()] == ["Prefers metric units (mm, N·m)"]
    assert len(candidates.pending()) == 1


async def test_malformed_candidate_is_skipped_not_crashed(env, client):
    await _turn(env)
    (candidates.candidates_dir() / "20260101T000000_abcdef.md").write_text("no front matter")
    (candidates.candidates_dir() / "20260101T000001_abcdef.md").write_text(
        "---\nstatus: maybe\n---\ntext\n")
    events = await _turn(env, FakeClient(picks="[]"))
    assert events[-1].type == "done"
    assert len(client.get("/memory/candidates").json()["candidates"]) == 2


async def test_remember_tool_still_saves_directly(env):
    class Remembers(FakeClient):
        step = 0

        async def complete(self, system, user, *, max_tokens=2000):
            if "worth remembering" in system:
                return "[]"
            self.step += 1
            if self.step == 1:
                return '{"tool": "remember", "args": {"text": "Badge number 4471"}}'
            return '{"final": "Saved."}'

    await _turn(env, Remembers(), "remember my badge is 4471")
    assert [(f["text"], f["source"]) for f in store.all_facts()] == [("Badge number 4471", "explicit")]
    assert "Badge number 4471" in (candidates.memory_dir() / "facts.md").read_text(encoding="utf-8")


def test_review_off_endpoints_say_so(client):
    assert client.get("/memory/candidates").json() == {"review": False, "candidates": [], "folder": None}
    assert client.get("/memory").json()["review"] is False


async def test_cli_review_commands(env):
    await _turn(env)
    cli._review_command("/reject 2")
    cli._review_command("/approve all")
    assert [f["text"] for f in store.all_facts()] == ["Prefers metric units"]
    assert candidates.pending() == []
    cli._review_command("/approve 9")  # out of range: message, no crash
