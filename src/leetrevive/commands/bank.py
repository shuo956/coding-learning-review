from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import typer
from rich.table import Table

from ..db import get_all_problems, get_db_path, get_reviews
from ..utils import console, difficulty_display, err_console, format_dt, format_due


def bank(
    due: bool = typer.Option(False, "--due", help="Show only problems due or overdue"),
    weak: bool = typer.Option(
        False, "--weak", help="Show only weak problems (avg score < 1.5 or never reviewed)"
    ),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    pattern: Optional[str] = typer.Option(None, "--pattern", help="Filter by pattern"),
    limit: int = typer.Option(20, "--limit", "-l", min=1, help="Max rows to show"),
) -> None:
    """Browse your review bank with optional filters."""
    db_path = get_db_path()
    if not db_path.exists():
        err_console.print(
            "[error]Database not found.[/error] Run [bold]leetrevive init[/bold] first."
        )
        raise typer.Exit(1)

    problems = get_all_problems(db_path)
    if not problems:
        console.print(
            "[warning]No problems in bank yet.[/warning] "
            "Add some with [bold]leetrevive add[/bold]."
        )
        return

    now = datetime.now(tz=timezone.utc)

    if due:
        problems = [
            p for p in problems
            if p.next_due_at is None or p.next_due_at <= now
        ]

    if tag:
        tag_lower = tag.lower()
        problems = [p for p in problems if any(t.lower() == tag_lower for t in p.tags)]

    if pattern:
        pat_lower = pattern.lower()
        problems = [
            p for p in problems if p.pattern and p.pattern.lower() == pat_lower
        ]

    if weak:
        filtered = []
        for p in problems:
            history = get_reviews(p.problem_id, db_path)
            if not history:
                filtered.append(p)
            elif sum(r.score for r in history) / len(history) < 1.5:
                filtered.append(p)
        problems = filtered

    total = len(problems)
    problems = problems[:limit]

    suffix = f" — showing {len(problems)} of {total}" if total > limit else ""
    table = Table(
        title=f"[bold]Review Bank[/bold]{suffix}",
        show_header=True,
        header_style="bold",
        show_lines=False,
        expand=False,
        padding=(0, 1),
    )
    table.add_column("ID", width=6)
    table.add_column("Title", min_width=28)
    table.add_column("Diff", width=8)
    table.add_column("Tags", min_width=18)
    table.add_column("Pattern", min_width=16)
    table.add_column("Last Review", width=12)
    table.add_column("Next Due", width=14)

    for p in problems:
        table.add_row(
            p.problem_id,
            p.title,
            difficulty_display(p.difficulty),
            ", ".join(p.tags) if p.tags else "[dim]-[/dim]",
            p.pattern or "[dim]-[/dim]",
            format_dt(p.last_reviewed_at, relative=True),
            format_due(p.next_due_at),
        )

    console.print(table)
