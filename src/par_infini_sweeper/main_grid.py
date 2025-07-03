from __future__ import annotations

from rich.text import Text
from textual import work
from textual.binding import Binding
from textual.events import MouseDown, MouseEvent, MouseMove, MouseUp
from textual.geometry import Offset
from textual.widget import Widget
from textual.widgets import Static

from par_infini_sweeper.data_structures import GameState, GridPos, SubGrid
from par_infini_sweeper.dialogs.highscore_dialog import HighscoreDialog
from par_infini_sweeper.dialogs.information import InformationDialog


class MainGrid(Widget, can_focus=True):
    """Widget that renders the infinite minesweeper grid and handles mouse interactions."""

    BINDINGS = [
        Binding(key="o", action="origin", description="Origin"),
        Binding(key="c", action="center", description="Center", show=False),
        Binding(key="d", action="debug", description="Debug", show=False),
        Binding(key="p", action="pause", description="Pause"),
        Binding(key="s", action="subgrid_highlight", description="Subgrid Highlight"),
        Binding(key="ctrl+d", action="xray", description="X-Ray", show=False),
    ]
    ALLOW_SELECT = False

    def __init__(self, game_state: GameState, info_bar: Static, debug_panel: Static) -> None:
        super().__init__()
        game_state.parent = self
        self.info_bar = info_bar
        self.debug_panel = debug_panel
        self.game_state: GameState = game_state
        self.drag_start: GridPos | None = None
        self.drag_threshold: int = 2  # minimal cells to distinguish a drag from a click
        self.is_dragging: bool = False
        self.debug = False
        self.debug_panel.display = self.debug
        self.mouse_sg: SubGrid | None = None

    def on_mount(self) -> None:
        if self.game_state.offset.is_origin:
            self.call_after_refresh(self.action_center)
        self.update_info()
        self.set_interval(1, self.update_info)

    def update_info(self) -> None:
        """Update the info bar with the current game state."""
        if not self.game_state.game_over and not self.game_state.paused:
            self.game_state.duration += 1

        game_over_text = "" if not self.game_state.game_over else " - [red]Game Over![/]"
        self.info_bar.update(
            " - ".join(
                [
                    f" [#5F5FFF]{self.game_state.user['nickname']}[/]",
                    f"Difficulty: [#00FF00]{self.game_state.difficulty}[/]",
                    f"Solved: {self.game_state.num_solved} / {self.game_state.num_subgrids}",
                    f"Score: [#00FF00]{self.game_state.score()}[/]",
                    f"Time: {self.game_state.time_played}{game_over_text}",
                ]
            )
        )
        self.debug_panel.update(
            "\n".join(
                [
                    f"NumHighlighted: {len(self.game_state.highlighted_cells)}",
                    f"NumSaved: {self.game_state.num_grids_saved}",
                    f"BoardOffset: {self.game_state.offset}",
                    f"BoardCenter: {self.game_state.compute_board_center()}",
                ]
            )
        )

    def render(self) -> Text:
        """Render the visible portion of the grid as text. Each cell is represented by two characters."""
        cells_x: int = self.size.width // 2  # each cell is 2 characters wide
        cells_y: int = self.size.height
        lines = [
            "".join(
                self.game_state.get_cell_representation(col + self.game_state.offset.x, row + self.game_state.offset.y)
                for col in range(cells_x)
            )
            for row in range(cells_y)
        ]
        return Text.from_markup("\n".join(lines))

    def action_center(self) -> None:
        """Center view on center of board"""
        c = self.game_state.compute_board_center()
        self.game_state.offset = Offset(-self.size.width // 4 + c.x, -self.size.height // 4 + c.y)
        self.game_state.save()
        self.refresh()

    def action_origin(self) -> None:
        """Center view on center of first subgrid"""
        self.game_state.offset = Offset(-self.size.width // 4 + 5, -self.size.height // 4 - 3)
        self.game_state.save()
        self.refresh()

    def action_debug(self) -> None:
        """Toggle the debug mode for the game."""
        self.debug = not self.debug
        self.debug_panel.display = self.debug

    def action_xray(self) -> None:
        """Toggle the x-ray mode for the game."""
        self.game_state.xray = not self.game_state.xray
        self.refresh()

    @work
    async def action_pause(self) -> None:
        self.game_state.paused = True
        await self.app.push_screen_wait(InformationDialog("Paused", "Press ESC to continue"))
        self.game_state.paused = False

    def handle_click(self, event: MouseDown | MouseUp) -> None:
        """
        Handle a click event by converting the event position to a global cell coordinate.
        Left-click reveals a cell; middle-click toggles a mark.

        Args:
            event (MouseDown | MouseUp): The mouse event
        """
        if self.is_dragging:
            return
        gx, gy = self.game_state.mouse_to_global_grid_coords(event)
        if event.button == 1 and not (event.shift or event.ctrl):
            self.game_state.reveal_cell(gx, gy)
            self.game_state.first_click = False
        elif event.button == 1 and (event.shift or event.ctrl):
            self.game_state.toggle_mark(gx, gy, True)

    def adjust_mouse_pos(self, event: MouseEvent) -> None:
        """
        Adjust the mouse position to account for padding and cell size.

        Args:
            event (MouseEvent): The mouse event

        """
        event._x -= self.styles.padding.width + 1
        event._y -= self.styles.padding.height + 1

    def on_mouse_down(self, event: MouseDown) -> None:
        """
        Record mouse down for drag detection.

        Args:
            event (MouseDown): The mouse down event
        """
        self.adjust_mouse_pos(event)
        self.drag_start = event.x, event.y

        if event.button == 1 and (event.shift or event.ctrl):
            gx, gy = self.game_state.mouse_to_global_grid_coords(event)
            self.game_state.highlight_neighbors(gx, gy)

    def on_mouse_move(self, event: MouseMove) -> None:
        """
        Handle mouse move events to detect dragging.

        Args:
            event (MouseMove): The mouse move event
        """
        self.adjust_mouse_pos(event)
        self.game_state.update_mouse_info(event)
        # cell = self.game_state.global_to_cell(self.sg_coord)
        # if cell:
        #     if self.mouse_sg != cell.parent:
        #         if self.mouse_sg:
        #             self.mouse_sg.highlighted = False
        #         self.mouse_sg = cell.parent
        #         self.mouse_sg.highlighted = True
        if self.drag_start is not None:
            dx: int = event.x - self.drag_start[0]
            dy: int = event.y - self.drag_start[1]
            if abs(dx) >= self.drag_threshold or abs(dy) >= self.drag_threshold:
                # Update the view offset in the opposite direction of the drag.
                self.game_state.offset -= Offset(dx, dy)
                self.drag_start = (event.x, event.y)
                self.is_dragging = True
                self.refresh()

    def on_mouse_up(self, event: MouseUp) -> None:
        """
        Check if mouse up is a click or drag and handle accordingly.

        Args:
            event (MouseUp): The mouse
        """
        # If the drag was minimal, treat this as a click.
        if self.game_state.game_over:
            self.drag_start = None
            self.is_dragging = False
            return

        self.adjust_mouse_pos(event)
        self.game_state.offset = self.game_state.offset
        if self.drag_start is not None:
            self.handle_click(event)
        self.drag_start = None
        self.is_dragging = False
        self.game_state.clear_highlighted()
        self.game_state.save()
        self.refresh()
        if self.game_state.game_over:
            self.app.push_screen(HighscoreDialog(self.game_state))

            self.app.push_screen(
                InformationDialog("Game Over", f"[red]You hit a mine.[/]\nScore: [yellow]{self.game_state.score()}")
            )

    def action_subgrid_highlight(self) -> None:
        self.game_state.highlighted_subgrid = not self.game_state.highlighted_subgrid
        if not self.game_state.highlighted_subgrid:
            self.refresh()
