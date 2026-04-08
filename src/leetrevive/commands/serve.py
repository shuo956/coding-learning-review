from __future__ import annotations

import webbrowser
from typing import Optional

import typer

from ..utils import console, err_console


def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address"),
    port: int = typer.Option(8080, "--port", "-p", help="Port to listen on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
) -> None:
    """Start the web UI at http://localhost:8080."""
    try:
        import uvicorn  # noqa: F401
        from fastapi.staticfiles import StaticFiles  # noqa: F401
    except ImportError:
        err_console.print(
            "[error]Web dependencies not installed.[/error]\n"
            "Run: [bold]pip install leetrevive\\[web][/bold]"
        )
        raise typer.Exit(1)

    from ..db import get_db_path, init_db

    db_path = get_db_path()
    if not db_path.exists():
        err_console.print(
            "[error]Database not found.[/error] Run [bold]leetrevive init[/bold] first."
        )
        raise typer.Exit(1)

    # Re-run init to ensure knowledge_notes table exists (safe, idempotent)
    init_db(db_path)

    url = f"http://{host}:{port}"
    console.print(f"[success]Starting[/success] leetrevive web UI at [cyan]{url}[/cyan]")
    console.print("Press [bold]Ctrl+C[/bold] to stop.\n")

    if not no_browser:
        # Small delay so the server is up before the browser tries to load
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    import uvicorn
    from ..web.server import app

    uvicorn.run(app, host=host, port=port, log_level="warning")
