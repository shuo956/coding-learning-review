from __future__ import annotations

from typing import Optional

import typer

from . import __version__
from .commands.add import add
from .commands.bank import bank
from .commands.done import done
from .commands.open_ import open_problem
from .commands.review import review_problem
from .commands.serve import serve
from .commands.stats import stats
from .commands.today import today
from .utils import console

app = typer.Typer(
    name="leetrevive",
    help="Terminal-first LeetCode review assistant.",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", is_eager=True, help="Print version and exit."
    ),
) -> None:
    if version:
        typer.echo(f"leetrevive {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def init() -> None:
    """Initialize the local data directory and SQLite database."""
    from . import db as _db

    path = _db.init_db()
    console.print(f"[success]Initialized[/success] database at [cyan]{path}[/cyan]")
    console.print("Run [bold]leetrevive add <id> <title>[/bold] to add your first problem.")


app.command("add")(add)
app.command("done")(done)
app.command("today")(today)
app.command("bank")(bank)
app.command("review")(review_problem)
app.command("open")(open_problem)
app.command("stats")(stats)
app.command("serve")(serve)


def main() -> None:
    app()
