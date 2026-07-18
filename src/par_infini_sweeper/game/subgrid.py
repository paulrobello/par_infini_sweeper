"""``SubGrid`` — an 8×8 tile of ``Cell``s (ARC-004 extraction).

Pure model class moved out of ``data_structures.py``. Imports ``Cell`` for
real (cells are its building block) and the difficulty table from
``game.types``; the ``GameState`` import is TYPE_CHECKING-only to keep the
``subgrid ↔ state`` edge non-cyclic at runtime.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from par_infini_sweeper.enums import GameDifficulty
from par_infini_sweeper.game.cells import Cell
from par_infini_sweeper.game.types import GridPos, mine_counts

if TYPE_CHECKING:
    from par_infini_sweeper.game.state import GameState


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
