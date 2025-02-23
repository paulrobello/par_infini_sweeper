"""Main application"""

from __future__ import annotations

import os
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from textual_serve.server import Server

from par_infini_sweeper import __application_title__, __version__
from par_infini_sweeper.minesweeper_app import MinesweeperApp

app = typer.Typer()
console = Console(stderr=True)

load_dotenv()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        print(f"{__application_title__}: {__version__}")
        raise typer.Exit()


@app.command()
def main(
    start_server: Annotated[
        bool, typer.Option("--server", "-s", help="Start webserver that allows app to be played in a browser")
    ] = False,
    user_name: Annotated[str, typer.Option("--user", "-u", help="User name to use")] = os.environ.get("USER", "user"),
    nickname: Annotated[str | None, typer.Option("--nick", "-n", help="Set user nickname")] = None,
    version: Annotated[  # pylint: disable=unused-argument
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Main function."""
    if start_server:
        server_args: list[str] = ["pim"]
        if user_name:
            server_args.extend(["--user", user_name])
        if nickname:
            server_args.extend(["--nick", nickname])
        server = Server(" ".join(server_args))
        server.serve()
        return

    sweeper_app: MinesweeperApp = MinesweeperApp(user_name, nickname)
    sweeper_app.run()


if __name__ == "__main__":
    app()
