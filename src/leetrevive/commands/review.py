from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from ..db import get_db_path, get_problem, get_reviews
from ..meta import get_insight
from ..utils import (
    SCORE_LABELS,
    console,
    difficulty_display,
    err_console,
    format_dt,
    format_due,
)


def review_problem(
    problem_id: str = typer.Argument(..., help="Problem number to inspect"),
) -> None:
    """Show full details and review history for a problem."""
    db_path = get_db_path()
    if not db_path.exists():
        err_console.print(
            "[error]Database not found.[/error] Run [bold]leetrevive init[/bold] first."
        )
        raise typer.Exit(1)

    problem = get_problem(problem_id, db_path)
    if not problem:
        err_console.print(f"[error]Problem {problem_id!r} not found.[/error]")
        raise typer.Exit(1)

    reviews = get_reviews(problem_id, db_path)
    avg_str = (
        f"{sum(r.score for r in reviews) / len(reviews):.1f} / 3"
        if reviews
        else "[dim]n/a[/dim]"
    )

    insight = get_insight(problem_id)
    lines = [
        f"[bold]#{problem.problem_id}[/bold] — {problem.title}",
        f"Difficulty:   {difficulty_display(problem.difficulty)}",
        f"Tags:         {', '.join(problem.tags) if problem.tags else '[dim]none[/dim]'}",
        f"Pattern:      {problem.pattern or '[dim]none[/dim]'}",
        f"Source:       {problem.source}",
        f"URL:          [cyan]{problem.url or '[dim]not set[/dim]'}[/cyan]",
        f"Added:        {format_dt(problem.created_at)}",
        f"Last review:  {format_dt(problem.last_reviewed_at, relative=True)}",
        f"Next due:     {format_due(problem.next_due_at)}",
        f"Reviews:      [bold]{len(reviews)}[/bold]   Avg score: [bold]{avg_str}[/bold]",
    ]
    if insight:
        lines.insert(2, f"[yellow]💡 Insight:[/yellow]  {insight}")
    console.print(Panel("\n".join(lines), title="Problem", expand=False))

    if not reviews:
        console.print("[dim]No review history yet.[/dim]")
        return

    table = Table(
        title="Review History (newest first)",
        show_header=True,
        header_style="bold",
        show_lines=True,
        expand=False,
        padding=(0, 1),
    )
    table.add_column("Date", width=12)
    table.add_column("Score", width=18)
    table.add_column("Min", width=5, justify="right")
    table.add_column("Note", min_width=20)
    table.add_column("Mistake", min_width=20)

    for r in reversed(reviews):
        table.add_row(
            format_dt(r.reviewed_at),
            SCORE_LABELS.get(r.score, str(r.score)),
            str(r.minutes) if r.minutes is not None else "[dim]-[/dim]",
            r.note or "[dim]-[/dim]",
            r.mistake or "[dim]-[/dim]",
        )

    console.print(table)
