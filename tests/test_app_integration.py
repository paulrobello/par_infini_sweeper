"""Higher-level integration test for ``par_infini_sweeper``.

Phase 3b-ii safety net (ARC-004 decomposition): the unit tests in
``test_game.py`` / ``test_db.py`` exercise the pure model and the DB layer in
isolation, but nothing currently drives the full ``PimApp`` boot path —
construction → ``on_mount`` (storage init, schema init, ``GameState.load``,
``MainGrid`` mount) → interaction. This module does that so the
``data_structures.py`` decomposition has a real integration check beyond
"imports still resolve".

The first test uses Textual's ``App.run_test()`` pilot (the recommended
headless harness). The second is a synchronous construction + persistence
round-trip fallback that runs even if the Textual pilot path can't be used in
some environment. Both must stay green before AND after the god-module split.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from par_infini_sweeper.data_structures import GameState

# ---------------------------------------------------------------------------
# Primary: drive the real PimApp via Textual's headless pilot.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pim_app_boots_and_reveal_works_through_pilot() -> None:
    """Boot the full app, then reveal the origin cell through the integrated
    ``GameState`` (whose ``parent`` is the live ``MainGrid`` widget after mount).

    Asserts the boot path itself doesn't raise, ``on_mount`` actually populates
    ``game_state``, a real reveal opens at least one cell, and the save → load
    round-trip through SQLite preserves the persisted subgrid.
    """
    from par_infini_sweeper.pim_app import PimApp

    app = PimApp(user_name="pim_pilot")
    try:
        async with app.run_test() as pilot:
            # Let on_mount finish (storage init, schema init, GameState.load,
            # MainGrid mount). pilot.pause() drains the pending work queue.
            await pilot.pause()

            # Boot path completed without raising and populated game_state.
            assert app.game_state is not None
            assert app.sweeper_widget is not None
            # MainGrid.__init__ wires game_state.parent = self — the model↔UI
            # bridge the audit (ARC-005) flags. This assertion pins that bridge
            # so a future rewiring has to update this test deliberately.
            assert app.game_state.parent is app.sweeper_widget

            # Reveal the global origin cell. Reveal exercises global_to_cell,
            # the first-click mine relocation (ARC-015), count_adjacent_flags_mines,
            # the depth-bounded recursion (QA-002/QA-003), and check_subgrid_solved.
            app.game_state.reveal_cell(0, 0)
            await pilot.pause()

            origin = app.game_state.subgrids[(0, 0)]
            assert any(cell.uncovered for row in origin.cells for cell in row), (
                "reveal_cell(0,0) should uncover at least one cell in the origin subgrid"
            )

            # Persistence round-trip through the live SQLite DB.
            app.game_state.save()
            reloaded = GameState.load(None, "pim_pilot")
            assert (0, 0) in reloaded.subgrids
            reloaded_origin = reloaded.subgrids[(0, 0)]
            assert any(cell.uncovered for row in reloaded_origin.cells for cell in row), (
                "save/load round-trip must preserve the uncovered cell"
            )
    finally:
        try:
            app.stop_webserver()
        except Exception:  # pragma: no cover — best-effort cleanup
            pass


# ---------------------------------------------------------------------------
# Fallback: synchronous construction + persistence round-trip. Runs even in
# environments where Textual's pilot harness can't open a headless display.
# ---------------------------------------------------------------------------


def _make_user(**overrides: Any) -> dict[str, Any]:
    from par_infini_sweeper.enums import GameDifficulty

    base: dict[str, Any] = {
        "id": 1,
        "username": "pim_smoke",
        "nickname": "pim_smoke",
        "net_nickname": "",
        "id_token": "",
        "access_token": "",
        "refresh_token": "",
        "expires_at": 0,
        "prefs": {"theme": "textual-dark", "difficulty": GameDifficulty.EASY},
        "game": {"id": 1, "duration": 0, "game_over": False, "board_offset": "0,0"},
    }
    base.update(overrides)
    return base


def test_gamestate_save_load_round_trip_through_sqlite() -> None:
    """Build a ``GameState`` against the real ``db`` layer (no Textual),
    reveal a cell, persist, reload, and confirm the reveal survived the
    round-trip. This is the smoke-test fallback that exercises the same
    persistence path the app uses without depending on the pilot harness.
    """
    from par_infini_sweeper import db

    conn = db.get_db_connection()
    try:
        db.init_db(conn, "pim_smoke")
    finally:
        conn.close()

    user = db.get_user(db.get_db_connection(), "pim_smoke")
    parent = MagicMock(spec=["notify", "refresh", "app"])
    state = GameState(parent, user)

    # Make the origin subgrid mine-free at (0,0) so the reveal opens the cell
    # instead of ending the game on the very first click.
    origin_cell = state.global_to_cell(0, 0, True)
    assert origin_cell is not None
    origin_cell._is_mine = False

    state.reveal_cell(0, 0)
    assert origin_cell.uncovered is True

    saved = state.save()
    assert saved >= 1, "save() should persist at least the changed origin subgrid"

    reloaded = GameState.load(parent, "pim_smoke")
    assert (0, 0) in reloaded.subgrids
    reloaded_origin = reloaded.subgrids[(0, 0)].cells
    assert any(cell.uncovered for row in reloaded_origin for cell in row), (
        "persisted subgrid should still show the reveal after load()"
    )
