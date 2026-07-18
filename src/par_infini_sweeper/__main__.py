"""Main application"""

from __future__ import annotations

import os
from typing import Annotated

# ARC-007: load_dotenv + USER_AGENT must run BEFORE any par_infini_sweeper
# submodule import — auth.py reads AUTH0_DOMAIN / AUTH0_CLIENT_ID at module
# load time, and requests reads USER_AGENT for its default User-Agent header.
# Previously these lived in par_infini_sweeper.__init__ (package-import side
# effect); moved here so ``import par_infini_sweeper`` is side-effect-free.
# They sit at module scope rather than inside main() so the env is populated
# before the imports below this block fire.
from dotenv import load_dotenv

load_dotenv()

from par_infini_sweeper import __application_title__, __version__  # noqa: E402

os.environ["USER_AGENT"] = f"{__application_title__} {__version__}"

import typer  # noqa: E402
from rich.console import Console  # noqa: E402
from textual_serve.server import Server  # noqa: E402

from par_infini_sweeper.models import validate_nickname  # noqa: E402
from par_infini_sweeper.pim_app import PimApp  # noqa: E402

app = typer.Typer()
console = Console(stderr=True)


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

    # ARC-019: one-time stderr warning if AUTH0_CLIENT_ID was not provided via
    # env, so devs know they're hitting the production auth tenant by default.
    from par_infini_sweeper.auth import warn_if_default_auth0_client_id

    warn_if_default_auth0_client_id()

    if user_name and len(user_name) > 20:
        console.print("User name must be 20 characters or less")
        raise typer.Exit(1)
    if nickname:
        try:
            validate_nickname(nickname)
        except ValueError as e:
            console.print(str(e))
            raise typer.Exit(1) from e

    if start_server:
        server_args: list[str] = ["pim"]
        if user_name:
            server_args.extend(["--user", user_name])
        if nickname:
            server_args.extend(["--nick", nickname])
        server = Server(" ".join(server_args))
        server.serve()
        return

    sweeper_app: PimApp = PimApp(user_name, nickname)
    sweeper_app.run()


if __name__ == "__main__":
    main_app = app()
