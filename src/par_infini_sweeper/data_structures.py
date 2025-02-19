from __future__ import annotations

import random
import time
from typing import Any

import orjson
from textual.geometry import Offset

from par_infini_sweeper import db
from par_infini_sweeper.db import get_user
from par_infini_sweeper.enums import GameDifficulty

mine_counts: dict[GameDifficulty, int] = {GameDifficulty.EASY: 8, GameDifficulty.MEDIUM: 12, GameDifficulty.HARD: 16}
difficulty_mult: dict[GameDifficulty, int] = {GameDifficulty.EASY: 1, GameDifficulty.MEDIUM: 2, GameDifficulty.HARD: 3}


class Cell:
    """Represents a single cell in a subgrid."""

    def __init__(self, parent: SubGrid, is_mine: bool, marked: bool = False, uncovered: bool = False) -> None:
        self._parent = parent
        self._is_mine: bool = is_mine
        self._marked: bool = marked
        self._uncovered: bool = uncovered
        self._changed: bool = False

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
        self, pos: tuple[int, int], difficulty: GameDifficulty | None = None, safe_pos: tuple[int, int] | None = None
    ) -> None:
        """
        Initialize a subgrid at position `pos` with the given difficulty.
        Optionally ensure that the cell at local coordinate safe_pos is mine‑free.
        """
        self.changed: bool = False
        self.pos: tuple[int, int] = pos
        self.cells: list[list[Cell]] = self.generate_cells(difficulty, safe_pos) if difficulty else []
        self.solved: bool = False

    def generate_cells(self, difficulty: GameDifficulty, safe_pos: tuple[int, int] | None) -> list[list[Cell]]:
        """
        Generate an 8×8 grid of cells with mines distributed according to difficulty.
        The number of mines per subgrid is adjusted as follows:
          - easy: 8 mines
          - medium: 12 mines
          - hard: 16 mines
        If safe_pos is provided, that cell is guaranteed not to be a mine.
        """

        num_mines: int = mine_counts.get(difficulty, 8)
        positions: list[tuple[int, int]] = [(x, y) for y in range(8) for x in range(8)]
        if safe_pos in positions:
            positions.remove(safe_pos)
        mine_positions: list[tuple[int, int]] = random.sample(positions, num_mines)
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
    def from_dict(data: dict[str, Any]) -> SubGrid:
        """Create a SubGrid instance from its dictionary representation."""
        sg: SubGrid = SubGrid(tuple(data["pos"]))
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

    def __init__(self, user: dict[str, Any]) -> None:
        self.user: dict[str, Any] = user
        self.difficulty: GameDifficulty = user["prefs"]["difficulty"]
        self.theme: str = user["prefs"]["theme"]
        self.subgrids: dict[tuple[int, int], SubGrid] = {}
        self.subgrids[(0, 0)] = SubGrid((0, 0), self.difficulty)
        game = user["game"]
        offset: list[str] = game["board_offset"].split(",")
        assert len(offset) == 2
        self.offset = Offset(int(offset[0]), int(offset[1]))
        self.num_solved: int = 0
        self.started_ts: int = int(time.time())
        self.play_duration: int = game["play_duration"]
        self.game_over: bool = game["game_over"]
        self.num_grids_saved: int = 0

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

        sg = SubGrid((0, 0), self.difficulty)
        sg.changed = True
        self.subgrids: dict[tuple[int, int], SubGrid] = {(0, 0): sg}
        self.offset = Offset(0, 0)
        self.num_solved: int = 0
        self.started_ts: int = int(time.time())
        self.play_duration: int = 0
        self.num_grids_saved: int = 0
        self.game_over = False

        conn = db.get_db_connection()
        with conn:
            cursor = conn.cursor()
            # Update user preferences.
            cursor.execute(
                """DELETE FROM grids WHERE user_id = ?""",
                (self.user["id"],),
            )
        self.save()

    def compute_board_center(self) -> tuple[int, int]:
        """Compute the center of the game board."""
        c = (0, 0)
        for k in self.subgrids.keys():
            c = (c[0] + k[0], c[1] + k[1])

        c = (c[0] // len(self.subgrids) * 8, c[1] // len(self.subgrids) * 8)
        return c

    @property
    def num_changed(self) -> int:
        return sum(1 for sg in self.subgrids.values() if sg.changed)

    @property
    def num_subgrids(self) -> int:
        return len(self.subgrids)

    @staticmethod
    def load() -> GameState:
        """Load the game state from the SQLite database or create a new one."""
        with db.get_db_connection() as conn:
            user = get_user(conn, "user")
            user_id = user["id"]
            game = user["game"]
            state = GameState(user)

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
                coords: tuple[int, int] = (int(key_parts[0]), int(key_parts[1]))
                sg_data = orjson.loads(row["grid_data"])
                sg: SubGrid = SubGrid.from_dict(sg_data)
                state.subgrids[coords] = sg
                if sg.solved:
                    state.num_solved += 1
                row = cursor.fetchone()

        return state

    def score(self) -> int:
        """Calculate the score based on the number of solved subgrids and difficulty."""
        return self.num_solved * difficulty_mult.get(self.difficulty, 1)

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

    def save(self) -> None:
        """Save the game state to the SQLite database."""
        conn = db.get_db_connection()
        self.user["prefs"] = {"theme": self.theme, "difficulty": self.difficulty}
        user_id = self.user["id"]
        self.user["game"]["play_duration"] = self.play_duration
        self.user["game"]["game_over"] = self.game_over
        self.user["game"]["board_offset"] = f"{self.offset.x},{self.offset.y}"

        with conn:
            cursor = conn.cursor()
            # Update user preferences.
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
            for sg_coord, subgrid in self.subgrids.items():
                if not subgrid.changed:
                    continue
                self.num_grids_saved += 1
                subgrid.clear_changed()
                sub_grid_id = f"{sg_coord[0]},{sg_coord[1]}"
                grid_data = orjson.dumps(subgrid.to_dict()).decode("utf-8")
                cursor.execute(
                    """INSERT OR REPLACE INTO grids (game_id, user_id, sub_grid_id, grid_data) VALUES (?,?,?,?)""",
                    (self.user["game"]["id"], user_id, sub_grid_id, grid_data),
                )

    @property
    def time_played(self) -> str:
        """Calculate the time played in a human-readable format."""
        elapsed = self.play_duration
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{str(hours).rjust(2, '0')}:{str(minutes).rjust(2, '0')}:{str(seconds).rjust(2, '0')}"
