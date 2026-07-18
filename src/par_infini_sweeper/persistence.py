"""SQLite persistence helpers for ``GameState`` (ARC-004 decomposition).

All DB I/O previously inlined on ``GameState`` (``save`` / ``load`` SQL /
``save_score`` / ``save_user``) lives here. ``GameState``'s methods become
one-line delegates, so call sites are unchanged.

``fetch_saved_subgrids`` returns the raw ``(coords, grid_data)`` rows for a
game; ``GameState.load`` consumes them and runs the SubGrid deserialization
itself. Splitting the SQL from the reconstruction keeps the
``persistence ↔ model`` edge non-circular (persistence never imports
``GameState`` at runtime; it only writes one and reads raw rows).

Bodies are byte-for-byte equivalent to the originals.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import orjson

from par_infini_sweeper import db
from par_infini_sweeper.db import get_db_connection

if TYPE_CHECKING:
    from sqlite3 import Connection

    from par_infini_sweeper.game.state import GameState
    from par_infini_sweeper.game.types import GridPos


def save_user(state: GameState) -> None:
    """Persist the user dict on ``state`` to the users table."""
    db.save_user(state.user)


def save_score(state: GameState) -> None:
    """Insert a highscore row for ``state``'s current score (no-op when score is 0)."""
    score = state.score()
    if score == 0:
        return
    conn = db.get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO highscores (game_id, user_id, score) VALUES (?, ?,?)""",
            (state.user["game"]["id"], state.user["id"], score),
        )


def save_game_state(state: GameState) -> int:
    """Persist prefs / game row / changed subgrids; return the number of subgrids saved."""
    with get_db_connection() as conn:
        state.user["prefs"] = {"theme": state.theme, "difficulty": state.difficulty}
        user_id = state.user["id"]
        state.user["game"]["duration"] = state.duration
        state.user["game"]["game_over"] = state.game_over
        state.user["game"]["board_offset"] = f"{state.offset.x},{state.offset.y}"

        cursor = conn.cursor()
        cursor.execute(
            """UPDATE user_prefs SET theme = ?, difficulty = ? WHERE id = ?""",
            (state.theme, state.difficulty.value, user_id),
        )
        cursor.execute(
            """UPDATE games SET game_over = ?, board_offset = ?, duration = ? WHERE user_id = ?""",
            (
                state.user["game"]["game_over"],
                state.user["game"]["board_offset"],
                state.user["game"]["duration"],
                user_id,
            ),
        )

        # Save each subgrid using upsert.
        state.num_grids_saved = 0
        for sg in state.changed_subgrids:
            state.num_grids_saved += 1
            sg.clear_changed()
            sub_grid_id = f"{sg.pos[0]},{sg.pos[1]}"
            grid_data = orjson.dumps(sg.to_dict()).decode("utf-8")
            cursor.execute(
                """INSERT OR REPLACE INTO grids (game_id, user_id, sub_grid_id, grid_data) VALUES (?,?,?,?)""",
                (state.user["game"]["id"], user_id, sub_grid_id, grid_data),
            )
        state.clear_changed()
    return state.num_grids_saved


def fetch_saved_subgrids(
    conn: Connection, game_id: int, user_id: int
) -> Iterator[tuple[tuple[int, int], dict[str, Any]]]:
    """Yield ``(coords, sg_data)`` for every persisted subgrid of the given game.

    The caller (``GameState.load``) owns ``SubGrid.from_dict`` and the
    ``first_click`` / ``num_solved`` reconstruction — those aren't persistence
    concerns. Returns already-parsed coords + orjson-decoded grid_data so the
    SQL/orjson details stay inside this module.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM grids WHERE game_id = ? AND user_id = ?",
        (game_id, user_id),
    )
    row = cursor.fetchone()
    while row:
        key_parts: list[str] = row["sub_grid_id"].split(",")
        coords: GridPos = (int(key_parts[0]), int(key_parts[1]))
        sg_data = orjson.loads(row["grid_data"])
        yield coords, sg_data
        row = cursor.fetchone()
