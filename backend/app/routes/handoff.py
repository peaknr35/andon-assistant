"""Shift handoff endpoints: start a run (SSE), decide at a gate (SSE), list / load runs."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..models.handoff import HandoffDecision, HandoffEventFactory, HandoffRequest
from ..providers.base import ProviderError, build_client
from ..services import handoff

logger = logging.getLogger(__name__)
router = APIRouter(tags=["handoff"])

_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


def _stream(make_events, req):
    async def event_stream():
        try:
            client = build_client(req.provider, req.api_key, req.model)
        except ProviderError as exc:
            yield HandoffEventFactory().error(exc.message, code=exc.code).to_sse()
            return
        async for e in make_events(client):
            yield e.to_sse()
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/handoff/stream")
async def handoff_stream(req: HandoffRequest) -> StreamingResponse:
    logger.info("handoff start line=%s shift=%s provider=%s", req.line, req.shift, req.provider.value)
    return _stream(lambda client: handoff.run_handoff(req, client), req)


@router.post("/handoff/runs/{run_id}/decision")
async def handoff_decision(run_id: str, req: HandoffDecision) -> StreamingResponse:
    logger.info("handoff decision run=%s stage=%s action=%s", run_id, req.stage, req.action)
    return _stream(lambda client: handoff.decide(run_id, req, client), req)


@router.get("/handoff/runs")
async def handoff_runs() -> dict:
    return {"runs": await asyncio.to_thread(handoff.list_runs, 20)}


@router.get("/handoff/runs/{run_id}")
async def handoff_run(run_id: str) -> dict:
    run = await asyncio.to_thread(handoff.get_run, run_id)
    if run is None:
        raise HTTPException(404, f"No shift handoff run '{run_id}'.")
    return run
