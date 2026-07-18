"""Backward-compatibility re-export shim (ARC-004 decomposition).

Historically this 800+ LOC module held the entire game model plus its
persistence, leaderboard, and rendering concerns. Those have been split out:

* Pure model (``Cell`` / ``SubGrid`` / ``GameState`` / ``GridPos`` /
  ``mine_counts`` / ``difficulty_mult``) → :mod:`par_infini_sweeper.game`
* SQLite persistence → :mod:`par_infini_sweeper.persistence`
* OAuth/leaderboard HTTP → :mod:`par_infini_sweeper.leaderboard`
* Rich markup emission + ``count_to_color`` → :mod:`par_infini_sweeper.renderer`

This file is now a thin re-export layer so every existing
``from par_infini_sweeper.data_structures import X`` continues to resolve.
New code should import directly from the destination modules above.
"""

from __future__ import annotations

from par_infini_sweeper.game.cells import Cell
from par_infini_sweeper.game.state import GameState
from par_infini_sweeper.game.subgrid import SubGrid
from par_infini_sweeper.game.types import GridPos, difficulty_mult, mine_counts
from par_infini_sweeper.renderer import count_to_color

__all__: list[str] = [
    "GridPos",
    "mine_counts",
    "difficulty_mult",
    "count_to_color",
    "Cell",
    "SubGrid",
    "GameState",
]
