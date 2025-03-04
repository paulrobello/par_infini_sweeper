"""Provides a dialog for getting difficulty level from the user."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from par_infini_sweeper.enums import GameDifficulty


class DifficultyDialog(ModalScreen[GameDifficulty | None]):
    """Provides a dialog for getting difficulty level from the user."""

    DEFAULT_CSS = """
	DifficultyDialog {
		align: center middle;
	}

	DifficultyDialog > Vertical {
		background: $panel;
		height: auto;
		width: auto;
		border: thick $secondary;
		padding: 1;

        Center {
            width: 50;
        }
	}

	DifficultyDialog > Vertical > * {
		width: auto;
		height: auto;
	}

	DifficultyDialog Static {
		width: auto;
	}

	DifficultyDialog .spaced {
		padding: 1;
	}

	DifficultyDialog #question {
		min-width: 100%;
		border-top: solid $secondary;
		border-bottom: solid $secondary;
	}

	DifficultyDialog Button {
		margin-right: 1;
	}

	DifficultyDialog #buttons {
		width: 100%;
		align-horizontal: right;
		padding-right: 1;
	}
	"""

    BINDINGS = [
        Binding("left,up", "app.focus_previous", "", show=False),
        Binding("right,down", "app.focus_next", "", show=False),
        Binding("escape", "dismiss(None)", "", show=False),
    ]

    def __init__(
        self,
    ) -> None:
        """Initialise the yes/no dialog."""
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose the content of the dialog."""
        with Vertical():
            yield Static(
                "If you want to post your score to the internet,\nmake sure you do so before starting a new game!\n",
            )

            with Center():
                yield Static("Difficulty", classes="spaced")
                yield Button("Easy", id="easy")
                yield Button("Medium", id="medium")
                yield Button("Hard", id="hard")

    def on_mount(self) -> None:
        """Configure the dialog once the DOM is ready."""
        self.query(Button).first().focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button being pressed on the dialog."""
        self.dismiss(GameDifficulty(event.button.id))
