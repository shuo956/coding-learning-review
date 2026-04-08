from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import typer

from ..db import get_db_path, get_problem, insert_problem
from ..meta import lookup as meta_lookup
from ..models import Problem
from ..utils import build_leetcode_url, console, err_console


def add(
    problem_id: str = typer.Argument(..., help="LeetCode problem number, e.g. 146"),
    title: Optional[str] = typer.Argument(
        None,
        help="Problem title — omit to auto-fill from bundled metadata",
    ),
    url: Optional[str] = typer.Option(
        None, "--url", "-u", help="Problem URL (auto-generated when source is leetcode)"
    ),
    difficulty: Optional[str] = typer.Option(
        None, "--difficulty", "-d", help="easy | medium | hard"
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Comma-separated tags, e.g. 'array,hashmap'"
    ),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", "-p", help="Algorithm pattern, e.g. 'sliding-window'"
    ),
    source: str = typer.Option("leetcode", "--source", "-s", help="Problem source"),
) -> None:
    """Add a solved problem to your review bank.

    When the problem ID is known (LeetCode problems 1-3800+), title,
    difficulty, tags, and URL are filled automatically from bundled metadata.
    Any flag you pass explicitly overrides the bundled value.

    Examples:

      leetrevive add 146                          # fully auto

      leetrevive add 146 --pattern "design"       # auto + extra field

      leetrevive add 146 --tags "hashmap,lru"     # override tags

      leetrevive add 9999 "My Custom Problem"     # unknown ID, manual
    """
    db_path = get_db_path()
    if not db_path.exists():
        err_console.print(
            "[error]Database not found.[/error] Run [bold]leetrevive init[/bold] first."
        )
        raise typer.Exit(1)

    if get_problem(problem_id, db_path):
        err_console.print(
            f"[error]Problem {problem_id!r} already exists.[/error] "
            "Use [bold]leetrevive review[/bold] to inspect it."
        )
        raise typer.Exit(1)

    # ------------------------------------------------------------------
    # Resolve metadata: bundled data first, explicit flags override
    # ------------------------------------------------------------------
    meta = meta_lookup(problem_id)

    resolved_title = title or (meta.title if meta else None)
    if not resolved_title:
        err_console.print(
            f"[error]Unknown problem ID {problem_id!r}.[/error] "
            "Provide a title:  leetrevive add {problem_id} \"My Title\""
        )
        raise typer.Exit(1)

    resolved_difficulty = (
        difficulty.lower() if difficulty
        else (meta.difficulty if meta else None)
    )
    if resolved_difficulty and resolved_difficulty not in {"easy", "medium", "hard"}:
        err_console.print(
            f"[error]Invalid difficulty:[/error] {resolved_difficulty!r}. "
            "Choose from: easy, medium, hard."
        )
        raise typer.Exit(1)

    # Tags: explicit flag wins; otherwise use bundled tags
    if tags is not None:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif meta:
        tags_list = list(meta.tags)
    else:
        tags_list = []

    # URL: explicit flag > bundled meta > auto-generate from title
    resolved_url = url or (meta.url if meta else None)
    if not resolved_url and source == "leetcode":
        resolved_url = build_leetcode_url(resolved_title)

    problem = Problem(
        problem_id=problem_id,
        title=resolved_title,
        url=resolved_url,
        source=source,
        difficulty=resolved_difficulty,
        tags=tags_list,
        pattern=pattern,
        created_at=datetime.now(tz=timezone.utc),
        last_reviewed_at=None,
        next_due_at=None,
    )

    insert_problem(problem, db_path)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    source_label = "[dim](from metadata)[/dim]" if meta and not title else ""
    console.print(
        f"[success]Added[/success] [bold]#{problem_id}[/bold] — {resolved_title} {source_label}"
    )
    if resolved_url:
        console.print(f"  URL:        [cyan]{resolved_url}[/cyan]")
    if resolved_difficulty:
        console.print(f"  Difficulty: {resolved_difficulty.capitalize()}")
    if tags_list:
        console.print(f"  Tags:       {', '.join(tags_list)}")
    if pattern:
        console.print(f"  Pattern:    {pattern}")
    if meta and meta.paid:
        console.print("  [yellow]Note: this is a paid-only problem on LeetCode.[/yellow]")
