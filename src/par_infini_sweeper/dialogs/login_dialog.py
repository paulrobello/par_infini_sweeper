"""Provides login / out / nickname management dialog."""

from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent
from typing import Literal

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, Static

from par_infini_sweeper.data_structures import GameState
from par_infini_sweeper.dialogs.input_dialog import InputDialog
from par_infini_sweeper.utils import escape_brackets


class AuthDialog(ModalScreen[None]):
    """Provides login / out / nickname management dialog."""

    DEFAULT_CSS = """
	AuthDialog {
		align: center middle;
		.spaced {
		    padding: 1 4;
	    }
	}

	#main {
	    border-title-color: red;
		border: round $primary;
		background: $boost;
		width: 1fr;
		height: 1fr;
		padding: 1;
		Horizontal {
		    width: 1fr;
		    height: 3;
		    align: left middle;
		    Label {
		        margin: 1 1 0 0;
		    }
        }
	}

	#blurb {
		width: 1fr;
		margin: 0 0 1 0;
	}
	#net_nickname{
	    margin-right: 1;
	}
	Button {
	    margin-bottom: 1;
	}
	"""

    BINDINGS = [
        Binding("q,escape", "dismiss(None)", "Return", show=True),
    ]

    @dataclass
    class OauthDone(Message):
        status: Literal["success", "error"]
        msg: str

    def __init__(self, game_state: GameState) -> None:  # noqa: F821
        """Initialise the dialog."""
        super().__init__()

        self.game_state = game_state

    @work(thread=True, exclusive=True, group="login")
    async def do_login(self) -> None:
        """Do OAUTH2 flow."""
        try:
            if self.game_state.auth_client:
                self.post_message(AuthDialog.OauthDone("success", "Logged in"))
        except Exception as e:
            self.notify(str(e), severity="error")
            self.post_message(AuthDialog.OauthDone("error", str(e)))

    @on(OauthDone)
    async def oauth_done(self, event: OauthDone) -> None:
        """OAUTH done."""
        self.query_exactly_one("#main").loading = False
        if event.status == "success":
            self.notify(event.msg)
        else:
            self.notify(event.msg, severity="error")
        await self.recompose()

    def compose(self) -> ComposeResult:
        """Compose the content of the modal dialog."""
        logged_in = self.game_state.is_logged_in()

        yield Footer()
        with Vertical(id="main") as v:
            if self.game_state.game_over:
                v.border_title = "Game Over"
            with Horizontal():
                if logged_in:
                    yield Label("Net Nickname: ", id="net_nick_label")
                    yield Label(self.game_state.user["net_nickname"] or "Not set", id="net_nickname")
                    nickname_button = Button.warning(
                        "Change Net Nickname" if self.game_state.user["net_nickname"] else "Register Net Nickname",
                        id="change_nickname",
                    )
                    yield nickname_button
                else:
                    yield Static("\n[yellow]Login to set nickname")

            yield Static(
                dedent("""
                Clicking Login uses an OAUTH social provider such as Google, Facebook, Github.
                See the Readme or full help if you want to know more about how this works and our data policies."""),
                id="blurb",
            )
            login_button = Button.success("Login", id="login")
            logout_button = Button.error("Logout", id="logout")
            login_button.display = not logged_in
            logout_button.display = not login_button.display
            yield login_button
            yield logout_button
            if not self.game_state.score():
                yield Static("No score to upload", id="score_label")
            else:
                yield Static(
                    " - ".join(
                        [
                            f"Difficulty: [#00FF00]{self.game_state.difficulty}[/]",
                            f"Solved: {self.game_state.num_solved} / {self.game_state.num_subgrids}",
                            f"Score: [#00FF00]{self.game_state.score()}[/]",
                            f"Time: {self.game_state.time_played}\n",
                        ]
                    )
                )
                if not logged_in:
                    yield Static("\n[yellow]Login to upload score")
                else:
                    yield Button.success("Upload Score", id="upload")

    @on(Button.Pressed, "#login")
    def login_click(self) -> None:
        """Login button clicked"""
        self.query_exactly_one("#main").loading = True
        self.do_login()

    @on(Button.Pressed, "#logout")
    async def logout_click(self) -> None:
        """Logout button clicked"""
        self.game_state.logout()
        await self.recompose()

    @on(Button.Pressed, "#upload")
    async def upload_click(self) -> None:
        """Upload button clicked"""
        if not self.game_state.is_logged_in():
            self.notify("Not logged in", severity="error")
            return
        try:
            result = self.game_state.post_internet_score()
            if result.status != "success":
                raise Exception(result.message)
            self.notify("Score uploaded", severity="information")
        except Exception as e:
            self.notify(escape_brackets(str(e)), severity="error")

    @on(Button.Pressed, "#change_nickname")
    @work
    async def change_nickname_click(self) -> None:
        """Change net_nickname button clicked"""
        new_nickname = await self.app.push_screen_wait(
            InputDialog(
                "New Nickname",
                self.game_state.user["net_nickname"] or self.game_state.user["nickname"],
                "Change Nickname",
                "Name may only contain letters, numbers and . - _  \n",
            )
        )
        if not new_nickname or len(new_nickname) < 2 or len(new_nickname) > 30:
            self.notify("Nickname must be between 2 and 30 characters", severity="error")
            return
        try:
            result = self.game_state.change_internet_nickname(new_nickname)
            if result.status != "success":
                raise Exception(result.message)
            else:
                self.notify(escape_brackets(result.message or "Nickname changed"), severity="information")
        except Exception as e:
            self.notify(escape_brackets(str(e)), severity="error")
            return
        await self.recompose()

    def on_mount(self) -> None:
        """Configure the dialog once the DOM has loaded."""
