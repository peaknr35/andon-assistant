"""deep_research tool -- fast, demo-friendly web research.

Runs its web searches in PARALLEL and writes one tight cited summary (a single
model call), so a live turn finishes in ~12-18s instead of 30-60s. The full
progressive pipeline still lives in services.research.run_research and powers
the /research UI page unchanged.
"""
from __future__ import annotations

import asyncio

from .base import ToolSpec

_SYS_SOURCED = (
    "You are a maintenance research analyst. Using the web results provided, write a "
    "concise markdown answer with: what it means, the most-likely cause(s), and clear "
    "numbered steps to resolve it. Cite sources inline by their URL in parentheses. "
    "Be tight and practical -- a technician on the line is reading this."
)
_SYS_UNSOURCED = (
    "You are a maintenance expert. No web results were available, so answer concisely "
    "from general knowledge with clear numbered steps, and note that it is not "
    "source-backed."
)


def make_deep_research(client) -> ToolSpec:
    async def deep_research(query: str) -> str:
        """Run a quick multi-source web research pass and return a cited markdown
        summary. Use when a question needs current, well-sourced information."""
        from ..services.search import web_search

        angles = [query, f"{query} cause fix steps"]
        try:
            batches = await asyncio.gather(*[web_search(a, 5) for a in angles])
        except Exception:
            batches = []

        seen: set[str] = set()
        sources = []
        for lst in batches:
            for s in lst:
                if s.url and s.url not in seen:
                    seen.add(s.url)
                    sources.append(s)
        sources = sources[:6]

        if sources:
            block = "\n\n".join(
                f"[{i}] {s.title}\nURL: {s.url}\n{s.snippet}"
                for i, s in enumerate(sources, 1)
            )
            system = _SYS_SOURCED
            user = f"Question: {query}\n\nWeb results:\n{block}\n\nWrite the cited answer now."
        else:
            system = _SYS_UNSOURCED
            user = f"Question: {query}\n\nWrite the answer now."

        try:
            report = await client.complete(system, user, max_tokens=700)
        except Exception as exc:  # surface provider errors to the turn, do not crash
            return f"deep_research error: {exc}"

        if sources:
            report = (report or "").rstrip() + "\n\n**Sources**\n" + "\n".join(
                f"- {s.url}" for s in sources
            )
        return report or "No report produced."

    return ToolSpec(
        "deep_research",
        "Fast multi-source web research producing a cited summary.",
        deep_research,
    )
