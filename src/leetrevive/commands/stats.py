from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import typer
from rich.panel import Panel
from rich.table import Table

from ..db import get_all_problems, get_all_reviews, get_db_path
from ..utils import console, err_console


def _review_streak(review_dates: list[date]) -> int:
    """Return the number of consecutive days (ending today or yesterday) with reviews."""
    if not review_dates:
        return 0

    today = datetime.now(tz=timezone.utc).date()
    unique = sorted(set(review_dates), reverse=True)

    # Streak is valid only if it ends today or yesterday
    if unique[0] < today - timedelta(days=1):
        return 0

    streak = 0
    expected = unique[0]
    for d in unique:
        if d == expected:
            streak += 1
            expected = d - timedelta(days=1)
        else:
            break
    return streak


def stats() -> None:
    """Show review statistics and learning progress."""
    db_path = get_db_path()
    if not db_path.exists():
        err_console.print(
            "[error]Database not found.[/error] Run [bold]leetrevive init[/bold] first."
        )
        raise typer.Exit(1)

    problems = get_all_problems(db_path)
    reviews = get_all_reviews(db_path)

    now = datetime.now(tz=timezone.utc)
    today_date = now.date()

    total_problems = len(problems)
    total_reviews = len(reviews)

    due_today = sum(
        1 for p in problems
        if p.next_due_at is not None and p.next_due_at.date() == today_date
    )
    overdue = sum(
        1 for p in problems
        if p.next_due_at is not None and p.next_due_at.date() < today_date
    )

    review_dates = [r.reviewed_at.date() for r in reviews]
    streak = _review_streak(review_dates)

    # ------------------------------------------------------------------
    # Weak patterns and tags (lowest average score)
    # ------------------------------------------------------------------
    pattern_scores: dict[str, list[int]] = defaultdict(list)
    tag_scores: dict[str, list[int]] = defaultdict(list)
    reviews_by_pid: dict[str, list[int]] = defaultdict(list)

    for r in reviews:
        reviews_by_pid[r.problem_id].append(r.score)

    for p in problems:
        scores = reviews_by_pid.get(p.problem_id, [])
        if not scores:
            continue
        avg = sum(scores) / len(scores)
        if p.pattern:
            pattern_scores[p.pattern].append(avg)
        for tag in p.tags:
            tag_scores[tag].append(avg)

    weak_patterns = sorted(
        [(k, sum(v) / len(v)) for k, v in pattern_scores.items()],
        key=lambda x: x[1],
    )[:5]

    weak_tags = sorted(
        [(k, sum(v) / len(v)) for k, v in tag_scores.items()],
        key=lambda x: x[1],
    )[:5]

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    streak_color = "green" if streak >= 3 else ("yellow" if streak >= 1 else "dim")
    summary = "\n".join(
        [
            f"Total problems:   [bold]{total_problems}[/bold]",
            f"Total reviews:    [bold]{total_reviews}[/bold]",
            f"Due today:        [yellow]{due_today}[/yellow]",
            f"Overdue:          [red]{overdue}[/red]",
            f"Review streak:    [{streak_color}]{streak} day{'s' if streak != 1 else ''}[/{streak_color}]",
        ]
    )
    console.print(Panel(summary, title="[bold]Overview[/bold]", expand=False))

    if weak_patterns:
        pt = Table(
            title="Weakest Patterns",
            show_header=True,
            header_style="bold",
            expand=False,
            padding=(0, 1),
        )
        pt.add_column("Pattern", min_width=22)
        pt.add_column("Avg Score", width=10, justify="right")
        for name, avg in weak_patterns:
            color = "red" if avg < 1.0 else ("yellow" if avg < 2.0 else "green")
            pt.add_row(name, f"[{color}]{avg:.1f}[/{color}]")
        console.print(pt)

    if weak_tags:
        tt = Table(
            title="Weakest Tags",
            show_header=True,
            header_style="bold",
            expand=False,
            padding=(0, 1),
        )
        tt.add_column("Tag", min_width=22)
        tt.add_column("Avg Score", width=10, justify="right")
        for name, avg in weak_tags:
            color = "red" if avg < 1.0 else ("yellow" if avg < 2.0 else "green")
            tt.add_row(name, f"[{color}]{avg:.1f}[/{color}]")
        console.print(tt)

    if not weak_patterns and not weak_tags:
        console.print("[dim]No pattern/tag stats yet — add reviews to see breakdown.[/dim]")
