from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.events import MouseDown, MouseEvent, MouseMove, MouseUp
from textual.geometry import Offset
from textual.widget import Widget
from textual.widgets import Static

from par_infini_sweeper import db
from par_infini_sweeper.data_structures import Cell, GameState, SubGrid
from par_infini_sweeper.dialogs.information import InformationDialog


class MainGrid(Widget, can_focus=True):
    """Widget that renders the infinite minesweeper grid and handles mouse interactions."""

    BINDINGS = [
        Binding(key="o", action="origin", description="Origin"),
        Binding(key="c", action="center", description="Center"),
        Binding(key="d", action="debug", description="Debug", show=False),
        Binding(key="ctrl+d", action="xray", description="X-Ray", show=False),
        Binding(key="h", action="highscores", description="Highscores"),
    ]
    ALLOW_SELECT = False

    def __init__(self, game_state: GameState, info: Static, debug_panel: Static) -> None:
        super().__init__()
        self.info = info
        self.debug_panel = debug_panel
        self.game_state: GameState = game_state
        self.board_offset = Offset(game_state.offset.x, game_state.offset.y)
        self.drag_start: tuple[int, int] | None = None
        self.drag_threshold: int = 2  # minimal cells to distinguish a drag from a click
        self.is_dragging: bool = False
        self.debug = False
        self.xray = False
        self.debug_panel.display = self.debug

    def on_mount(self) -> None:
        """Center subgrid 0,0"""
        if self.board_offset.is_origin:
            self.call_after_refresh(self.action_center)
        self.update_info()
        self.set_interval(1, self.update_info)

    def update_info(self) -> None:
        """Update the info bar with the current game state."""
        if not self.game_state.game_over:
            self.game_state.play_duration += 1
        game_over_text = "" if not self.game_state.game_over else " - [red]Game Over![/]"
        self.info.update(
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
                ]
            )
        )

    def render(self) -> Text:
        """Render the visible portion of the grid as text. Each cell is represented by two characters."""
        width: int = self.size.width
        height: int = self.size.height
        cell_width: int = 2  # each cell is 2 characters wide
        cells_x: int = width // cell_width
        cells_y: int = height
        lines: list[str] = []
        for row in range(cells_y):
            line: str = ""
            for col in range(cells_x):
                gx: int = col + self.board_offset.x
                gy: int = row + self.board_offset.y
                cell_char: str = self.get_cell_representation(gx, gy)
                line += cell_char
            lines.append(line)
        return Text.from_markup("\n".join(lines))

    def action_center(self) -> None:
        c = self.game_state.compute_board_center()
        self.board_offset = Offset(-self.size.width // 4 + (c[0]), -self.size.height // 4 - (c[1] + 4))
        self.game_state.offset = Offset(self.board_offset.x, self.board_offset.y)
        self.refresh()

    def action_origin(self) -> None:
        self.board_offset = Offset(-self.size.width // 4 + 5, -self.size.height // 4 - 3)
        self.game_state.offset = Offset(self.board_offset.x, self.board_offset.y)
        self.refresh()

    def action_highscores(self) -> None:
        data = db.get_highscores()
        scores = "\n".join([f"{row['nickname']} - {row['score']}" for row in data])
        self.app.push_screen(InformationDialog("Highscores", scores))

    def action_debug(self) -> None:
        self.debug = not self.debug
        self.debug_panel.display = self.debug

    def action_xray(self) -> None:
        self.xray= not self.xray
        self.refresh()

    @staticmethod
    def count_to_color(count: int) -> str:
        """Return a color based on the count of adjacent mines."""
        if count == 0:
            return "#FFFFFF"
        elif count == 1:
            return "#00FF00"
        elif count == 2:
            return "#5050FF"
        elif count == 3:
            return "#9327FF"
        elif count == 4:
            return "#FF00FF"
        elif count == 5:
            return "#FFFF00"
        elif count == 6:
            return "#FFA600"
        elif count == 7:
            return "#FF0000"
        else:
            return "#000000"

    def get_cell_representation(self, gx: int, gy: int) -> str:
        """
        Return a string representation of the cell at global coordinates (gx, gy).

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        Returns:
            str: The string representation of the cell
        """
        cell: Cell | None = self.global_to_cell(gx, gy)

        if not cell:
            return "[#C0C0C0]? [/]"  # placeholder for not-yet generated subgrid

        if self.xray or cell.uncovered:
            if cell.is_mine:
                return "[red]💣[/]"
            count: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
            if cell.parent.solved:
                color = "#A0A0A0"
            else:
                color =  "#FFFF00" if cell.highlighted else self.count_to_color(count[1])
            if cell.parent.solved:
                if count[1] == 0:
                    return f"[{color}]. [/]"
            return f"[{color}]{count[1]} [/]" if count[1] > 0 else "  "
        else:
            color = "#FFFF00" if cell.highlighted else "#E0E0E0"
            return "[red]⚑ [/]" if cell.marked else f"[{color}]■ [/]"


    def count_adjacent_flags_mines(self, gx: int, gy: int) -> tuple[int, int]:
        """
        Count the number of mines adjacent to the cell at (gx, gy). Generates any adjacent subgrid that has not yet been created.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        Returns:
            tuple[int, int]: A tuple containing the number of flagged cells and the number of mines

        """
        mine_count: int = 0
        flag_count: int = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: tuple[int, int] = (nx // 8, ny // 8)
                if n_sg not in self.game_state.subgrids:
                    continue
                    # if self.debug:
                    #     continue
                    # sg = SubGrid(n_sg, self.game_state.difficulty)
                    # sg.changed = True
                    # self.game_state.subgrids[n_sg] = sg
                subgrid: SubGrid = self.game_state.subgrids[n_sg]
                lx: int = nx % 8
                ly: int = ny % 8
                if subgrid.cells[ly][lx].is_mine:
                    mine_count += 1
                if subgrid.cells[ly][lx].marked:
                    flag_count += 1
        return flag_count, mine_count

    def cell_has_uncovered_neighbor(self, gx: int, gy: int) -> bool:
        """
        Check whether the cell at (gx, gy) has at least one uncovered neighbor.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        Returns:
            bool: True if the cell has at least one uncovered neighbor, False otherwise
        """
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: tuple[int, int] = (nx // 8, ny // 8)
                if n_sg in self.game_state.subgrids:
                    subgrid: SubGrid = self.game_state.subgrids[n_sg]
                    lx: int = nx % 8
                    ly: int = ny % 8
                    if subgrid.cells[ly][lx].uncovered or subgrid.cells[ly][lx].is_mine:
                        return True
        return False

    def check_subgrid_solved(self, sg_coord: tuple[int, int]) -> None:
        """
        Mark a subgrid as solved if the all cells that dont contain a mine have been uncovered.

        Args:
            sg_coord (tuple[int, int]): The coordinates of the subgrid
        """
        subgrid: SubGrid = self.game_state.subgrids[sg_coord]
        if subgrid.solved:
            return
        for row in subgrid.cells:
            for cell in row:
                if not cell.is_mine and not cell.uncovered:
                    return
        subgrid.solved = True
        self.game_state.num_solved += 1
        for row in subgrid.cells:
            for cell in row:
                if cell.is_mine and not cell.marked:
                    cell.marked = True

    def reveal_cell(self, gx: int, gy: int, depth: int = 0) -> None:
        """
        Reveal the cell at global coordinates (gx, gy). If it is a mine the game ends. Also, generate any adjacent subgrids as needed.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            depth (int): The depth of the recursion (to prevent infinite recursion)
        """
        if self.game_state.game_over:
            return
        sg_coord: tuple[int, int] = (gx // 8, gy // 8)

        # For non-initial subgrids, only allow a reveal if at least one neighbor is uncovered.
        if sg_coord != (0, 0) and not self.cell_has_uncovered_neighbor(gx, gy):
            self.notify("No uncovered neighbors")
            return

        cell: Cell | None = self.global_to_cell(gx, gy, True)
        # Do nothing if cell is marked or uncovered.
        if not cell or cell.marked or cell.uncovered:
            return

        # Uncover the cell only if we are not in reveal surrounding mode
        cell.uncovered = True
        if cell.uncovered and cell.is_mine:
            self.game_state.game_over = True
            self.game_state.save()
            self.game_state.save_score()
            self.notify("Game Over! You hit a mine.", severity="error")
            self.refresh()
            return
        # Generate any adjacent subgrids.
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: tuple[int, int] = (nx // 8, ny // 8)
                if n_sg not in self.game_state.subgrids:
                    self.game_state.subgrids[n_sg] = SubGrid(self.game_state, n_sg, self.game_state.difficulty)

        # Prevent infinite recursion by limiting depth.
        if depth < 250:
            # If the cell has 0 neighboring mines, recursively reveal its neighbors.
            counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
            if counts[1] == 0:
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx: int = gx + dx
                        ny: int = gy + dy
                        self.reveal_cell(nx, ny, depth + 1)
        self.check_subgrid_solved(sg_coord)

    def global_to_cell(self, gx: int, gy: int, create_if_needed: bool = False) -> Cell | None:
        """
        Convert global coordinates to local cell coordinates.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            create_if_needed (bool): Whether to create the subgrid if it does not exist

        Returns:
            Cell | None: The cell at the given coordinates, or None if the subgrid does not exist and create_if_needed is False
        """
        sg_coord: tuple[int, int] = (gx // 8, gy // 8)
        local_x: int = gx % 8
        local_y: int = gy % 8
        if sg_coord not in self.game_state.subgrids:
            if not create_if_needed:
                return None
            self.game_state.subgrids[sg_coord] = SubGrid(self.game_state, sg_coord, self.game_state.difficulty)
        subgrid: SubGrid = self.game_state.subgrids[sg_coord]
        return subgrid.cells[local_y][local_x]

    def reveal_surround(self, gx: int, gy: int) -> None:
        """
        Reveal surrounding cells if the cell at (gx, gy) is uncovered and the number of flagged cells matches the number of mines.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        """
        if self.game_state.game_over:
            return
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell or not cell.uncovered:
            return
        counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
        if not counts[0]:
            # self.notify("No flagged cells", severity="warning")
            return
        if cell.uncovered:
            if counts[0] != counts[1]:
                # self.notify("Flag count does not match mine count", severity="error")
                return

            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx: int = gx + dx
                    ny: int = gy + dy
                    self.reveal_cell(nx, ny)
        self.game_state.save()
        self.refresh()

    def highlight_neighbors(self, gx: int, gy: int) -> None:
        """
        Highlight the cell neighbors around (gx, gy).
        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
        """
        if self.game_state.game_over:
            return
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell or not cell.uncovered:
            return
        counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
        if not counts[1]:
            return

        # cell.highlighted = True
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                cell = self.global_to_cell(gx + dx, gy + dy)
                if cell and not cell.uncovered:
                    cell.highlighted = True
        self.refresh()

    def toggle_mark(self, gx: int, gy: int, surround: bool = False) -> None:
        """
        Toggle the mark (flag) on the cell at global coordinates (gx, gy).

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            surround (bool): Whether to reveal surrounding cells if the cell is already uncovered
        """
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell:
            return
        if cell.uncovered:
            if not surround:
                return
            self.reveal_surround(gx, gy)
            return
        cell.marked = not cell.marked
        self.game_state.save()
        self.refresh()

    def mouse_to_grid(self, event: MouseEvent) -> tuple[int, int]:
        """
        Convert mouse event coordinates to global cell coordinates.

        Args:
            event (MouseEvent): The mouse event

        Returns:
            tuple[int, int]: The global cell coordinates (gx, gy)
        """
        cell_width: int = 2
        cell_height: int = 1
        col: int = event.x // cell_width
        row: int = event.y // cell_height
        gx: int = col + self.board_offset.x
        gy: int = row + self.board_offset.y
        return gx, gy

    def handle_click(self, event: MouseDown | MouseUp) -> None:
        """
        Handle a click event by converting the event position to a global cell coordinate.
        Left-click reveals a cell; middle-click toggles a mark.

        Args:
            event (MouseDown | MouseUp): The mouse event
        """
        if self.is_dragging:
            return
        gx, gy = self.mouse_to_grid(event)
        if event.button == 1 and not (event.shift or event.ctrl):
            self.reveal_cell(gx, gy)
        elif event.button == 1 and (event.shift or event.ctrl):
            self.toggle_mark(gx, gy, True)

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
        self.drag_start = (event.x, event.y)

        if event.button == 1 and (event.shift or event.ctrl):
            gx, gy = self.mouse_to_grid(event)
            self.highlight_neighbors(gx, gy)

    def on_mouse_move(self, event: MouseMove) -> None:
        """
        Handle mouse move events to detect dragging.

        Args:
            event (MouseMove): The mouse move event
        """
        self.adjust_mouse_pos(event)

        if self.drag_start is not None:
            dx: int = event.x - self.drag_start[0]
            dy: int = event.y - self.drag_start[1]
            if abs(dx) >= self.drag_threshold or abs(dy) >= self.drag_threshold:
                # Update the view offset in the opposite direction of the drag.
                self.board_offset -= Offset(dx, dy)
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
        self.game_state.offset = self.board_offset
        if self.drag_start is not None:
            self.handle_click(event)
        self.drag_start = None
        self.is_dragging = False
        self.game_state.clear_highlighted()
        self.game_state.save()
        self.refresh()
        if self.game_state.game_over:
            self.app.push_screen(
                InformationDialog("Game Over", f"[red]You hit a mine.[/]\nScore: [yellow]{self.game_state.score()}")
            )
