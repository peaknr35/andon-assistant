"""Request and event models for the research API.

The event shape is the single source of truth mirror of
``_shared/api-contract.md``. Change both together.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Provider(str, enum.Enum):
    openai = "openai"
    anthropic = "anthropic"
    kimi = "kimi"


class _KeyedRequest(BaseModel):
    """Provider + model + the user's own key (used for one request, never stored)."""

    provider: Provider
    model: Optional[str] = Field(default=None, max_length=100)
    api_key: str = Field(..., min_length=8, max_length=400, repr=False)

    @field_validator("api_key")
    @classmethod
    def _strip_key(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 8:
            raise ValueError("api_key is too short")
        return v

    @field_validator("model")
    @classmethod
    def _strip_model(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ResearchRequest(_KeyedRequest):
    """Validated body for POST /research/stream."""

    query: str = Field(..., min_length=3, max_length=2000)
    max_subquestions: int = Field(default=4, ge=1, le=8)
    search: bool = True
    # Pause after 01_plan (and on an andon STOP) for a person to approve/edit/reject.
    review_plan: bool = False

    @field_validator("query")
    @classmethod
    def _strip_query(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("query must be at least 3 characters")
        return v


class DecisionRequest(_KeyedRequest):
    """Body for POST /research/runs/{run_id}/decision (resume a paused run)."""

    stage: str = Field(..., max_length=40)
    action: Literal["approve", "edit", "reject"]
    edited_content: Optional[str] = Field(default=None, max_length=50_000)
    note: Optional[str] = Field(default=None, max_length=2000)


class Source(BaseModel):
    title: str = ""
    url: str = ""
    snippet: str = ""


EventType = Literal[
    "status", "plan", "sources", "finding", "token", "report", "await_approval", "done", "error"
]


class ResearchEvent(BaseModel):
    type: EventType
    stage: Optional[str] = None
    message: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    research_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_sse(self) -> str:
        """Serialize to a single Server-Sent Event frame."""
        return f"data: {self.model_dump_json()}\n\n"


class EventFactory:
    """Builds ResearchEvents that all share one research_id."""

    def __init__(self, research_id: Optional[str] = None) -> None:
        self.research_id = research_id or str(uuid.uuid4())

    def _mk(
        self,
        type_: EventType,
        stage: Optional[str] = None,
        message: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> ResearchEvent:
        return ResearchEvent(
            type=type_, stage=stage, message=message, data=data,
            research_id=self.research_id,
        )

    def status(self, stage: str, message: str, progress: Optional[float] = None) -> ResearchEvent:
        data = {"progress": round(progress, 3)} if progress is not None else None
        return self._mk("status", stage, message, data)

    def plan(self, subquestions: list[str]) -> ResearchEvent:
        return self._mk("plan", "planning", "Research plan ready", {"subquestions": subquestions})

    def sources(self, index: int, subquestion: str, sources: list[Source]) -> ResearchEvent:
        return self._mk(
            "sources", "researching", None,
            {"index": index, "subquestion": subquestion,
             "sources": [s.model_dump() for s in sources]},
        )

    def finding(self, index: int, subquestion: str, summary: str, sources: list[Source]) -> ResearchEvent:
        return self._mk(
            "finding", "researching", None,
            {"index": index, "subquestion": subquestion, "summary": summary,
             "sources": [s.model_dump() for s in sources]},
        )

    def token(self, text: str) -> ResearchEvent:
        return self._mk("token", "report", None, {"text": text})

    def report(self, report: str, sources: list[Source]) -> ResearchEvent:
        return self._mk(
            "report", "report", "Report complete",
            {"report": report, "sources": [s.model_dump() for s in sources]},
        )

    def await_approval(self, data: dict[str, Any]) -> ResearchEvent:
        return self._mk("await_approval", "approval", "Waiting for your review", data)

    def done(self, status: str = "complete") -> ResearchEvent:
        """``status``: complete | paused (awaiting a decision) | rejected."""
        messages = {"complete": "Research complete", "paused": "Paused for review",
                    "rejected": "Run rejected"}
        data = None if status == "complete" else {"status": status}
        return self._mk("done", "done", messages.get(status, status), data)

    def error(self, message: str, code: str = "internal") -> ResearchEvent:
        return self._mk("error", "error", message, {"code": code})
