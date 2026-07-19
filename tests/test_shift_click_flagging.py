"""Regression test for shift/ctrl+click cell flagging.

The mouse-handler pipeline (``on_mouse_down`` -> ``on_mouse_up`` ->
``handle_click`` -> ``toggle_mark``) was not exercised by the unit or
integration tests, which left shift/ctrl+click flagging uncovered. This drives
the full path through Textual's headless pilot with ``shift=True`` (and the
coordinate math that ``MainGrid.adjust_mouse_pos`` +
``GameState.mouse_to_global_grid_coords`` use) to prove a covered cell becomes
flagged.

Note on the "shift+click does nothing" report: the code path below is correct
and Textual's event pipeline delivers the modifier — the failure users see in a
real terminal is that the terminal itself intercepts Shift+click/drag for text
selection (the standard "override mouse capture" gesture) and never forwards
the event. Ctrl+click hits the same ``event.shift or event.ctrl`` branch and
works in every terminal.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_shift_click_flags_covered_cell() -> None:
    """Boot PimApp, reveal the origin so cells exist, then shift+click a
    precisely-targeted covered cell via the pilot and assert it is flagged."""
    from par_infini_sweeper.pim_app import PimApp

    app = PimApp(user_name="shiftclick_reg")
    try:
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.sweeper_widget
            state = app.game_state
            assert grid is not None and state is not None

            # Reveal origin so subgrid (0,0) and its cells exist.
            state.reveal_cell(0, 0)
            await pilot.pause()
            origin = state.subgrids.get((0, 0))
            assert origin is not None

            # Pick a still-covered, non-mine cell in subgrid (0,0). Local coords
            # within the (0,0) subgrid are the same as global coords here.
            target_coord = None
            for ly, row in enumerate(origin.cells):
                for lx, cell in enumerate(row):
                    if not cell.uncovered and not cell.is_mine:
                        target_coord = (lx, ly)
                        break
                if target_coord is not None:
                    break
            assert target_coord is not None, "need a covered non-mine cell to flag"
            cgx, cgy = target_coord

            # Invert mouse_to_global_grid_coords to find the widget click offset:
            #   gx = (x_adj // 2) + offset.x ; x_adj = ox - (pad_w + 1)
            #   gy = y_adj + offset.y        ; y_adj = oy - (pad_h + 1)
            pad_w = grid.styles.padding.width
            pad_h = grid.styles.padding.height
            ox = (cgx - state.offset.x) * 2 + pad_w + 1
            oy = (cgy - state.offset.y) + pad_h + 1

            target_cell = state.global_to_cell(cgx, cgy)
            assert target_cell is not None and not target_cell.marked

            await pilot.click(grid, offset=(ox, oy), shift=True)
            await pilot.pause()

            assert target_cell.marked is True, "shift+click through the real pipeline should flag the covered cell"
    finally:
        try:
            app.stop_webserver()
        except Exception:  # pragma: no cover — best-effort cleanup
            pass


@pytest.mark.asyncio
async def test_right_click_flags_covered_cell() -> None:
    """Right-click (non-left button) flags a covered cell — the terminal-
    independent flagging path. Shift/Ctrl modifiers are unreliable across
    terminals (Shift is reserved for text selection), but non-left buttons
    are delivered consistently, so right-click is the reliable way to flag."""
    from par_infini_sweeper.pim_app import PimApp

    app = PimApp(user_name="rclick_reg")
    try:
        async with app.run_test() as pilot:
            await pilot.pause()
            grid = app.sweeper_widget
            state = app.game_state
            assert grid is not None and state is not None

            state.reveal_cell(0, 0)
            await pilot.pause()
            origin = state.subgrids.get((0, 0))
            assert origin is not None

            target_coord = None
            for ly, row in enumerate(origin.cells):
                for lx, cell in enumerate(row):
                    if not cell.uncovered and not cell.is_mine:
                        target_coord = (lx, ly)
                        break
                if target_coord is not None:
                    break
            assert target_coord is not None
            cgx, cgy = target_coord

            pad_w = grid.styles.padding.width
            pad_h = grid.styles.padding.height
            ox = (cgx - state.offset.x) * 2 + pad_w + 1
            oy = (cgy - state.offset.y) + pad_h + 1

            target_cell = state.global_to_cell(cgx, cgy)
            assert target_cell is not None and not target_cell.marked

            # button=2 is right-click in Textual's pilot; any non-left button
            # takes the flag branch in handle_click.
            await pilot.click(grid, offset=(ox, oy), button=2)
            await pilot.pause()

            assert target_cell.marked is True, "right-click through the real pipeline should flag the covered cell"
    finally:
        try:
            app.stop_webserver()
        except Exception:  # pragma: no cover — best-effort cleanup
            pass
