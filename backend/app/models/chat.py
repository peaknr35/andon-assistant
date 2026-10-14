"""Chat request + turn-event models. The TurnEvent is the server side of the
agent-turn SSE contract (../../../_shared/agent-turn-contract.md)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .research import Provider


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    provider: Provider
    model: Optional[str] = Field(default=None, max_length=100)
    api_key: str = Field(..., min_length=8, max_length=400, repr=False)
    conversation_id: Optional[int] = None
    backend: Optional[str] = None  # "pydantic_ai" | "manual" (override the default)

    @field_validator("message")
    @classmethod
    def _strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message is empty")
        return v

    @field_validator("api_key")
    @classmethod
    def _strip_key(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8:
            raise ValueError("api_key is too short")
        return v


TurnEventType = Literal[
    "phase", "thought", "tool_call", "tool_result", "memory", "token", "final", "error", "done"
]


class TurnEvent(BaseModel):
    type: TurnEventType
    phase: Optional[str] = None
    name: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    turn_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class TurnEventFactory:
    def __init__(self, turn_id: Optional[str] = None) -> None:
        self.turn_id = turn_id or str(uuid.uuid4())

    def _mk(self, type_, phase=None, name=None, message=None, data=None) -> TurnEvent:
        return TurnEvent(type=type_, phase=phase, name=name, message=message,
                         data=data, turn_id=self.turn_id)

    def phase(self, phase: str, message: Optional[str] = None) -> TurnEvent:
        return self._mk("phase", phase=phase, message=message)

    def tool_call(self, name: str, args) -> TurnEvent:
        return self._mk("tool_call", phase="act", name=name, data={"args": args})

    def tool_result(self, name: str, args, result: str, ok: bool = True) -> TurnEvent:
        return self._mk("tool_result", phase="observe", name=name,
                        data={"args": args, "result": result, "ok": ok})

    def memory(self, action: str, items: list[str]) -> TurnEvent:
        phase = "recall" if action == "recall" else "remember"  # save | propose | promote
        return self._mk("memory", phase=phase, name=action, data={"items": items})

    def token(self, text: str) -> TurnEvent:
        return self._mk("token", phase="reply", data={"text": text})

    def final(self, text: str) -> TurnEvent:
        return self._mk("final", phase="reply", message=text)

    def error(self, message: str, code: str = "internal") -> TurnEvent:
        return self._mk("error", phase="error", message=message, data={"code": code})

    def done(self, conversation_id=None, turn_db_id=None) -> TurnEvent:
        return self._mk("done", phase="done",
                        data={"conversation_id": conversation_id, "turn_id": turn_db_id})


class CandidateDecision(BaseModel):
    """Body for POST /memory/candidates/{id}: approve (optionally edited) or reject."""

    action: Literal["approve", "reject"]
    text: Optional[str] = Field(default=None, max_length=1000)
