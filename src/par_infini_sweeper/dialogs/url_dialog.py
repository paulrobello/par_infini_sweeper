"""Provides a base modal dialog for showing text to the user."""

from __future__ import annotations

from rich.console import ConsoleRenderable, RichCast
from rich.text import TextType
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.visual import SupportsVisual
from textual.widgets import Button, Static


class UrlDialog(ModalScreen[None]):
    """Base modal dialog for showing information."""

    DEFAULT_CSS = """
	UrlDialog {
		align: center middle;
	}

	UrlDialog Center {
		width: 100%;
	}

	UrlDialog > Vertical {
		background: $boost;
		min-width: 30%;
		width: auto;
		height: auto;
		border: round $primary;
	}

	UrlDialog Static {
		width: auto;
	}

	UrlDialog .spaced {
		padding: 1 4;
	}

	UrlDialog #message {
		min-width: 100%;
	}
	"""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "", show=False),
    ]

    def __init__(self, title: TextType, message: ConsoleRenderable | RichCast | str | SupportsVisual, url: str) -> None:  # noqa: F821
        """Initialise the dialog."""
        super().__init__()
        self._title = title
        self._message = message
        self._url = url

    def compose(self) -> ComposeResult:
        """Compose the content of the modal dialog."""
        with Vertical():
            with Center():
                yield Static(self._title, classes="spaced")
            yield Static(self._message, id="message", classes="spaced")
            with Center(classes="spaced"):
                yield Button("Copy", variant="success")

    def on_mount(self) -> None:
        """Configure the dialog once the DOM has loaded."""
        self.query_one(Button).focus()

    def on_button_pressed(self) -> None:
        """Handle the OK button being pressed."""
        self.app.copy_to_clipboard(self._url)
        self.notify("URL copied to clipboard")
        self.dismiss(None)
