"""Game-domain package (ARC-004 decomposition).

Holds the pure model — ``Cell`` / ``SubGrid`` / ``GameState`` / shared types —
separated from the cross-cutting adapters that ``GameState`` delegates to
(``par_infini_sweeper.persistence``, ``par_infini_sweeper.leaderboard``,
``par_infini_sweeper.renderer``).

Re-exports the public names for convenience so callers can write
``from par_infini_sweeper.game import GameState`` if they prefer; the legacy
``par_infini_sweeper.data_structures`` module remains a thin re-export shim.
"""

from __future__ import annotations

from par_infini_sweeper.game.cells import Cell
from par_infini_sweeper.game.state import GameState
from par_infini_sweeper.game.subgrid import SubGrid
from par_infini_sweeper.game.types import GridPos, difficulty_mult, mine_counts

__all__: list[str] = [
    "GridPos",
    "mine_counts",
    "difficulty_mult",
    "Cell",
    "SubGrid",
    "GameState",
]
