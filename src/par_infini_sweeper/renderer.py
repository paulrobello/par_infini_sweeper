"""Cell rendering helpers (ARC-004 decomposition).

Pure Rich-markup emission for the minesweeper board — moved out of
``data_structures.py`` so the model is no longer coupled to presentation.
``render_cell`` is a free function taking the ``GameState``; the legacy
``GameState.get_cell_representation`` method is preserved as a one-line
delegate so call sites are unchanged.

The body is byte-for-byte equivalent to the original
``GameState.get_cell_representation`` plus the module-level ``count_to_color``
table that lived next to it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # TYPE_CHECKING-only so renderer.py has no runtime dependency on the model
    # module — breaks the otherwise-circular ``game.state ↔ renderer`` edge.
    from par_infini_sweeper.game.state import GameState

# Color mapping based on the count of adjacent mines.
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


def render_cell(state: GameState, gx: int, gy: int) -> str:
    """Return a Rich-markup string representation of the cell at (gx, gy).

    Args:
        state (GameState): The game state the cell belongs to.
        gx (int): The global x-coordinate of the cell.
        gy (int): The global y-coordinate of the cell.

    Returns:
        str: The Rich markup string for the cell.
    """
    cell = state.global_to_cell(gx, gy)

    # set background based on checker pattern
    sg_coord: tuple[int, int] = (gx // 8, gy // 8)
    bg_color = "#000000" if (sg_coord[0] + sg_coord[1]) % 2 == 0 else "#111111"
    if state.mouse_sg_coord == sg_coord and state.highlighted_subgrid:
        bg_color = "#888800"

    if not cell:
        return f"[#C0C0C0 on {bg_color}]? [/]"  # placeholder for not-yet generated subgrid

    if state.xray or cell.uncovered:
        if cell.is_mine:
            if state.xray and cell.marked:
                return f"[#FF0000 on {bg_color}]⚑ [/]"
            return f"[#FF0000 on {bg_color}]💣[/]"
        count: tuple[int, int] = state.count_adjacent_flags_mines(gx, gy)
        if cell.parent.solved:
            color = "#A0A0A0"
        else:
            color = "#FFFF00" if cell.highlighted else count_to_color.get(count[1], "#FFFFFF")
        if cell.parent.solved:
            if count[1] == 0:
                return f"[{color} on {bg_color}]. [/]"
        if count[1] > 0:
            return f"[{color} on {bg_color}]{count[1]} [/]"
        return f"[#C0C0C0 on {bg_color}]  [/]"
    else:
        if cell.marked:
            return f"[#FF0000 on {bg_color}]⚑ [/]"
        color = "#FFFF00" if cell.highlighted else "#E0E0E0"
        return f"[{color} on {bg_color}]■ [/]"
