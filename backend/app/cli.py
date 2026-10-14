"""Terminal TUI for the assistant: python -m app.cli  (or the `assistant` command).

Reads provider/model/key from the environment (local-first):
  APP_PROVIDER (default from settings), APP_MODEL (optional), APP_API_KEY (required).
Renders each turn-loop phase live with Rich.
"""
from __future__ import annotations

import asyncio
import os

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from .agent.loop import run_turn
from .config import get_settings
from .memory import candidates, db, store

console = Console()


async def _one_turn(message: str, provider: str, model, api_key: str, conv_id):
    lines: list[Text] = []

    def view() -> Panel:
        body = Group(*lines) if lines else Text("thinking...", style="dim")
        return Panel(body, title="turn", border_style="cyan")

    from rich.live import Live
    final = ""
    with Live(view(), console=console, refresh_per_second=12, transient=True) as live:
        async for ev in run_turn(message=message, provider=provider, api_key=api_key,
                                 model=model, conversation_id=conv_id):
            if ev.type == "phase":
                lines.append(Text(f"● {ev.phase}: {ev.message or ''}", style="dim"))
            elif ev.type == "memory":
                items = ", ".join((ev.data or {}).get("items", [])) or "-"
                lines.append(Text(f"  memory[{ev.name}]: {items}", style="magenta"))
            elif ev.type == "tool_call":
                lines.append(Text(f"  -> {ev.name}({(ev.data or {}).get('args')})", style="yellow"))
            elif ev.type == "tool_result":
                d = ev.data or {}
                snippet = str(d.get("result", ""))[:200].replace("\n", " ")
                lines.append(Text(f"     {snippet}", style="green" if d.get("ok") else "red"))
            elif ev.type == "final":
                final = ev.message or ""
            elif ev.type == "error":
                final = f"[error] {ev.message}"
            elif ev.type == "done":
                conv_id = (ev.data or {}).get("conversation_id", conv_id)
            live.update(view())

    console.print(Panel(final or "(no answer)", title=get_settings().assistant_name,
                        border_style="green"))
    return conv_id


def _load_dotenv() -> None:
    """Populate os.environ from backend/.env (local CLI convenience; never overrides real env)."""
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / ".env"
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


async def _main() -> None:
    _load_dotenv()
    s = get_settings()
    provider = os.getenv("APP_PROVIDER", s.default_provider)
    model = os.getenv("APP_MODEL") or None
    api_key = os.getenv("APP_API_KEY", "")

    console.print(Panel(
        f"[bold]{s.assistant_name}[/] -- local-first agent\n"
        f"provider: {provider}   model: {model or '(default)'}   backend: {s.agent_backend}\n"
        f"memory: {db.db_path()}\n"
        "commands: /mem (show memory), /review /approve N|all /reject N (memory candidates), /exit"
        + ("\nmemory review: ON -- new facts wait for your approval" if candidates.enabled() else ""),
        border_style="cyan",
    ))
    if not api_key:
        console.print("[yellow]Set APP_API_KEY (and optionally APP_PROVIDER / APP_MODEL) to start chatting.[/]")
        return

    conv_id = None
    while True:
        try:
            msg = console.input("[bold cyan]you >[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not msg:
            continue
        if msg in ("/exit", "/quit"):
            break
        if msg == "/mem":
            facts = store.all_facts(20)
            console.print(Panel("\n".join(f"- {f['text']}" for f in facts) or "(empty)",
                                title="memory", border_style="magenta"))
            continue
        if msg.split()[0] in ("/review", "/approve", "/reject"):
            _review_command(msg)
            continue
        conv_id = await _one_turn(msg, provider, model, api_key, conv_id)


def _review_command(msg: str) -> None:
    """/review lists pending memory candidates; /approve N|all and /reject N decide."""
    if not candidates.enabled():
        console.print("[yellow]Memory review is off. Set APP_MEMORY_REVIEW=1 in backend/.env.[/]")
        return
    hand = candidates.sync_hand_edits()
    for t in hand["promoted"]:
        console.print(f"[green]promoted (edited file):[/] {t}")
    items = candidates.pending()
    parts = msg.split()
    if parts[0] in ("/approve", "/reject") and len(parts) == 2:
        chosen = items if parts[1] == "all" and parts[0] == "/approve" else (
            [items[int(parts[1]) - 1]] if parts[1].isdigit() and 0 < int(parts[1]) <= len(items) else []
        )
        if not chosen:
            console.print("[yellow]No such candidate. Run /review to see the numbers.[/]")
            return
        action = "approve" if parts[0] == "/approve" else "reject"
        for c in chosen:
            try:
                candidates.decide(c.id, action)
            except KeyError:  # decided meanwhile, e.g. from the dashboard
                console.print(f"[yellow]already decided elsewhere:[/] {c.text}")
                continue
            except OSError as exc:
                console.print(f"[red]could not save the decision ({exc}):[/] {c.text}")
                continue
            console.print(f"[{'green' if action == 'approve' else 'red'}]{action}d:[/] {c.text}")
        items = candidates.pending()
    lines = [f"{i}. {c.text}  [dim]({c.reason})[/]" for i, c in enumerate(items, 1)]
    console.print(Panel(
        "\n".join(lines) or "(nothing waiting)",
        title=f"memory candidates -- {candidates.candidates_dir()}",
        subtitle="/approve N|all  /reject N  (or edit the file: status: approved)",
        border_style="magenta",
    ))


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
