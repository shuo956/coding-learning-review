from __future__ import annotations

from datetime import datetime, timezone

import typer
from rich.table import Table

from ..db import get_all_problems, get_all_reviews, get_db_path
from ..scheduler import pick_today
from ..utils import console, difficulty_display, err_console, format_due


def today() -> None:
    """Show 3 recommended problems to review today."""
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

    reviews = get_all_reviews(db_path)
    now = datetime.now(tz=timezone.utc)
    picks = pick_today(problems, reviews, now)

    if not picks:
        console.print(
            "[success]Nothing due today![/success] "
            "Great job keeping up with your reviews."
        )
        return

    date_str = now.strftime("%Y-%m-%d")
    table = Table(
        title=f"[bold]Today's Review — {date_str}[/bold]",
        show_header=True,
        header_style="bold",
        show_lines=False,
        expand=False,
        padding=(0, 1),
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("ID", width=6)
    table.add_column("Title", min_width=28)
    table.add_column("Diff", width=8)
    table.add_column("Due", width=14)
    table.add_column("Reason", style="dim italic", min_width=22)

    for i, pick in enumerate(picks, 1):
        p = pick.problem
        table.add_row(
            str(i),
            p.problem_id,
            p.title,
            difficulty_display(p.difficulty),
            format_due(p.next_due_at),
            pick.reason,
        )

    console.print(table)
    console.print(
        "\nTip: [bold]leetrevive open <id>[/bold] to open in browser  •  "
        "[bold]leetrevive done <id>[/bold] to record a review"
    )
