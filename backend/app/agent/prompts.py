"""System prompts for the agent: identity + memory, the manual tool protocol, and
the consolidation gate."""
from __future__ import annotations

from datetime import date
from typing import Optional


def _memory_block(memories: list[dict]) -> str:
    if not memories:
        return ""
    lines = "\n".join(f"- {m['text']}" for m in memories)
    return f"\n\nWhat you remember about the user:\n{lines}"


def base_system(assistant_name: str, memories: list[dict],
                skills: Optional[list[dict]] = None) -> str:
    today = date.today().isoformat()
    s = (
        f"You are {assistant_name}, a helpful local-first personal assistant running on "
        "the user's own laptop. You can use tools to do practical things: search the web, "
        "run deep research, manage a local calendar, read/write workspace files, and "
        "remember facts. Prefer a tool over guessing when you need current or personal "
        "information. Be concise, friendly, and direct. "
        f"Today's date is {today}; use it to resolve relative dates like "
        "'today', 'tomorrow', or 'next Monday'."
    )
    s += _memory_block(memories)
    if skills:
        sk = "\n".join(f"- {k['name']}: {k.get('description', '')}" for k in skills)
        s += f"\n\nSkills you can follow:\n{sk}"
    return s


MANUAL_PROTOCOL = (
    "\n\nYou operate in a tool loop. Respond with EXACTLY ONE JSON object and nothing "
    "else:\n"
    '  to use a tool:  {{"tool": "<name>", "args": {{ ... }}}}\n'
    '  to answer:      {{"final": "<your answer to the user>"}}\n'
    "Use one tool at a time; you will see its result and may then use another tool or "
    "answer. Available tools:\n{catalog}"
)


def manual_system(assistant_name: str, memories: list[dict], catalog: str,
                  skills: Optional[list[dict]] = None) -> str:
    return base_system(assistant_name, memories, skills) + MANUAL_PROTOCOL.format(catalog=catalog)


CONSOLIDATE_SYSTEM = (
    "You decide what is worth remembering long-term about the user. Given the latest "
    "exchange, extract only durable, useful facts or preferences (names, preferences, "
    "recurring context) -- NOT small talk or transient details. Respond with ONLY a JSON "
    "array of short strings. Use [] if nothing is worth keeping."
)
