"""run_turn() -- the visible turn loop (pure functions we own).

RECEIVE -> RECALL -> [REASON -> ACT -> OBSERVE]* (run_middle) -> REMEMBER -> REPLY.
Yields TurnEvents for the terminal TUI and the dashboard. DB work runs in threads
so SQLite never blocks the event loop.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Optional

from ..config import get_settings
from ..memory import candidates, store
from ..models.chat import TurnEvent, TurnEventFactory
from ..providers.base import ProviderError, build_client
from ..tools.registry import build_registry
from .generate import consolidate, run_middle

logger = logging.getLogger(__name__)


async def run_turn(
    *,
    message: str,
    provider: str,
    api_key: str,
    model: Optional[str] = None,
    conversation_id: Optional[int] = None,
    backend: Optional[str] = None,
    assistant_name: Optional[str] = None,
    max_steps: Optional[int] = None,
) -> AsyncIterator[TurnEvent]:
    ev = TurnEventFactory()
    s = get_settings()
    backend = backend or s.agent_backend
    assistant_name = assistant_name or s.assistant_name
    max_steps = max_steps or s.agent_max_steps

    try:
        yield ev.phase("receive", "Received your message")
        client = build_client(provider, api_key, model)
        registry = build_registry(client)
        conv = conversation_id or await asyncio.to_thread(store.start_conversation)
        history = await asyncio.to_thread(store.recent_turns, conv, 10)
        await asyncio.to_thread(store.add_turn, conv, "user", message)

        yield ev.phase("recall", "Searching memory")
        if candidates.enabled():  # pick up approvals a person made by editing files
            try:
                hand = await asyncio.to_thread(candidates.sync_hand_edits)
                if hand["promoted"]:
                    yield ev.memory("promote", hand["promoted"])
            except OSError as exc:
                logger.warning("memory candidate sync failed: %s", exc)
        memories = await asyncio.to_thread(store.recall, message, 6)
        if memories:
            yield ev.memory("recall", [m["text"] for m in memories])

        final_text = ""
        tool_events: list[TurnEvent] = []
        async for e in run_middle(
            backend, client=client, provider=provider, model=model, api_key=api_key, ev=ev,
            assistant_name=assistant_name, memories=memories, history=history,
            message=message, registry=registry, max_steps=max_steps,
        ):
            if e.type == "final":
                final_text = e.message or ""
            elif e.type == "tool_result":
                tool_events.append(e)
            yield e

        yield ev.phase("remember", "Deciding what to keep")
        picked = await consolidate(client, message, final_text)
        if candidates.enabled():
            # Controlled promotion: propose, don't save. A person approves later.
            proposed = []
            for fact in picked:
                c = await asyncio.to_thread(
                    candidates.propose, fact, "fact", f"from: {message[:160]}"
                )
                if c:
                    proposed.append(c.text)
            if proposed:
                yield ev.memory("propose", proposed)
        else:
            for fact in picked:
                await asyncio.to_thread(store.add_fact, fact, "fact", "auto")
            if picked:
                yield ev.memory("save", picked)
        try:  # keep the readable facts.md mirror current (also covers the remember tool)
            await asyncio.to_thread(candidates.export_facts_md)
        except OSError as exc:
            logger.warning("facts.md export failed: %s", exc)

        a_turn = await asyncio.to_thread(
            store.add_turn, conv, "assistant", final_text, {"backend": backend}
        )
        for te in tool_events:
            d = te.data or {}
            await asyncio.to_thread(
                store.add_tool_run, a_turn, te.name or "", d.get("args"),
                str(d.get("result", "")), bool(d.get("ok", True)),
            )
        yield ev.done(conversation_id=conv, turn_db_id=a_turn)

    except ProviderError as exc:
        yield ev.error(exc.message, code=exc.code)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("turn failed")
        yield ev.error(str(exc))
