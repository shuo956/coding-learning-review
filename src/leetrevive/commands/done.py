from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import typer

from ..db import get_db_path, get_problem, get_reviews, insert_review, update_problem_review
from ..models import Review
from ..scheduler import compute_next_due
from ..utils import console, err_console

_SCORE_LABELS = {0: "Blank", 1: "Partial", 2: "Struggled", 3: "Clean"}
_SCORE_COLORS = {0: "red", 1: "yellow", 2: "blue", 3: "green"}


def done(
    problem_id: str = typer.Argument(..., help="Problem number to mark as reviewed"),
    score: int = typer.Option(
        ...,
        "--score",
        "-s",
        prompt="Score (0=blank  1=partial  2=struggled  3=clean)",
        min=0,
        max=3,
        help="Review quality: 0 blank | 1 partial | 2 struggled | 3 clean",
    ),
    minutes: Optional[int] = typer.Option(
        None, "--minutes", "-m", help="Time spent solving (minutes)"
    ),
    note: Optional[str] = typer.Option(
        None, "--note", "-n", help="Short note about this attempt"
    ),
    mistake: Optional[str] = typer.Option(
        None, "--mistake", help="What went wrong or what to remember"
    ),
) -> None:
    """Record a review attempt and update the next due date."""
    db_path = get_db_path()
    if not db_path.exists():
        err_console.print(
            "[error]Database not found.[/error] Run [bold]leetrevive init[/bold] first."
        )
        raise typer.Exit(1)

    problem = get_problem(problem_id, db_path)
    if not problem:
        err_console.print(
            f"[error]Problem {problem_id!r} not found.[/error] "
            "Add it first with [bold]leetrevive add[/bold]."
        )
        raise typer.Exit(1)

    now = datetime.now(tz=timezone.utc)
    history = get_reviews(problem_id, db_path)

    review = Review(
        problem_id=problem_id,
        reviewed_at=now,
        score=score,
        minutes=minutes,
        note=note,
        mistake=mistake,
    )
    insert_review(review, db_path)

    next_due = compute_next_due(score, history, now)
    update_problem_review(problem_id, now, next_due, db_path)

    color = _SCORE_COLORS[score]
    label = _SCORE_LABELS[score]
    review_count = len(history) + 1

    console.print(
        f"[success]Recorded[/success] [bold]#{problem_id}[/bold] — {problem.title}"
    )
    console.print(f"  Score:      [{color}]{score} — {label}[/{color}]")
    if minutes is not None:
        console.print(f"  Time:       {minutes} min")
    console.print(
        f"  Next due:   [cyan]{next_due.strftime('%Y-%m-%d')}[/cyan]"
        f"  [dim](review #{review_count})[/dim]"
    )
