from __future__ import annotations

import random
import time
from typing import Any

import orjson
from textual.geometry import Offset
from textual.widget import Widget

from par_infini_sweeper import db
from par_infini_sweeper.db import get_user
from par_infini_sweeper.enums import GameDifficulty, GameMode

GridPos = tuple[int, int]

mine_counts: dict[GameDifficulty, int] = {GameDifficulty.EASY: 8, GameDifficulty.MEDIUM: 12, GameDifficulty.HARD: 16}
difficulty_mult: dict[GameDifficulty, int] = {GameDifficulty.EASY: 1, GameDifficulty.MEDIUM: 2, GameDifficulty.HARD: 3}

"""Return a color based on the count of adjacent mines."""
count_to_color: dict[int, str] = {
    0: "#FFFFFF",
    1: "#00FF00",
    2: "#5050FF",
    3: "#9327FF",
    4: "#FF00FF",
    5: "#FFFF00",
    6: "#FFA600",
    7: "#FF0000",
    8: "#A00000",
}


class Cell:
    """Represents a single cell in a subgrid."""

    def __init__(self, parent: SubGrid, is_mine: bool, marked: bool = False, uncovered: bool = False) -> None:
        self._parent = parent
        self._is_mine: bool = is_mine
        self._marked: bool = marked
        self._uncovered: bool = uncovered
        self._changed: bool = False
        self._highlighted: bool = False

    @property
    def is_mine(self) -> bool:
        return self._is_mine

    @is_mine.setter
    def is_mine(self, value: bool) -> None:
        if self._is_mine != value:
            self._is_mine = value
            self.changed = True

    @property
    def marked(self) -> bool:
        return self._marked

    @marked.setter
    def marked(self, value: bool) -> None:
        if self._marked != value:
            self._marked = value
            self.changed = True

    @property
    def uncovered(self) -> bool:
        return self._uncovered

    @uncovered.setter
    def uncovered(self, value: bool) -> None:
        if self._uncovered != value:
            self._uncovered = value
            self.changed = True

    @property
    def highlighted(self) -> bool:
        return self._highlighted

    @highlighted.setter
    def highlighted(self, value: bool) -> None:
        if self._highlighted != value:
            self._highlighted = value
            self.parent.parent.highlighted_cells.add(self) if value else self.parent.parent.highlighted_cells.discard(
                self
            )

    @property
    def parent(self) -> SubGrid:
        return self._parent

    @property
    def changed(self) -> bool:
        return self._changed

    @changed.setter
    def changed(self, value: bool) -> None:
        if self._changed != value:
            self._changed = value
            if value:
                self._parent.changed = True

    def to_dict(self) -> dict[str, bool]:
        """Return a dictionary representation of this cell."""
        return {"is_mine": self.is_mine, "marked": self.marked, "uncovered": self.uncovered}

    @staticmethod
    def from_dict(parent: SubGrid, data: dict[str, bool]) -> Cell:
        """Create a Cell instance from its dictionary representation."""
        return Cell(parent, data["is_mine"], data["marked"], data["uncovered"])


