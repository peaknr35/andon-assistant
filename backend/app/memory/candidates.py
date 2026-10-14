"""Memory candidates: facts the consolidation gate *proposes*, waiting for a person.

With ``APP_MEMORY_REVIEW=1`` the REMEMBER phase writes each auto-extracted fact as a
markdown file instead of inserting it into ``facts``:

    ~/.assistant/memory/candidates/<id>.md     pending (edit the text or the status)
    ~/.assistant/memory/candidates/_done/      approved -> promoted to facts (source=reviewed)
    ~/.assistant/memory/candidates/_rejected/  rejected (never re-proposed)

A person decides from the dashboard, the CLI (``/review``), or by editing the file and
setting ``status: approved`` / ``status: rejected``; ``sync_hand_edits()`` picks those
up. Only promoted candidates are recalled. The ``remember`` tool (an explicit user
request) still writes straight to ``facts``.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import get_settings
from . import store

logger = logging.getLogger(__name__)

_ID = re.compile(r"^\d{8}T\d{6}_[0-9a-f]{6}$")
_HINT = ("<!-- Edit the text above if needed, then set status to approved or rejected. "
         "Changes are picked up on the next chat turn, or with /review. -->")


def memory_dir() -> Path:
    s = get_settings()
    d = Path(s.memory_dir).expanduser() if s.memory_dir else Path.home() / ".assistant" / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def candidates_dir() -> Path:
    d = memory_dir() / "candidates"
    for sub in ("", "_done", "_rejected"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def enabled() -> bool:
    return bool(get_settings().memory_review)


@dataclass
class Candidate:
    id: str
    text: str
    kind: str
    status: str          # pending | approved | rejected
    proposed_at: str
    reason: str
    path: Path

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "kind": self.kind, "status": self.status,
                "proposed_at": self.proposed_at, "reason": self.reason, "file": str(self.path)}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _render(c: Candidate) -> str:
    return (
        "---\n"
        f"id: {c.id}\n"
        f"kind: {c.kind}\n"
        f"status: {c.status}\n"
        f"proposed_at: {c.proposed_at}\n"
        f"reason: {c.reason}\n"
        "---\n"
        f"{c.text}\n\n{_HINT}\n"
    )


def _parse(path: Path) -> Optional[Candidate]:
    """Parse a candidate file; None if it is malformed (it is then left alone)."""
    try:
        raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return None
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if not m:
        return None
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    body = re.sub(r"<!--.*?-->", "", m.group(2), flags=re.S).strip()
    status = meta.get("status", "").lower()
    if not body or status not in ("pending", "approved", "rejected"):
        return None
    return Candidate(id=meta.get("id") or path.stem, text=body, kind=meta.get("kind") or "fact",
                     status=status, proposed_at=meta.get("proposed_at", ""),
                     reason=meta.get("reason", ""), path=path)


def _all_in(folder: Path) -> list[Candidate]:
    out = []
    for p in sorted(folder.glob("*.md")):
        c = _parse(p)
        if c is None:
            logger.warning("skipping malformed memory candidate: %s", p)
            continue
        out.append(c)
    return out


def pending() -> list[Candidate]:
    return [c for c in _all_in(candidates_dir()) if c.status == "pending"]


def propose(text: str, kind: str = "fact", reason: str = "") -> Optional[Candidate]:
    """Write a pending candidate. Skips text that is already a fact, already pending,
    or was rejected before (so the model can't nag with the same proposal)."""
    text = " ".join((text or "").split())
    if not text:
        return None
    key = _norm(text)
    d = candidates_dir()
    known = {_norm(f["text"]) for f in store.all_facts(10_000)}
    known |= {_norm(c.text) for c in _all_in(d)}
    known |= {_norm(c.text) for c in _all_in(d / "_rejected")}
    if key in known:
        return None
    now = datetime.now(timezone.utc)
    cid = f"{now.strftime('%Y%m%dT%H%M%S')}_{hashlib.sha1(key.encode()).hexdigest()[:6]}"
    c = Candidate(id=cid, text=text, kind=kind, status="pending", proposed_at=now.isoformat(),
                  reason=" ".join(reason.split())[:200], path=d / f"{cid}.md")
    c.path.write_text(_render(c), encoding="utf-8")
    return c


def get(cid: str) -> Optional[Candidate]:
    if not _ID.match(cid or ""):
        return None
    p = candidates_dir() / f"{cid}.md"
    return _parse(p) if p.exists() else None


def _finish(c: Candidate, status: str) -> Optional[int]:
    """Move a decided candidate out of the pending folder; promote if approved."""
    fact_id = None
    if status == "approved":
        fact_id = store.add_fact(c.text, c.kind, "reviewed")
    c.status = status
    dest = c.path.parent / ("_done" if status == "approved" else "_rejected") / c.path.name
    dest.write_text(_render(c), encoding="utf-8")
    c.path.unlink(missing_ok=True)
    c.path = dest
    return fact_id


def decide(cid: str, action: str, text: Optional[str] = None) -> dict:
    """approve (optionally with edited ``text``) or reject one pending candidate."""
    c = get(cid)
    if c is None or c.status != "pending":
        raise KeyError(cid)
    if action == "approve":
        if text is not None and " ".join(text.split()):
            c.text = " ".join(text.split())
        fact_id = _finish(c, "approved")
        export_facts_md()
        return {"id": cid, "status": "approved", "fact_id": fact_id, "text": c.text}
    if action == "reject":
        _finish(c, "rejected")
        return {"id": cid, "status": "rejected"}
    raise ValueError(f"unknown action {action!r}")


def sync_hand_edits() -> dict:
    """Apply decisions a person made by editing files (status: approved / rejected)."""
    promoted, rejected = [], []
    for c in _all_in(candidates_dir()):
        if c.status == "approved":
            _finish(c, "approved")
            promoted.append(c.text)
        elif c.status == "rejected":
            _finish(c, "rejected")
            rejected.append(c.text)
    if promoted:
        export_facts_md()
    return {"promoted": promoted, "rejected": rejected}


def export_facts_md() -> Path:
    """Regenerate the read-only human view of the facts table."""
    path = memory_dir() / "facts.md"
    facts = sorted(store.all_facts(10_000), key=lambda f: (f["kind"], f["id"]))
    lines = [
        "# Facts",
        "",
        f"_Read-only mirror of the `facts` table in state.db, exported "
        f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}. Edits here are "
        "overwritten; review new facts in `candidates/`._",
    ]
    kind = None
    for f in facts:
        if f["kind"] != kind:
            kind = f["kind"]
            lines += ["", f"## {kind}", ""]
        lines.append(f"- [{f['id']}] {f['text']}  _({f['source']}, {str(f['created_at'])[:10]})_")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
