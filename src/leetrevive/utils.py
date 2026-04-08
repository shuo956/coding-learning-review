from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.theme import Theme

DIFFICULTY_COLORS = {
    "easy": "green",
    "medium": "yellow",
    "hard": "red",
}

SCORE_LABELS: dict[int, str] = {
    0: "[red]0 — Blank[/red]",
    1: "[yellow]1 — Partial[/yellow]",
    2: "[blue]2 — Struggled[/blue]",
    3: "[green]3 — Clean[/green]",
}

_THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
    }
)

console = Console(theme=_THEME)
err_console = Console(stderr=True, theme=_THEME)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def title_to_slug(title: str) -> str:
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug


def build_leetcode_url(title: str) -> str:
    return f"https://leetcode.com/problems/{title_to_slug(title)}/"


# ---------------------------------------------------------------------------
# Formatting helpers for rich output
# ---------------------------------------------------------------------------

def difficulty_display(difficulty: Optional[str]) -> str:
    if not difficulty:
        return "[dim]-[/dim]"
    color = DIFFICULTY_COLORS.get(difficulty.lower(), "white")
    return f"[{color}]{difficulty.capitalize()}[/{color}]"


def format_dt(dt: Optional[datetime], *, relative: bool = False) -> str:
    """Format a datetime for display. Pass relative=True for '5d ago' style."""
    if dt is None:
        return "[dim]never[/dim]"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if relative:
        now = datetime.now(tz=timezone.utc)
        delta = now - dt
        days = delta.days
        if days < 0:
            return "just now"
        if days == 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 30:
            return f"{days}d ago"
        if days < 365:
            return f"{days // 30}mo ago"
        return f"{days // 365}y ago"
    return dt.strftime("%Y-%m-%d")


def format_due(due: Optional[datetime]) -> str:
    """Format a next_due datetime with colour-coded urgency."""
    if due is None:
        return "[dim]not scheduled[/dim]"
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    delta = due - now
    days = delta.days
    if days < 0:
        overdue = -days
        return f"[red]overdue {overdue}d[/red]"
    if days == 0:
        return "[yellow]today[/yellow]"
    if days == 1:
        return "[cyan]tomorrow[/cyan]"
    return f"[dim]in {days}d[/dim]"
