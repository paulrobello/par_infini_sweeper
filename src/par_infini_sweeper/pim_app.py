"""
Infinite Minesweeper implemented with Python 3.12 and the textual library.

The game grid is composed of subgrids (8×8 each). The first (initial) subgrid
is generated at (0, 0) and new subgrids are generated on demand as you uncover cells.
Left-clicking a cell will reveal it (unless it is marked) and if it’s a mine the game ends.
Right-clicking or Shift + Left-clicking toggles a mine mark on that cell.
Only in the initial subgrid may any cell be clicked; in other subgrids only cells bordering an already uncovered cell are clickable.
"""

from __future__ import annotations

import logging
import os
import socketserver
from typing import Any

from rich.console import ConsoleRenderable, RichCast
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.messages import ExitApp
from textual.visual import SupportsVisual, Visual
from textual.widgets import Footer, Header, Static

from par_infini_sweeper import __application_title__
from par_infini_sweeper.data_structures import GameState
from par_infini_sweeper.dialogs.difficulty_dialog import DifficultyDialog
from par_infini_sweeper.dialogs.help_dialog import HelpDialog
from par_infini_sweeper.dialogs.highscore_dialog import HighscoreDialog
from par_infini_sweeper.dialogs.information import InformationDialog
from par_infini_sweeper.dialogs.login_dialog import AuthDialog
from par_infini_sweeper.dialogs.theme_dialog import ThemeDialog
from par_infini_sweeper.dialogs.url_dialog import UrlDialog
from par_infini_sweeper.enums import GameDifficulty
from par_infini_sweeper.main_grid import MainGrid
from par_infini_sweeper.messages import AuthServerError, ShowURL, WebServerStarted, WebServerStopped

logger = logging.getLogger(__name__)


class PimApp(App):
    """
    Textual App for Infinite Minesweeper.
    Bindings:
      - n: New Game (prompts for difficulty)
      - h: Highscores
      - t: Change Theme
      - q: Quit
      - f1: Help
    """

    TITLE = __application_title__
    ENABLE_COMMAND_PALETTE = False
    ALLOW_SELECT = False
    CSS_PATH = "pim.tcss"
    BINDINGS = [
        Binding(key="n", action="new_game", description="New Game"),
        Binding(key="h", action="highscores", description="Highscores"),
        Binding(key="t", action="change_theme", description="Change Theme"),
        Binding(key="a", action="auth", description="Authentication"),
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="f1", action="help", description="Help", show=True),
    ]

    def __init__(self, user_name: str | None = None, nickname: str | None = None, **kwargs: Any) -> None:
        if not user_name:
            user_name = os.environ.get("USER", "user")
        # ARC-017: heavy DB I/O deferred to on_mount so construction is cheap
        # and the event loop starts before SQLite/auth bootstrap runs. The
        # previous constructor opened a connection, ran init_db (DDL +
        # migrations), and ran GameState.load (multiple SELECTs) — all
        # synchronously before run() could paint the first frame.
        self._user_name: str = user_name
        self._nickname: str | None = nickname
        super().__init__(**kwargs)
        self.info = Static("Info", id="info")
        self.debug_panel = Static("Debug", id="debug")
        self.game_state: GameState | None = None
        self.sweeper_widget: MainGrid | None = None
        self._web_server: socketserver.TCPServer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()
        with Vertical():
            yield self.info
            with Horizontal():
                # sweeper_widget is mounted dynamically by on_mount once the
                # deferred DB I/O completes (ARC-017). Yield debug_panel now so
                # the layout is stable before the game state loads.
                yield self.debug_panel

    def on_mount(self) -> None:
        # ARC-006/ARC-007: storage init (mkdir, legacy rename, backup) runs
        # ONCE at startup, not inside every get_db_connection. ARC-017: DB
        # I/O moved out of __init__ so construction stays cheap.
        from par_infini_sweeper import db

        db.init_storage()
        with db.get_db_connection() as conn:
            db.init_db(conn, self._user_name)
        self.game_state = GameState.load(None, self._user_name, self._nickname)
        self.sweeper_widget = MainGrid(self.game_state, self.info, self.debug_panel)
        # Insert into the existing Horizontal container, before debug_panel,
        # so the layout matches the pre-deferral compose tree.
        self.query_one(Horizontal).mount(self.sweeper_widget, before=self.debug_panel)
        self.theme = self.game_state.theme
        self.sweeper_widget.focus()

    @work
    async def action_change_theme(self) -> None:
        """An action to change the theme."""
        assert self.game_state is not None  # populated by on_mount before any keypress
        self.game_state.theme = await self.push_screen_wait(ThemeDialog())
        self.game_state.save()

    def action_help(self) -> None:
        """Show help screen"""
        self.app.push_screen(HelpDialog())

    def action_highscores(self) -> None:
        """Display the highscores for each game mode."""
        assert self.game_state is not None  # populated by on_mount before any keypress
        self.app.push_screen(HighscoreDialog(self.game_state))

    def action_auth(self) -> None:
        """Display the auth dialog."""
        assert self.game_state is not None  # populated by on_mount before any keypress
        self.app.push_screen(AuthDialog(self.game_state))

    def set_debug(self, text: ConsoleRenderable | RichCast | str | SupportsVisual | Visual) -> None:
        self.debug_panel.update(text)

    @work
    async def action_new_game(self) -> None:
        """
        Start a new game. Prompts the user for a difficulty (easy, medium, or hard),
        resets the game state, and saves it.
        """
        assert self.game_state is not None  # populated by on_mount before any keypress
        assert self.sweeper_widget is not None
        difficulty: GameDifficulty | None = await self.push_screen_wait(DifficultyDialog())
        if difficulty is None:
            return
        self.game_state.difficulty = difficulty
        self.game_state.new_game()
        self.sweeper_widget.action_center()

    @on(ShowURL)
    def show_url(self, event: ShowURL) -> None:
        self.push_screen(
            UrlDialog(
                "OAUTH Login",
                "If your browser does not automatically open, click Copy and paste the url into a browser to start login.",
                event.url,
            )
        )

    @on(AuthServerError)
    def auth_server_error(self, event: AuthServerError) -> None:
        """ARC-018: surface a port-in-use / listener failure to the user."""
        self.push_screen(InformationDialog("Authentication Error", event.error))

    @on(WebServerStarted)
    def webserver_started(self, event: WebServerStarted):
        self._web_server = event.server
        # stop the server if its still running after 5 minutes
        self.set_timer(300, self.stop_webserver)

    @on(WebServerStopped)
    def webserver_stopped(self):
        self._web_server = None

    def stop_webserver(self) -> None:
        if self._web_server:
            try:
                self._web_server.shutdown()
            except OSError:
                # QA-004: webserver shutdown is best-effort cleanup (socket may
                # already be torn down by the OS during process exit). Keep
                # swallowing but surface it at debug so port-reuse diagnostics
                # aren't completely invisible.
                logger.debug("webserver shutdown raised, ignoring", exc_info=True)
            finally:
                self._web_server = None

    @on(ExitApp)
    def do_exit_app(self) -> None:
        self.stop_webserver()
