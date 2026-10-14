"""AI judge for reports + replay through the real provider SDKs (HTTP mocked, no network)."""
import asyncio
import json

import httpx
import pytest
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

import app.services.research as research_svc
from app.models.research import ResearchRequest, Source
from app.providers.base import build_client
from app.services import runs
from evals import stages

REPORT = (
    "# Report\n\n## Summary\n"
    "An andon cord lets any operator stop the line on a defect (https://ex.com/1). "
    "Toyota introduced the practice in the 1950s at its main plant.\n\n"
    "- Response teams arrive within sixty seconds on most lines.\n\n"
    "## Sources\n- [Ex](https://ex.com/1)\n"
)


class FakeLLM:
    provider = "fake"
    model = "fake"

    def __init__(self, verdicts=None, report=REPORT):
        self.verdicts = verdicts
        self.report = report
        self.judge_calls = 0

    async def complete(self, system, user, *, max_tokens=2000):
        if system == stages.JUDGE_SYSTEM:
            self.judge_calls += 1
            return self.verdicts if isinstance(self.verdicts, str) else json.dumps(self.verdicts)
        if system == research_svc.PLAN_SYSTEM:
            return '["What is an andon cord?"]'
        return "Any operator can stop the line (https://ex.com/1)."

    async def stream(self, system, user, *, max_tokens=4000):
        yield self.report


def _make_run(monkeypatch, client=None):
    async def search(q, max_results=5):
        return [Source(title="Ex", url="https://ex.com/1", snippet="operators stop the line")]
    monkeypatch.setattr(research_svc, "web_search", search)
    req = ResearchRequest(query="How does andon work?", provider="openai",
                          api_key="sk-test-abcdefgh", max_subquestions=1)

    async def go():
        return [e async for e in research_svc.run_research(req, client or FakeLLM())]
    asyncio.run(go())
    return [d for d in runs.runs_root().iterdir() if (d / "state.json").exists()][-1]


def _status(j, name_start):
    return next(c.status for c in j["checks"] if c.name.startswith(name_start))


def test_split_claims_skips_headings_sources_and_fragments():
    assert stages.split_claims(REPORT) == [
        "An andon cord lets any operator stop the line on a defect (https://ex.com/1).",
        "Toyota introduced the practice in the 1950s at its main plant.",
        "Response teams arrive within sixty seconds on most lines.",
    ]


def test_judge_scores_and_flags(monkeypatch):
    d = _make_run(monkeypatch)
    before = sorted(p.name for p in d.rglob("*"))
    j = asyncio.run(stages.judge_report(d, FakeLLM(verdicts=[
        {"id": 1, "verdict": "supported", "block": 1, "why": "block 1 says so"},
        {"id": 2, "verdict": "unsupported", "block": None, "why": "no date in evidence"},
        {"id": 3, "verdict": "contradicted", "block": 1, "why": "evidence says minutes"},
    ])))
    assert j["counts"]["supported"] == 1 and j["counts"]["unsupported"] == 1
    assert _status(j, "no claim contradicts") == "FAIL"
    assert _status(j, "unsupported claims") == "FAIL"  # 1/3 > 20%
    assert j["score"] == pytest.approx(1 / 3)
    md = stages.render_judgement(j)
    assert "| 2 | unsupported |" in md and "grounded score: 33%" in md
    assert sorted(p.name for p in d.rglob("*")) == before  # judging never writes into the run


def test_judge_all_supported_passes_and_threshold_is_tunable(monkeypatch):
    d = _make_run(monkeypatch)
    ok = [{"id": i, "verdict": "supported"} for i in (1, 2, 3)]
    j = asyncio.run(stages.judge_report(d, FakeLLM(verdicts=ok)))
    assert {c.status for c in j["checks"]} == {"PASS"} and j["score"] == 1.0

    one_bad = [{"id": 1, "verdict": "supported"}, {"id": 2, "verdict": "supported"},
               {"id": 3, "verdict": "unsupported"}]
    loose = asyncio.run(stages.judge_report(d, FakeLLM(verdicts=one_bad), max_unsupported=0.5))
    assert _status(loose, "unsupported claims") == "WARN"


def test_judge_survives_garbage_and_missing_ids(monkeypatch):
    d = _make_run(monkeypatch)
    j = asyncio.run(stages.judge_report(d, FakeLLM(verdicts="I think it's mostly fine!")))
    assert j["counts"]["unjudged"] == 3 and _status(j, "every claim judged") == "WARN"
    j = asyncio.run(stages.judge_report(d, FakeLLM(verdicts=[{"id": 2, "verdict": "SUPPORTED"},
                                                             {"id": "x"}, {"id": 3, "verdict": "maybe"}])))
    assert [c["verdict"] for c in j["claims"]] == ["unjudged", "supported", "unjudged"]


def test_judge_batches_long_reports(monkeypatch):
    long_report = "# R\n\n" + "\n".join(f"- Claim number {i} is about the line speed." for i in range(1, 31))
    d = _make_run(monkeypatch, FakeLLM(report=long_report))
    client = FakeLLM(verdicts=[{"id": i, "verdict": "supported"} for i in range(1, 31)])
    j = asyncio.run(stages.judge_report(d, client, batch=25))
    assert client.judge_calls == 2 and len(j["claims"]) == 30
    assert j["counts"]["supported"] == 30