class SubGrid:
    """Represents an 8×8 subgrid of cells."""

    def __init__(
        self,
        parent: GameState,
        pos: GridPos,
        difficulty: GameDifficulty | None = None,
    ) -> None:
        """
        Initialize a subgrid at position `pos` with the given difficulty.
        Optionally ensure that the cell at local coordinate safe_pos is mine‑free.

        Args:
            parent (GameState): The parent game state.
            pos (GridPos): The position of the subgrid.
            difficulty (GameDifficulty | None): The difficulty level of the game.
        """
        self._changed: bool = False
        self.pos: GridPos = pos
        self.cells: list[list[Cell]] = self.generate_cells(difficulty) if difficulty else []
        self.solved: bool = False
        self._parent: GameState = parent

    @property
    def parent(self) -> GameState:
        return self._parent

    @property
    def changed(self) -> bool:
        return self._changed

    @changed.setter
    def changed(self, value: bool) -> None:
        if self._changed != value:
            self._changed = value
            if value:
                self.parent.changed_subgrids.add(self)

    def generate_cells(self, difficulty: GameDifficulty) -> list[list[Cell]]:
        """
        Generate an 8×8 grid of cells with mines distributed according to difficulty.
        The number of mines per subgrid is adjusted as follows:
          - easy: 8 mines
          - medium: 12 mines
          - hard: 16 mines
        """

        num_mines: int = mine_counts.get(difficulty, 8)
        positions: list[GridPos] = [(x, y) for y in range(8) for x in range(8)]
        mine_positions: list[GridPos] = random.sample(positions, num_mines)
        grid: list[list[Cell]] = []
        for y in range(8):
            row: list[Cell] = []
            for x in range(8):
                is_mine: bool = (x, y) in mine_positions
                row.append(Cell(self, is_mine))
            grid.append(row)
        return grid

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of this subgrid."""
        return {
            "pos": self.pos,
            "cells": [[cell.to_dict() for cell in row] for row in self.cells],
            "solved": self.solved,
        }

    def clear_changed(self) -> None:
        """Clear the changed flag for all cells in the subgrid."""
        for row in self.cells:
            for cell in row:
                cell.changed = False
        self.changed = False

    @property
    def key_str(self) -> str:
        """Return a unique key for this subgrid."""
        return f"{self.pos[0]},{self.pos[1]}"

    @staticmethod
    def from_dict(parent: GameState, data: dict[str, Any]) -> SubGrid:
        """Create a SubGrid instance from its dictionary representation."""
        sg: SubGrid = SubGrid(parent, tuple(data["pos"]))
        sg.cells = [[Cell.from_dict(sg, cell) for cell in row] for row in data["cells"]]
        sg.solved = data.get("solved", False)
        if sg.solved:
            return sg
        # Ensure that the subgrid is solved if all non-mine cells are uncovered.
        for row in sg.cells:
            for cell in row:
                if not cell.is_mine and not cell.uncovered:
                    return sg
        sg.solved = True

        for row in sg.cells:
            for cell in row:
                if cell.is_mine and not cell.marked:
                    cell.marked = True

        return sg


class GameState:
    """Represents the overall game state including difficulty and all subgrids."""

    def __init__(self, parent: Widget | None, user: dict[str, Any]) -> None:
        self.parent = parent
        self.game_mode: GameMode = GameMode.INFINITE
        self.user: dict[str, Any] = user
        self.difficulty: GameDifficulty = user["prefs"]["difficulty"]
        self.theme: str = user["prefs"]["theme"]
        self.subgrids: dict[GridPos, SubGrid] = {}
        self.subgrids[(0, 0)] = SubGrid(self, (0, 0), self.difficulty)
        game: dict[str, Any] = user["game"]
        offset: list[str] = game["board_offset"].split(",")
        assert len(offset) == 2
        self.offset = Offset(int(offset[0]), int(offset[1]))
        self.num_solved: int = 0
        self.started_ts: int = int(time.time())
        self.play_duration: int = game["play_duration"]
        self.game_over: bool = game["game_over"]
        self.num_grids_saved: int = 0
        self.highlighted_cells: set[Cell] = set()
        self.changed_subgrids: set[SubGrid] = set()
        self.paused: bool = False
        self.xray: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the game state."""
        return {
            "user_id": self.user["id"],
            "theme": self.theme,
            "difficulty": self.difficulty,
            "game_over": self.game_over,
            "started_ts": self.started_ts,
            "play_duration": self.play_duration,
            "offset": (self.offset.x, self.offset.y),
            "subgrids": {f"{k[0]},{k[1]}": sg.to_dict() for k, sg in self.subgrids.items()},
        }

    def new_game(self) -> None:
        """Start a new game by resetting the game state."""

        sg = SubGrid(self, (0, 0), self.difficulty)
        sg.changed = True
        self.subgrids = {(0, 0): sg}
        self.offset = Offset(0, 0)
        self.num_solved = 0
        self.started_ts = int(time.time())
        self.play_duration = 0
        self.num_grids_saved = 0
        self.game_over = False
        self.clear_highlighted()
        self.clear_changed()
        self.xray = False

        conn = db.get_db_connection()
        with conn:
            cursor = conn.cursor()
            # Update user preferences.
            cursor.execute(
                """DELETE FROM grids WHERE user_id = ?""",
                (self.user["id"],),
            )
        self.save()

    def compute_board_center(self) -> Offset:
        """Compute the center of the game board in cells based on subgrid positions."""
        c = (0, 0)
        for k in self.subgrids.keys():
            c = (c[0] + k[0] * 8, c[1] + k[1] * 8)

        return Offset(c[0] // len(self.subgrids) + 5, c[1] // len(self.subgrids) - 3)

    @property
    def num_changed(self) -> int:
        return sum(1 for sg in self.subgrids.values() if sg.changed)

    @property
    def num_subgrids(self) -> int:
        return len(self.subgrids)

    @staticmethod
    def load(parent: Widget | None, user_name: str, nickname: str | None = None) -> GameState:
        """
        Load the game state from the SQLite database or create a new one.

        Args:
            parent (Widget): The parent widget.
            user_name (str): The name of the user.
            nickname (str | None): The nickname of the user.
        """
        with db.get_db_connection() as conn:
            user = get_user(conn, user_name, nickname)
            user_id = user["id"]
            game = user["game"]
            state = GameState(parent, user)

            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM grids WHERE game_id = ? AND user_id = ?",
                (
                    game["id"],
                    user_id,
                ),
            )

            state.num_solved = 0
            row = cursor.fetchone()
            while row:
                key_parts: list[str] = row["sub_grid_id"].split(",")
                coords: GridPos = (int(key_parts[0]), int(key_parts[1]))
                sg_data = orjson.loads(row["grid_data"])
                sg: SubGrid = SubGrid.from_dict(state, sg_data)
                state.subgrids[coords] = sg
                if sg.solved:
                    state.num_solved += 1
                row = cursor.fetchone()

        return state

    def score(self) -> int:
        """Calculate the score based on the number of solved subgrids and difficulty."""
        return self.num_solved * mine_counts.get(self.difficulty, 8)

    def save_score(self) -> None:
        score = self.score()
        if score == 0:
            return
        conn = db.get_db_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO highscores (game_id, user_id, score) VALUES (?, ?,?)""",
                (self.user["game"]["id"], self.user["id"], score),
            )

    def save(self) -> int:
        """
        Save the game state to the SQLite database.

        Returns:
            int: The number of subgrids saved.
        """
        with db.get_db_connection() as conn:
            self.user["prefs"] = {"theme": self.theme, "difficulty": self.difficulty}
            user_id = self.user["id"]
            self.user["game"]["play_duration"] = self.play_duration
            self.user["game"]["game_over"] = self.game_over
            self.user["game"]["board_offset"] = f"{self.offset.x},{self.offset.y}"

            cursor = conn.cursor()
            cursor.execute(
                """UPDATE user_prefs SET theme = ?, difficulty = ? WHERE id = ?""",
                (self.theme, self.difficulty.value, user_id),
            )
            cursor.execute(
                """UPDATE games SET game_over = ?, board_offset = ?, play_duration = ? WHERE user_id = ?""",
                (
                    self.user["game"]["game_over"],
                    self.user["game"]["board_offset"],
                    self.user["game"]["play_duration"],
                    user_id,
                ),
            )

            # Save each subgrid using upsert.
            self.num_grids_saved = 0
            for sg in self.changed_subgrids:
                self.num_grids_saved += 1
                sg.clear_changed()
                sub_grid_id = f"{sg.pos[0]},{sg.pos[1]}"
                grid_data = orjson.dumps(sg.to_dict()).decode("utf-8")
                cursor.execute(
                    """INSERT OR REPLACE INTO grids (game_id, user_id, sub_grid_id, grid_data) VALUES (?,?,?,?)""",
                    (self.user["game"]["id"], user_id, sub_grid_id, grid_data),
                )
            self.clear_changed()
        return self.num_grids_saved

    @property
    def time_played(self) -> str:
        """Calculate the time played in a human-readable format."""
        elapsed = self.play_duration
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{str(hours).rjust(2, '0')}:{str(minutes).rjust(2, '0')}:{str(seconds).rjust(2, '0')}"

    def clear_highlighted(self) -> None:
        """Clear the highlighted flag for all cells in all subgrids."""
        for cell in list(self.highlighted_cells):
            cell.highlighted = False
        self.highlighted_cells.clear()

    def clear_changed(self) -> None:
        """Clear the changed flag for all subgrids."""
        for sg in list(self.changed_subgrids):
            sg.clear_changed()
        self.changed_subgrids.clear()

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
        sg_coord: GridPos = (gx // 8, gy // 8)
        local_x: int = gx % 8
        local_y: int = gy % 8
        if sg_coord not in self.subgrids:
            if not create_if_needed:
                return None
            self.subgrids[sg_coord] = SubGrid(self, sg_coord, self.difficulty)
            self.subgrids[sg_coord].changed = True
        subgrid: SubGrid = self.subgrids[sg_coord]
        return subgrid.cells[local_y][local_x]

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
                n_sg: GridPos = (nx // 8, ny // 8)
                if n_sg in self.subgrids:
                    subgrid: SubGrid = self.subgrids[n_sg]
                    lx: int = nx % 8
                    ly: int = ny % 8
                    if subgrid.cells[ly][lx].uncovered or subgrid.cells[ly][lx].is_mine:
                        return True
        return False

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
                n_sg: GridPos = (nx // 8, ny // 8)
                if n_sg not in self.subgrids:
                    continue
                subgrid: SubGrid = self.subgrids[n_sg]
                lx: int = nx % 8
                ly: int = ny % 8
                if subgrid.cells[ly][lx].is_mine:
                    mine_count += 1
                if subgrid.cells[ly][lx].marked:
                    flag_count += 1
        return flag_count, mine_count

    def reveal_cell(self, gx: int, gy: int, depth: int = 0) -> None:
        """
        Reveal the cell at global coordinates (gx, gy). If it is a mine the game ends. Also, generate any adjacent subgrids as needed.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            depth (int): The depth of the recursion (to prevent infinite recursion)
        """
        if self.game_over:
            return
        sg_coord: GridPos = (gx // 8, gy // 8)
        assert self.parent
        # For non-initial subgrids, only allow a reveal if at least one neighbor is uncovered.
        if sg_coord != (0, 0) and not self.cell_has_uncovered_neighbor(gx, gy):
            self.parent.notify("No uncovered neighbors")
            return

        cell: Cell | None = self.global_to_cell(gx, gy, True)
        # Do nothing if cell is marked or uncovered.
        if not cell or cell.marked or cell.uncovered:
            return

        # Uncover the cell only if we are not in reveal surrounding mode
        cell.uncovered = True
        if cell.uncovered and cell.is_mine:
            self.game_over = True
            self.save()
            self.save_score()
            self.parent.notify("Game Over! You hit a mine.", severity="error")
            self.parent.refresh()
            return
        # Generate any adjacent subgrids.
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: GridPos = (nx // 8, ny // 8)
                if n_sg not in self.subgrids:
                    self.subgrids[n_sg] = SubGrid(self, n_sg, self.difficulty)
                    self.subgrids[n_sg].changed = True

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

    def reveal_surround(self, gx: int, gy: int) -> None:
        """
        Reveal surrounding cells if the cell at (gx, gy) is uncovered and the number of flagged cells matches the number of mines.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        """
        if self.game_over:
            return
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell or not cell.uncovered:
            return
        counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
        if not counts[0]:
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
        self.save()
        assert self.parent

        self.parent.refresh()

    def highlight_neighbors(self, gx: int, gy: int) -> None:
        """
        Highlight the cell neighbors around (gx, gy).
        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
        """
        if self.game_over:
            return
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell or not cell.uncovered:
            return
        counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
        # if no neighboring mines do not highlight
        if not counts[1]:
            return

        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                cell = self.global_to_cell(gx + dx, gy + dy)
                if cell and not cell.uncovered:
                    cell.highlighted = True
        assert self.parent
        self.parent.refresh()

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
        self.save()

        assert self.parent
        self.parent.refresh()

    def check_subgrid_solved(self, sg_coord: GridPos) -> None:
        """
        Mark a subgrid as solved if the all cells that dont contain a mine have been uncovered.

        Args:
            sg_coord (GridPos): The coordinates of the subgrid
        """
        subgrid: SubGrid = self.subgrids[sg_coord]
        if subgrid.solved:
            return
        for row in subgrid.cells:
            for cell in row:
                if not cell.is_mine and not cell.uncovered:
                    return
        subgrid.solved = True
        self.num_solved += 1
        for row in subgrid.cells:
            for cell in row:
                if cell.is_mine and not cell.marked:
                    cell.marked = True

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
                if self.xray and cell.marked:
                    return "[red]⚑ [/]"
                return "[red]💣[/]"
            count: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
            if cell.parent.solved:
                color = "#A0A0A0"
            else:
                color = "#FFFF00" if cell.highlighted else count_to_color.get(count[1], "#000000")
            if cell.parent.solved:
                if count[1] == 0:
                    return f"[{color}]. [/]"
            return f"[{color}]{count[1]} [/]" if count[1] > 0 else "  "
        else:
            color = "#FFFF00" if cell.highlighted else "#E0E0E0"
            return "[red]⚑ [/]" if cell.marked else f"[{color}]■ [/]"
