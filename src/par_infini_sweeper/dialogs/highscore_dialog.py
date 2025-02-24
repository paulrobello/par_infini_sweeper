"""Provides a base modal dialog for showing text to the user."""

from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, TabbedContent

from par_infini_sweeper import db
from par_infini_sweeper.enums import GameMode
from par_infini_sweeper.utils import format_duration


class HighscoreDialog(ModalScreen[None]):
    """Base modal dialog for showing information."""

    DEFAULT_CSS = """
	HighscoreDialog {
		align: center middle;
	}

	#main {
		background: $boost;
		width: 1fr;
		height: 1fr;
		border: round $primary;
	}
	#tc {
	}

	HighscoreDialog .spaced {
		padding: 1 4;
	}

	HighscoreDialog .scores {
		min-width: 100%;
	}
	#local_vs {
		width: 1fr;
		height: 1fr;
	}
	DataTable {
	    border: round $primary;
	}
	"""

    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("escape", "dismiss(None)", "Return", show=True),
    ]

    def __init__(self) -> None:  # noqa: F821
        """Initialise the dialog."""
        super().__init__()

        self.tc = TabbedContent("Local", "Internet", id="tc")

    @work
    async def load_local_data(self) -> None:
        """Load local data."""
        self.query_exactly_one("#local_vs", VerticalScroll).loading = True
        try:
            data = db.get_highscores()
            for mode, data in data.items():
                rows = [("Name", "Score", "Time")]
                for row in data:
                    rows.append((row["nickname"], str(row["score"]), format_duration(row["duration"])))
                table = self.query_exactly_one(f"#local_dt_{mode}", DataTable)
                table.clear(True)
                table.add_columns(*rows[0])
                table.add_rows(rows[1:])
        except Exception as _:
            self.notify("Error loading remote data", severity="error")
        finally:
            self.query_exactly_one("#local_vs", VerticalScroll).loading = False

    def compose_local(self) -> ComposeResult:
        with VerticalScroll(id="local_vs") as vs:
            vs.loading = True
            for mode in GameMode:
                dt = DataTable(
                    id=f"local_dt_{mode}",
                    zebra_stripes=True,
                    show_cursor=False,
                    cursor_type="row",
                    classes="spaced scores",
                )
                dt.border_title = mode.name.capitalize()
                yield dt

    @work
    async def load_remote_data(self) -> None:
        """Load internet data."""
        self.query_exactly_one("#internet_vs", VerticalScroll).loading = True
        try:
            data = db.get_internet_highscores()
            for mode, data in data.items():
                rows = [("Name", "Score", "Time")]
                for row in data:
                    rows.append((row["nickname"], str(row["score"]), format_duration(row["duration"])))
                table = self.query_exactly_one(f"#dt_{mode}", DataTable)
                table.clear(True)
                table.add_columns(*rows[0])
                table.add_rows(rows[1:])
                self.notify("Loaded remote data")
        except Exception as _:
            self.notify("Error loading remote data", severity="error")
        finally:
            self.query_exactly_one("#internet_vs", VerticalScroll).loading = False

    def compose_internet(self) -> ComposeResult:
        with VerticalScroll(id="internet_vs") as vs:
            vs.loading = True
            for mode in GameMode:
                dt = DataTable(
                    id=f"dt_{mode}",
                    zebra_stripes=True,
                    show_cursor=False,
                    cursor_type="row",
                    classes="spaced scores",
                )
                dt.border_title = mode.name.capitalize()
                yield dt

    def compose(self) -> ComposeResult:
        """Compose the content of the modal dialog."""
        yield Footer()
        with Vertical(id="main"):
            with self.tc:
                yield from self.compose_local()
                yield from self.compose_internet()

    def action_refresh(self) -> None:
        """Refresh the data in the dialog."""
        self.load_local_data()
        self.load_remote_data()

    def on_mount(self) -> None:
        """Configure the dialog once the DOM has loaded."""
        self.query_one(DataTable).focus()
        self.load_local_data()
        # self.load_remote_data()

    @on(TabbedContent.TabActivated)
    def on_remote_tab_selected(self, event: TabbedContent.TabActivated) -> None:
        """Load the remote data when the tab is selected."""
        # self.notify(event.tab.id or "?")
        if event.tab.id == "--content-tab-tab-2":
            self.load_remote_data()
