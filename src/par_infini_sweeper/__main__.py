"""Main application"""

from __future__ import annotations

from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console

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
    version: Annotated[  # pylint: disable=unused-argument
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """Main function."""
    sweeper_app: MinesweeperApp = MinesweeperApp()
    sweeper_app.run()


if __name__ == "__main__":
    app()