def test_cli_judge_writes_to_evals_folder(monkeypatch, capsys):
    monkeypatch.setattr("app.cli._load_dotenv", lambda: None)
    d = _make_run(monkeypatch)
    monkeypatch.setenv("APP_API_KEY", "sk-test-abcdefgh")
    monkeypatch.setattr("app.providers.base.build_client",
                        lambda *a, **k: FakeLLM(verdicts=[{"id": i, "verdict": "supported"} for i in (1, 2, 3)]))
    assert stages.main(["judge", str(d)]) == 0
    out = list((runs.runs_root() / "_evals").glob(f"{d.name}__judge_*"))
    assert {p.suffix for p in out} == {".md", ".json"}
    assert "grounded 100%" in capsys.readouterr().out


# --- the real provider SDKs, end to end, with only the HTTP layer faked ---

def _reply_for(system: str) -> str:
    if system == stages.JUDGE_SYSTEM:
        return json.dumps([{"id": 1, "verdict": "supported", "block": 1},
                           {"id": 2, "verdict": "unsupported"},
                           {"id": 3, "verdict": "supported", "block": 1}])
    if system == research_svc.REPORT_SYSTEM:
        return REPORT.replace("main plant", "Takaoka plant")
    return "Any operator can stop the line (https://ex.com/1)."


def _sse(events: list[tuple[str, dict]]) -> bytes:
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()


def _anthropic_handler(seen, http_lib=httpx):
    def handle(request):
        body = json.loads(request.content)
        seen.append(request.headers.get("x-api-key"))
        text = _reply_for(body["system"])
        events = [
            ("message_start", {"type": "message_start", "message": {
                "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                "content": [], "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 1}}}),
            ("content_block_start", {"type": "content_block_start", "index": 0,
                                     "content_block": {"type": "text", "text": ""}}),
        ]
        for i in range(0, len(text), 40):  # stream it in pieces like the real API
            events.append(("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                   "delta": {"type": "text_delta", "text": text[i:i + 40]}}))
        events += [
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn",
                                                                   "stop_sequence": None},
                               "usage": {"output_tokens": 50}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        return http_lib.Response(200, content=_sse(events), headers={"content-type": "text/event-stream"})
    return handle


def _openai_handler(seen, http_lib=httpx):
    def handle(request):
        body = json.loads(request.content)
        seen.append(request.headers.get("authorization"))
        text = _reply_for(body["messages"][0]["content"])
        if not body.get("stream"):
            return http_lib.Response(200, json={
                "id": "c1", "object": "chat.completion", "created": 1, "model": body["model"],
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": text}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
        chunks = [{"id": "c1", "object": "chat.completion.chunk", "created": 1, "model": body["model"],
                   "choices": [{"index": 0, "delta": {"content": text[i:i + 40]}, "finish_reason": None}]}
                  for i in range(0, len(text), 40)]
        payload = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return http_lib.Response(200, content=payload.encode(), headers={"content-type": "text/event-stream"})
    return handle


@pytest.mark.parametrize("provider", ["anthropic", "openai"])
def test_replay_and_judge_through_real_sdk(monkeypatch, provider):
    d = _make_run(monkeypatch)

    async def no_network(*a, **k):
        raise AssertionError("replay must use the recorded search")
    monkeypatch.setattr(research_svc, "web_search", no_network)

    key = "sk-ant-wire-test-123456" if provider == "anthropic" else "sk-wire-test-1234567890"
    client = build_client(provider, key, None)
    seen: list = []
    # Use whichever HTTP library this SDK version is built on (newer ones ship an httpx2 fork).
    import anthropic._base_client as a_base
    import openai._base_client as o_base
    sdk_base = a_base if provider == "anthropic" else o_base
    lib = getattr(sdk_base, "httpx2", None) or sdk_base.httpx
    handler = _anthropic_handler(seen, lib) if provider == "anthropic" else _openai_handler(seen, lib)
    http = lib.AsyncClient(transport=lib.MockTransport(handler))
    client._client = (AsyncAnthropic if provider == "anthropic" else AsyncOpenAI)(
        api_key=key, http_client=http, max_retries=0)

    res = asyncio.run(stages.replay(d, client, "02_search", judge_client=client))

    assert res["events"][-1].type == "done", res["events"][-1]
    assert list(res["diffs"]) == [runs.REPORT_FILE]
    added = [l for l in res["diffs"][runs.REPORT_FILE].splitlines() if l.startswith("+") and "Takaoka" in l]
    assert added, res["diffs"][runs.REPORT_FILE]  # the streamed report really changed
    assert {c.status for c in res["checks"]} == {"PASS"}  # incl. "no API key on disk"
    assert res["judged"]["replay"]["counts"] == {"supported": 2, "partial": 0, "unsupported": 1,
                                                 "contradicted": 0, "no_claim": 0, "unjudged": 0}
    assert "| replay | 67% |" in (res["dir"] / "REPLAY.md").read_text()
    assert seen and all(key in (h or "") for h in seen)  # the key went to the provider...
    for f in res["dir"].rglob("*"):                        # ...and nowhere on disk
        if f.is_file():
            assert key not in f.read_text(encoding="utf-8")
