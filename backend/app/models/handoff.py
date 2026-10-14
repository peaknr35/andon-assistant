"""Request and event models for the shift-handoff workflow (``_shared/shift-handoff.md``)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .research import _KeyedRequest


class HandoffRequest(_KeyedRequest):
    """Body for POST /handoff/stream: start a run from raw end-of-shift notes."""

    notes: str = Field(..., min_length=1, max_length=50_000)
    line: str = Field(..., min_length=1, max_length=80)
    shift: str = Field(..., min_length=1, max_length=40)
    supervisor: Optional[str] = Field(default=None, max_length=80)

    @field_validator("line", "shift")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("required")
        return v


class HandoffDecision(_KeyedRequest):
    """Body for POST /handoff/runs/{run_id}/decision."""

    stage: str = Field(..., max_length=40)
    action: Literal["approve", "edit", "reject"]
    edited_content: Optional[str] = Field(default=None, max_length=50_000)
    note: Optional[str] = Field(default=None, max_length=2000)


HandoffEventType = Literal["status", "token", "stage_output", "await_approval", "done", "error"]


class HandoffEvent(BaseModel):
    type: HandoffEventType
    stage: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class HandoffEventFactory:
    def __init__(self, run_id: Optional[str] = None) -> None:
        self.run_id = run_id or str(uuid.uuid4())

    def _mk(self, type_, stage=None, message=None, data=None) -> HandoffEvent:
        return HandoffEvent(type=type_, stage=stage, message=message, data=data, run_id=self.run_id)

    def status(self, stage: str, message: str) -> HandoffEvent:
        return self._mk("status", stage, message)

    def token(self, stage: str, text: str) -> HandoffEvent:
        return self._mk("token", stage, None, {"text": text})

    def stage_output(self, stage: str, path: str, content: str, warnings: list[str]) -> HandoffEvent:
        return self._mk("stage_output", stage, f"{stage} written",
                        {"artifact": path, "content": content, "citation_warnings": warnings})

    def await_approval(self, data: dict[str, Any]) -> HandoffEvent:
        return self._mk("await_approval", data.get("stage"), "Waiting for the supervisor", data)

    def done(self, status: str = "complete", data: Optional[dict[str, Any]] = None) -> HandoffEvent:
        """``status``: complete | paused | rejected."""
        return self._mk("done", "done", {"complete": "Brief ready", "paused": "Paused for review",
                                         "rejected": "Run rejected"}.get(status, status),
                        {"status": status, **(data or {})})

    def error(self, message: str, code: str = "internal") -> HandoffEvent:
        return self._mk("error", "error", message, {"code": code})
