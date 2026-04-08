from __future__ import annotations

import webbrowser

import typer

from ..db import get_db_path, get_problem
from ..utils import console, err_console


def open_problem(
    problem_id: str = typer.Argument(..., help="Problem number to open in browser"),
) -> None:
    """Open the original problem URL in your default browser."""
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

    if not problem.url:
        err_console.print(
            f"[error]No URL stored for problem {problem_id}.[/error] "
            "Re-add it with [bold]--url[/bold] to set one."
        )
        raise typer.Exit(1)

    console.print(f"Opening [cyan]{problem.url}[/cyan]")
    webbrowser.open(problem.url)
