"""The main help dialog for the application."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown

from par_infini_sweeper import __application_title__, __version__

HELP: Final[str] = f"""
# {__application_title__} v{__version__} Help

"""


class HelpDialog(ModalScreen[None]):
    """Modal dialog that shows the application's help."""

    DEFAULT_CSS = """
    HelpDialog {
        align: center middle;
        & > Vertical {
            border: thick $primary 50%;
            width: 80%;
            height: 80%;
            background: $boost;
            Markdown {
                height: 1fr;
            }
        }
    }
    """

    BINDINGS = [
        Binding("escape,f1", "dismiss(None)", "", show=False),
    ]

    def compose(self) -> ComposeResult:
        """Compose the help screen."""
        help_text = (Path(__file__).parent.parent / "help.md").read_text(encoding="utf-8")
        with Vertical():
            yield Markdown(HELP + help_text)
            with Center():
                yield Button("Close", variant="primary")

    def on_mount(self) -> None:
        """Configure the help screen once the DOM is ready."""
        # It seems that some things inside Markdown can still grab focus;
        # which might not be right. Let's ensure that can't happen here.
        self.query_one(Markdown).can_focus_children = False
        self.query_one(Button).focus()

    def on_button_pressed(self) -> None:
        """React to button press."""
        self.dismiss(None)

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """A link was clicked in the help."""
        self.app.open_url(event.href)
