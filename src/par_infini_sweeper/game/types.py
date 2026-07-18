"""Shared types and difficulty constants for the game domain (ARC-004).

Lives in its own module so ``Cell`` / ``SubGrid`` / ``GameState`` can import
the constants without pulling each other in.
"""

from __future__ import annotations

from par_infini_sweeper.enums import GameDifficulty

#: Canonical (subgrid_x, subgrid_y) / (cell_x, cell_y) coordinate pair.
GridPos = tuple[int, int]

#: Mines per 8×8 subgrid at each difficulty. Used by ``SubGrid.generate_cells``
#: and ``GameState.score``.
mine_counts: dict[GameDifficulty, int] = {
    GameDifficulty.EASY: 8,
    GameDifficulty.MEDIUM: 12,
    GameDifficulty.HARD: 16,
}

#: Score multiplier per difficulty. Kept here next to ``mine_counts`` for
#: discoverability; not currently read by any code path, but preserved as a
#: public name for backward compatibility.
difficulty_mult: dict[GameDifficulty, int] = {
    GameDifficulty.EASY: 1,
    GameDifficulty.MEDIUM: 2,
    GameDifficulty.HARD: 3,
}
