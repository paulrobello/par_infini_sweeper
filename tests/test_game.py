"""Regression + behaviour tests for the pure game model.

Covers:
  * ARC-003 — ``GameState.is_logged_in`` had inverted expiry semantics.
  * QA-002  — first-click "safety" used to scrub mines from the entire
              opening flood-fill because ``first_click`` was cleared only
              after ``reveal_cell`` returned.
  * Audit coverage: ``SubGrid.generate_cells`` mine counts / distribution,
    ``check_subgrid_solved``, and ``to_dict`` / ``from_dict`` round-trips
    for Cell / SubGrid / GameState.

These tests construct model objects directly with a stub parent widget so
the pure game logic is exercised without spinning up Textual, SQLite, or
the OAuth client.
"""

from __future__ import annotations

import random
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from jose import jwt

from par_infini_sweeper.data_structures import Cell, GameState, SubGrid
from par_infini_sweeper.enums import GameDifficulty


def make_user(**overrides: Any) -> dict[str, Any]:
    """Build a minimal user dict satisfying GameState.__init__'s contract."""
    base: dict[str, Any] = {
        "id": 1,
        "username": "test",
        "nickname": "test",
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


def make_state(parent: Any = None, **user_overrides: Any) -> GameState:
    """Build a GameState with a Mock parent (sufficient for reveal_cell /
    check_subgrid_solved, which only need ``parent.notify`` / ``parent.refresh``)."""
    parent = parent or MagicMock(spec=["notify", "refresh", "app"])
    return GameState(parent, make_user(**user_overrides))


def make_token(exp_offset_seconds: int) -> str:
    """HS256 JWT with the given ``exp`` offset from now. ``get_unverified_claims``
    doesn't verify the signature, so any symmetric secret works."""
    return jwt.encode({"exp": int(time.time()) + exp_offset_seconds}, "test-secret", algorithm="HS256")


# =============================================================================
# ARC-003 — is_logged_in expiry semantics
# =============================================================================


def test_is_logged_in_returns_false_with_no_access_token() -> None:
    state = make_state()
    assert state.is_logged_in() is False


def test_is_logged_in_true_for_fresh_token_without_refresh() -> None:
    """A token valid for an hour with no refresh token must read as logged-in."""
    state = make_state()
    state.user["access_token"] = make_token(exp_offset_seconds=3600)
    state.user["refresh_token"] = ""
    assert state.is_logged_in() is True


def test_is_logged_in_true_for_fresh_token_default_grace() -> None:
    """Default grace_time is 60s — a token with 10 minutes left is healthy."""
    state = make_state()
    state.user["access_token"] = make_token(exp_offset_seconds=600)
    assert state.is_logged_in() is True


def test_is_logged_in_false_for_expired_token_no_refresh() -> None:
    """ARC-003 regression: expired access token + no refresh_token => False.

    The pre-fix code returned True here (the inverted ``time_remaining >
    grace_time`` check fired only while healthy), so stale tokens went
    undetected.
    """
    state = make_state()
    state.user["access_token"] = make_token(exp_offset_seconds=-3600)
    state.user["refresh_token"] = ""
    assert state.is_logged_in() is False


def test_is_logged_in_true_for_expired_token_with_refresh() -> None:
    """An expired access token can still be renewed via offline_access, so the
    user is considered logged in."""
    state = make_state()
    state.user["access_token"] = make_token(exp_offset_seconds=-3600)
    state.user["refresh_token"] = "some-refresh-token"
    assert state.is_logged_in() is True


def test_is_logged_in_false_when_within_grace_window_without_refresh() -> None:
    """Inside the 60s grace window with no refresh token, we are effectively
    expired."""
    state = make_state()
    state.user["access_token"] = make_token(exp_offset_seconds=30)  # < grace_time=60
    state.user["refresh_token"] = ""
    assert state.is_logged_in() is False


def test_is_logged_in_false_when_within_grace_window_with_refresh() -> None:
    """Inside the grace window WITH a refresh token, the renewal path keeps us
    logged in."""
    state = make_state()
    state.user["access_token"] = make_token(exp_offset_seconds=30)
    state.user["refresh_token"] = "rt"
    assert state.is_logged_in() is True


# =============================================================================
# QA-002 — first-click mine relocation
# =============================================================================


def test_first_click_starts_true() -> None:
    """Sanity: a fresh GameState has first_click=True (relies on no prior reveal)."""
    state = make_state()
    assert state.first_click is True


def test_first_click_cleared_before_recursion_on_non_mine() -> None:
    """QA-002 regression: clicking a non-mine cell must clear first_click BEFORE
    flood-fill recursion starts (was cleared only after reveal_cell returned)."""
    state = make_state()
    # Make the (0,0) subgrid mine-free so the recursion expands.
    for row in state.subgrids[(0, 0)].cells:
        for cell in row:
            cell._is_mine = False
    state.reveal_cell(0, 0)
    assert state.first_click is False


def test_first_click_relocates_mine_for_clicked_cell() -> None:
    """The originally-clicked mine is still relocated (first-click safety
    preserved for the cell the user actually clicked)."""
    state = make_state()
    clicked = state.global_to_cell(0, 0, True)
    assert clicked is not None
    clicked._is_mine = True
    state.first_click = True

    state.reveal_cell(0, 0)

    assert state.game_over is False
    assert clicked.is_mine is False
    # first_click must be cleared by the entry call regardless of the mine path.
    assert state.first_click is False
    # Mine was moved to one of the surrounding cells.
    neighbours = [state.global_to_cell(dx, dy) for dx in range(-1, 2) for dy in range(-1, 2)]
    assert any(c is not None and c.is_mine for c in neighbours if c is not clicked)


def test_recursive_reveal_of_mine_ends_game() -> None:
    """QA-002 regression: a mine encountered DURING flood-fill recursion ends
    the game rather than being silently relocated.

    The bug was that ``first_click`` stayed True for the entire flood fill, so
    any mine hit mid-recursion took the relocation branch. With the fix the
    entry call (``depth == 0``) clears ``first_click`` before recursion starts,
    so a depth>0 mine hit must trigger game-over.

    We drive this directly by calling reveal_cell with ``depth=5`` on a mine
    after first_click has been cleared — the exact state the recursion would
    be in under the fix.
    """
    state = make_state()
    state.first_click = False  # simulates post-entry-call state
    target = state.global_to_cell(0, 0, True)
    assert target is not None
    target._is_mine = True
    target._uncovered = False
    state.save = MagicMock(name="save")
    state.save_score = MagicMock(name="save_score")

    state.reveal_cell(0, 0, depth=5)

    assert state.game_over is True
    assert target.is_mine is True  # not relocated
    state.save.assert_called_once()
    state.save_score.assert_called_once()


def test_second_click_on_mine_ends_game() -> None:
    """A real second click on a mine ends the game once first_click has been
    cleared by the first reveal."""
    state = make_state()
    # First click on (0,0) — first_click ends up False regardless of layout.
    state.reveal_cell(0, 0)
    assert state.first_click is False

    # Force a fresh covered mine in the (0,0) subgrid for the second click.
    # The first click's flood may have revealed cells in (0,0); pick one and
    # explicitly mark it covered + mine so the second reveal is exercised
    # against a mine hit, not skipped by the early-return guard.
    target = state.global_to_cell(0, 0, True)
    assert target is not None
    target._is_mine = True
    target._uncovered = False
    state.save = MagicMock(name="save")
    state.save_score = MagicMock(name="save_score")

    state.reveal_cell(0, 0)

    assert state.game_over is True
    assert target.is_mine is True


# =============================================================================
# SubGrid.generate_cells — mine counts & distribution
# =============================================================================


@pytest.mark.parametrize(
    ("difficulty", "expected_mines"),
    [
        (GameDifficulty.EASY, 8),
        (GameDifficulty.MEDIUM, 12),
        (GameDifficulty.HARD, 16),
    ],
)
def test_generate_cells_mine_count_matches_difficulty(difficulty: GameDifficulty, expected_mines: int) -> None:
    state = make_state()
    random.seed(0)
    sg = SubGrid(state, (0, 0), difficulty)
    actual_mines = sum(1 for row in sg.cells for cell in row if cell.is_mine)
    assert actual_mines == expected_mines


def test_generate_cells_grid_shape_is_8x8() -> None:
    state = make_state()
    sg = SubGrid(state, (0, 0), GameDifficulty.EASY)
    assert len(sg.cells) == 8
    assert all(len(row) == 8 for row in sg.cells)


def test_generate_cells_distribution_is_non_degenerate() -> None:
    """With a fixed seed, easy (8 mines) must not place all mines in a single
    row or column — that would indicate a broken distribution."""
    state = make_state()
    random.seed(1234)
    sg = SubGrid(state, (0, 0), GameDifficulty.EASY)

    mines_per_row = [sum(1 for cell in row if cell.is_mine) for row in sg.cells]
    mines_per_col = [sum(1 for row in sg.cells if row[col].is_mine) for col in range(8)]

    assert sum(1 for c in mines_per_row if c > 0) >= 2
    assert sum(1 for c in mines_per_col if c > 0) >= 2


def test_generate_cells_two_subgrids_differ_with_different_seed() -> None:
    """Randomness is actually random — two consecutive subgrids shouldn't share
    identical mine layouts under different seeds."""
    state = make_state()
    random.seed(1)
    sg1 = SubGrid(state, (0, 0), GameDifficulty.EASY)
    random.seed(2)
    sg2 = SubGrid(state, (1, 0), GameDifficulty.EASY)

    layout1 = {(x, y) for y in range(8) for x in range(8) if sg1.cells[y][x].is_mine}
    layout2 = {(x, y) for y in range(8) for x in range(8) if sg2.cells[y][x].is_mine}
    assert layout1 != layout2


# =============================================================================
# check_subgrid_solved
# =============================================================================


def test_check_subgrid_solved_marks_when_all_non_mines_uncovered() -> None:
    state = make_state()
    sg = state.subgrids[(0, 0)]
    for row in sg.cells:
        for cell in row:
            if not cell.is_mine:
                cell.uncovered = True

    state.check_subgrid_solved((0, 0))

    assert sg.solved is True
    # Once solved, every remaining mine cell should be auto-flagged.
    for row in sg.cells:
        for cell in row:
            if cell.is_mine:
                assert cell.marked is True


def test_check_subgrid_solved_no_op_when_mines_unrevealed() -> None:
    state = make_state()
    sg = state.subgrids[(0, 0)]
    # Uncover only one cell — many non-mine cells remain covered.
    sg.cells[0][0].uncovered = True

    state.check_subgrid_solved((0, 0))

    assert sg.solved is False
    assert state.num_solved == 0


def test_check_subgrid_solved_idempotent() -> None:
    state = make_state()
    sg = state.subgrids[(0, 0)]
    for row in sg.cells:
        for cell in row:
            if not cell.is_mine:
                cell.uncovered = True

    state.check_subgrid_solved((0, 0))
    state.check_subgrid_solved((0, 0))  # second call must not double-count

    assert sg.solved is True
    assert state.num_solved == 1


# =============================================================================
# to_dict / from_dict round-trips
# =============================================================================


def test_cell_round_trip() -> None:
    state = make_state()
    sg = state.subgrids[(0, 0)]
    original = Cell(sg, is_mine=True, marked=True, uncovered=False)
    data = original.to_dict()

    assert data == {"is_mine": True, "marked": True, "uncovered": False}

    restored = Cell.from_dict(sg, data)
    assert restored.is_mine is True
    assert restored.marked is True
    assert restored.uncovered is False


def test_subgrid_round_trip() -> None:
    state = make_state()
    random.seed(7)
    sg = SubGrid(state, (3, 4), GameDifficulty.MEDIUM)
    # Mutate some state so round-trip is non-trivial.
    sg.cells[0][0].uncovered = True
    sg.cells[1][2].marked = True
    sg.solved = False

    data = sg.to_dict()
    restored = SubGrid.from_dict(state, data)

    assert restored.pos == (3, 4)
    assert len(restored.cells) == 8
    assert all(len(row) == 8 for row in restored.cells)
    for y in range(8):
        for x in range(8):
            orig = sg.cells[y][x]
            got = restored.cells[y][x]
            assert got.is_mine == orig.is_mine
            assert got.marked == orig.marked
            assert got.uncovered == orig.uncovered
    assert restored.solved is False


def test_subgrid_round_trip_marks_solved_after_full_uncover() -> None:
    """from_dict re-derives `solved` if every non-mine cell is uncovered — even
    when the serialised `solved` was False."""
    state = make_state()
    random.seed(11)
    sg = SubGrid(state, (0, 0), GameDifficulty.EASY)
    for row in sg.cells:
        for cell in row:
            if not cell.is_mine:
                cell.uncovered = True
    sg.solved = False  # serialise as unsolved even though non-mines are all open

    restored = SubGrid.from_dict(state, sg.to_dict())

    assert restored.solved is True
    for row in restored.cells:
        for cell in row:
            if cell.is_mine:
                assert cell.marked is True


def test_game_state_round_trip_keys() -> None:
    """GameState.to_dict emits the keys load() needs to round-trip."""
    state = make_state()
    data = state.to_dict()

    expected_keys = {
        "user_id",
        "theme",
        "difficulty",
        "game_over",
        "started_ts",
        "duration",
        "offset",
        "subgrids",
        "first_click",
    }
    assert set(data.keys()) == expected_keys
    assert data["difficulty"] == GameDifficulty.EASY
    assert data["offset"] == (0, 0)
    assert data["first_click"] is True
    assert isinstance(data["subgrids"], dict)
    assert "0,0" in data["subgrids"]
