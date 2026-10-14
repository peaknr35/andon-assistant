"""Assistant endpoints: the streaming turn, memory/trace for the dashboard, and the
memory-candidate review step (approve / reject facts the agent proposed)."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..agent.loop import run_turn
from ..memory import candidates, store
from ..models.chat import CandidateDecision, ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["assistant"])


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    async def event_stream():
        logger.info("chat turn provider=%s backend=%s", req.provider.value, req.backend or "(default)")
        async for ev in run_turn(
            message=req.message, provider=req.provider.value, api_key=req.api_key,
            model=req.model, conversation_id=req.conversation_id, backend=req.backend,
        ):
            yield ev.to_sse()

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.get("/memory")
async def get_memory() -> dict:
    facts = await asyncio.to_thread(store.all_facts, 100)
    counts = await asyncio.to_thread(store.counts)
    pending = await asyncio.to_thread(candidates.pending) if candidates.enabled() else []
    return {"facts": facts, "counts": counts, "review": candidates.enabled(),
            "pending_candidates": len(pending)}


@router.get("/memory/candidates")
async def list_candidates() -> dict:
    """Pending proposals (after applying any decisions made by editing the files)."""
    if not candidates.enabled():
        return {"review": False, "candidates": [], "folder": None}
    await asyncio.to_thread(candidates.sync_hand_edits)
    pending = await asyncio.to_thread(candidates.pending)
    return {"review": True, "candidates": [c.to_dict() for c in pending],
            "folder": str(candidates.candidates_dir())}


@router.post("/memory/candidates/{candidate_id}")
async def decide_candidate(candidate_id: str, body: CandidateDecision) -> dict:
    try:
        return await asyncio.to_thread(candidates.decide, candidate_id, body.action, body.text)
    except KeyError:
        raise HTTPException(404, f"No pending memory candidate '{candidate_id}'.")


@router.get("/trace")
async def get_trace() -> dict:
    runs = await asyncio.to_thread(store.recent_tool_runs, 50)
    return {"tool_runs": runs}
