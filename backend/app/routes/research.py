"""POST /research/stream runs the pipeline; POST /research/runs/{id}/decision resumes a
paused run. Both stream SSE events."""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..models.research import DecisionRequest, EventFactory, ResearchRequest
from ..providers.base import ProviderError, build_client
from ..services.research import decide, run_research

logger = logging.getLogger(__name__)
router = APIRouter(tags=["research"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering so events flush live
}


@router.post("/research/stream")
async def research_stream(req: ResearchRequest) -> StreamingResponse:
    async def event_stream():
        try:
            client = build_client(req.provider, req.api_key, req.model)
        except ProviderError as exc:
            yield EventFactory().error(exc.message, code=exc.code).to_sse()
            return
        logger.info(
            "research start provider=%s model=%s subq=%s search=%s",
            req.provider.value, req.model or "(default)", req.max_subquestions, req.search,
        )
        async for event in run_research(req, client):
            yield event.to_sse()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/research/runs/{run_id}/decision")
async def research_decision(run_id: str, req: DecisionRequest) -> StreamingResponse:
    """Approve / edit / reject a run paused by an ``await_approval`` event."""
    async def event_stream():
        try:
            client = build_client(req.provider, req.api_key, req.model)
        except ProviderError as exc:
            yield EventFactory().error(exc.message, code=exc.code).to_sse()
            return
        logger.info("research decision run=%s stage=%s action=%s", run_id, req.stage, req.action)
        async for event in decide(run_id, req, client):
            yield event.to_sse()

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
