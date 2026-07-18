"""``GameState`` — central game-domain orchestrator (ARC-004 extraction).

Moved out of ``data_structures.py``. Owns the model state (subgrids, score,
mines, mouse info, auth tokens) and the high-level game logic (reveal /
flag / highlight / solve detection). Cross-cutting concerns are delegated:

* SQLite writes/reads → ``par_infini_sweeper.persistence``
* OAuth/leaderboard HTTP → ``par_infini_sweeper.leaderboard``
* Rich markup emission → ``par_infini_sweeper.renderer``

ARC-005 deferred: the ``parent`` widget bridge (``self.parent.notify`` /
``self.parent.refresh``) is preserved unchanged. Replacing it with Textual
``Message``s needs a UI integration-test harness that doesn't exist yet.
"""

from __future__ import annotations

import time
from typing import Any

from authlib.integrations.requests_client import OAuth2Session
from jose import jwt
from textual.geometry import Offset
from textual.widget import Widget

from par_infini_sweeper import db, persistence
from par_infini_sweeper.auth import build_auth_client
from par_infini_sweeper.db import get_db_connection, get_user
from par_infini_sweeper.enums import GameDifficulty, GameMode
from par_infini_sweeper.game.cells import Cell
from par_infini_sweeper.game.subgrid import SubGrid
from par_infini_sweeper.game.types import GridPos, mine_counts
from par_infini_sweeper.leaderboard import change_internet_nickname, post_internet_score
from par_infini_sweeper.models import ChangeNicknameResponse, PostScoreResult
from par_infini_sweeper.renderer import render_cell
from par_infini_sweeper.utils import format_duration


class GameState:
    """Represents the overall game state including difficulty and all subgrids."""

    def __init__(self, parent: Widget | None, user: dict[str, Any]) -> None:
        self.parent = parent
        self.mode: GameMode = GameMode.INFINITE
        self.user: dict[str, Any] = user
        self.difficulty: GameDifficulty = user["prefs"]["difficulty"]
        self.theme: str = user["prefs"]["theme"]
        self.subgrids: dict[GridPos, SubGrid] = {}
        self.subgrids[(0, 0)] = SubGrid(self, (0, 0), self.difficulty)
        game: dict[str, Any] = user["game"]
        offset: list[str] = game["board_offset"].split(",")
        assert len(offset) == 2
        self.offset = Offset(int(offset[0]), int(offset[1]))
        self.num_solved: int = 0
        self.started_ts: int = int(time.time())
        self.duration: int = game["duration"]
        self.game_over: bool = game["game_over"]
        self.num_grids_saved: int = 0
        self.highlighted_cells: set[Cell] = set()
        self.changed_subgrids: set[SubGrid] = set()
        self.mouse_grid: SubGrid | None = None
        self.paused: bool = False
        self.xray: bool = False
        self._auth_client: OAuth2Session | None = None
        self.first_click: bool = True
        self.mouse_pos: GridPos = 0, 0
        self.mouse_global_grid_coord: GridPos = 0, 0
        self.mouse_sg_coord: GridPos = (self.mouse_global_grid_coord[0] // 8, self.mouse_global_grid_coord[1] // 8)
        self.shift_pressed: bool = False
        self.ctrl_pressed: bool = False
        self.highlighted_subgrid: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the game state."""
        return {
            "user_id": self.user["id"],
            "theme": self.theme,
            "difficulty": self.difficulty,
            "game_over": self.game_over,
            "started_ts": self.started_ts,
            "duration": self.duration,
            "offset": (self.offset.x, self.offset.y),
            "subgrids": {f"{k[0]},{k[1]}": sg.to_dict() for k, sg in self.subgrids.items()},
            "first_click": self.first_click,
        }

    def mouse_to_global_grid_coords(self, x: int, y: int) -> GridPos:
        """
        Convert widget-local coordinates to global cell coordinates.

        Args:
            x (int): The widget-local x coordinate (already padding-adjusted by the caller).
            y (int): The widget-local y coordinate (already padding-adjusted by the caller).

        Returns:
            GridPos: The global cell coordinates (gx, gy)
        """
        # ARC-005: takes explicit (x, y) rather than a MouseEvent so MainGrid
        # no longer has to mutate ``event._x`` / ``event._y`` to apply padding.
        gx: int = (x // 2) + self.offset.x
        gy: int = y + self.offset.y
        return gx, gy

    def update_mouse_info(self, x: int, y: int, shift: bool, ctrl: bool) -> None:
        """Cache the latest mouse position + modifier state on the game state.

        Args:
            x (int): The widget-local x coordinate (already padding-adjusted by the caller).
            y (int): The widget-local y coordinate (already padding-adjusted by the caller).
            shift (bool): Whether Shift was held.
            ctrl (bool): Whether Ctrl was held.
        """
        # ARC-005: takes explicit (x, y, shift, ctrl) rather than a MouseEvent,
        # so the model never reaches into Textual event internals.
        self.mouse_pos = x, y
        self.mouse_global_grid_coord = self.mouse_to_global_grid_coords(x, y)
        self.mouse_sg_coord = (self.mouse_global_grid_coord[0] // 8, self.mouse_global_grid_coord[1] // 8)

        if self.parent and self.highlighted_subgrid:
            self.parent.refresh()

        self.shift_pressed = shift
        self.ctrl_pressed = ctrl

    @property
    def auth_client(self) -> OAuth2Session:
        if not self._auth_client or not self.is_logged_in():
            assert self.parent and self.parent.app
            self._auth_client = build_auth_client(self.user, self.parent.app)
        return self._auth_client

    def is_logged_in(self, grace_time: int = 60) -> bool:
        """
        Check if the user is logged in by checking the access token.
        Args:
            grace_time (int): Grace period in seconds for token expiration.
        Returns:
            bool: True if the user is logged in and the access token is valid, False otherwise.
        """
        if not self.user["access_token"]:
            return False
        try:
            unverified_claims = jwt.get_unverified_claims(self.user["access_token"])
            time_remaining = unverified_claims.get("exp", 0) - int(time.time())
            # ARC-003: token is expired once grace_time is exhausted (was inverted —
            # previously True while healthy). A refresh_token (offline_access) still
            # lets us transparently renew, so treat that as logged-in.
            is_expired = time_remaining <= grace_time
            return (not is_expired) or bool(self.user.get("refresh_token"))
        except Exception as _:
            self.logout()
            return False

    def logout(self) -> None:
        """
        Clear the user's tokens from the database.
        """
        self.user["id_token"] = ""
        self.user["access_token"] = ""
        self.user["refresh_token"] = ""
        self.user["expires_at"] = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE users SET id_token = '', access_token = '', refresh_token = '', expires_at = 0 WHERE id = ?""",
                (self.user["id"],),
            )
        self._auth_client = None

    def save_user(self) -> None:
        """Save user data to the database."""
        # ARC-004: DB write moved to persistence.save_user.
        persistence.save_user(self)

    def change_internet_nickname(self, nickname: str) -> ChangeNicknameResponse:
        """
        Change nickname on the internet leaderboard.
        Args:
            nickname (str): New nickname to set.

        Returns:
            PostScoreResult: Result of the post operation.
        """
        # ARC-004: HTTP/nickname logic moved to leaderboard.change_internet_nickname.
        return change_internet_nickname(self, nickname)

    def new_game(self) -> None:
        """Start a new game by resetting the game state."""

        sg = SubGrid(self, (0, 0), self.difficulty)
        sg.changed = True
        self.subgrids = {(0, 0): sg}
        self.offset = Offset(0, 0)
        self.num_solved = 0
        self.started_ts = int(time.time())
        self.duration = 0
        self.num_grids_saved = 0
        self.game_over = False
        self.clear_highlighted()
        self.clear_changed()
        self.xray = False
        self.first_click = True

        conn = db.get_db_connection()
        with conn:
            cursor = conn.cursor()
            # Update user preferences.
            cursor.execute(
                """DELETE FROM grids WHERE user_id = ?""",
                (self.user["id"],),
            )
        self.save()

    def compute_board_center(self) -> Offset:
        """Compute the center of the game board in cells based on subgrid positions."""
        c = (0, 0)
        for k in self.subgrids.keys():
            c = (c[0] + k[0] * 8, c[1] + k[1] * 8)

        return Offset(c[0] // len(self.subgrids) + 5, c[1] // len(self.subgrids) - 3)

    @property
    def num_changed(self) -> int:
        return sum(1 for sg in self.subgrids.values() if sg.changed)

    @property
    def num_subgrids(self) -> int:
        return len(self.subgrids)

    @staticmethod
    def load(parent: Widget | None, user_name: str, nickname: str | None = None) -> GameState:
        """
        Load the game state from the SQLite database or create a new one.

        Args:
            parent (Widget): The parent widget.
            user_name (str): The name of the user.
            nickname (str | None): The nickname of the user.
        """
        # ARC-004: SQL row scan moved to persistence.fetch_saved_subgrids; the
        # SubGrid deserialization + first_click/num_solved reconstruction
        # stays here (model logic, not persistence).
        with db.get_db_connection() as conn:
            user = get_user(conn, user_name, nickname)
            user_id = user["id"]
            game = user["game"]
            state = GameState(parent, user)

            state.num_solved = 0
            for coords, sg_data in persistence.fetch_saved_subgrids(conn, game["id"], user_id):
                sg: SubGrid = SubGrid.from_dict(state, sg_data)
                state.subgrids[coords] = sg
                if sg.solved:
                    state.num_solved += 1
                if state.first_click:
                    for row in sg.cells:
                        if not state.first_click:
                            break
                        for cell in row:
                            if cell.uncovered:
                                state.first_click = False
                                break

        return state

    def score(self) -> int:
        """Calculate the score based on the number of solved subgrids and difficulty."""
        return self.num_solved * mine_counts.get(self.difficulty, 8)

    def save_score(self) -> None:
        """Insert a highscore row for the current score (no-op when score is 0)."""
        # ARC-004: DB write moved to persistence.save_score.
        persistence.save_score(self)

    def save(self) -> int:
        """
        Save the game state to the SQLite database.

        Returns:
            int: The number of subgrids saved.
        """
        # ARC-004: DB writes moved to persistence.save_game_state.
        return persistence.save_game_state(self)

    @property
    def time_played(self) -> str:
        """Calculate the time played in a human-readable format."""
        return format_duration(self.duration)

    def clear_highlighted(self) -> None:
        """Clear the highlighted flag for all cells in all subgrids."""
        for cell in list(self.highlighted_cells):
            cell.highlighted = False
        self.highlighted_cells.clear()

    def clear_changed(self) -> None:
        """Clear the changed flag for all subgrids."""
        for sg in list(self.changed_subgrids):
            sg.clear_changed()
        self.changed_subgrids.clear()

    def global_to_cell(self, gx: int, gy: int, create_if_needed: bool = False) -> Cell | None:
        """
        Convert global coordinates to local cell coordinates.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            create_if_needed (bool): Whether to create the subgrid if it does not exist

        Returns:
            Cell | None: The cell at the given coordinates, or None if the subgrid does not exist and create_if_needed is False
        """
        sg_coord: GridPos = (gx // 8, gy // 8)
        local_x: int = gx % 8
        local_y: int = gy % 8
        if sg_coord not in self.subgrids:
            if not create_if_needed:
                return None
            self.subgrids[sg_coord] = SubGrid(self, sg_coord, self.difficulty)
            self.subgrids[sg_coord].changed = True
        subgrid: SubGrid = self.subgrids[sg_coord]
        return subgrid.cells[local_y][local_x]

    def cell_has_uncovered_neighbor(self, gx: int, gy: int) -> bool:
        """
        Check whether the cell at (gx, gy) has at least one uncovered neighbor.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        Returns:
            bool: True if the cell has at least one uncovered neighbor, False otherwise
        """
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: GridPos = (nx // 8, ny // 8)
                if n_sg in self.subgrids:
                    subgrid: SubGrid = self.subgrids[n_sg]
                    lx: int = nx % 8
                    ly: int = ny % 8
                    if subgrid.cells[ly][lx].uncovered or subgrid.cells[ly][lx].is_mine:
                        return True
        return False

    def count_adjacent_flags_mines(self, gx: int, gy: int) -> tuple[int, int]:
        """
        Count the number of mines adjacent to the cell at (gx, gy). Generates any adjacent subgrid that has not yet been created.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        Returns:
            tuple[int, int]: A tuple containing the number of flagged cells and the number of mines

        """
        mine_count: int = 0
        flag_count: int = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: GridPos = (nx // 8, ny // 8)
                if n_sg not in self.subgrids:
                    continue
                subgrid: SubGrid = self.subgrids[n_sg]
                lx: int = nx % 8
                ly: int = ny % 8
                if subgrid.cells[ly][lx].is_mine:
                    mine_count += 1
                if subgrid.cells[ly][lx].marked:
                    flag_count += 1
        return flag_count, mine_count

    def reveal_cell(self, gx: int, gy: int, depth: int = 0) -> None:
        """
        Reveal the cell at global coordinates (gx, gy). If it is a mine the game ends. Also, generate any adjacent subgrids as needed.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            depth (int): The depth of the recursion (to prevent infinite recursion)
        """
        if self.game_over:
            return
        sg_coord: GridPos = (gx // 8, gy // 8)
        assert self.parent
        # For non-initial subgrids, only allow a reveal if at least one neighbor is uncovered.
        if sg_coord != (0, 0) and not self.cell_has_uncovered_neighbor(gx, gy):
            self.parent.notify("No uncovered neighbors")
            return

        cell: Cell | None = self.global_to_cell(gx, gy, True)
        # Do nothing if cell is marked or uncovered.
        if not cell or cell.marked or cell.uncovered:
            return

        cell.uncovered = True
        if cell.uncovered and cell.is_mine:
            if not self.first_click:
                self.game_over = True
                self.save()
                self.save_score()
                self.parent.refresh()
                return
            cell.is_mine = False
            # ARC-015: relocate the mine to the first surrounding non-mine cell.
            # The previous code declared ``border_cell: Cell | None`` at both
            # the outer scope and again inside the inner loop, which pyright
            # flags as a redeclaration (and reads as shadowing). Renamed so the
            # accumulator (``target``) and each inspected neighbor (``candidate``)
            # are distinct variables; logic is identical.
            target: Cell | None = None
            for dx in [-1, 0, 1]:
                if target:
                    break
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx: int = gx + dx
                    ny: int = gy + dy
                    candidate: Cell | None = self.global_to_cell(nx, ny, True)
                    if candidate and not candidate.is_mine:
                        candidate.is_mine = True
                        target = candidate
                        break
        # Generate any adjacent subgrids.
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx: int = gx + dx
                ny: int = gy + dy
                n_sg: GridPos = (nx // 8, ny // 8)
                if n_sg not in self.subgrids:
                    self.subgrids[n_sg] = SubGrid(self, n_sg, self.difficulty)
                    self.subgrids[n_sg].changed = True

        # QA-002: on the entry call (depth==0) the originally-clicked cell has
        # already been through the first-click mine-relocation branch above, so
        # clear the flag NOW — before any recursion — so mines encountered during
        # the flood fill end the game instead of being silently relocated. The
        # caller used to clear this only after reveal_cell returned, leaving it
        # True for the entire opening region.
        if depth == 0:
            self.first_click = False

        # Prevent infinite recursion by limiting depth.
        if depth < 250:
            # If the cell has 0 neighboring mines, recursively reveal its neighbors.
            counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
            if counts[1] == 0:
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0:
                            continue
                        nx: int = gx + dx
                        ny: int = gy + dy
                        self.reveal_cell(nx, ny, depth + 1)
        self.check_subgrid_solved(sg_coord)

    def reveal_surround(self, gx: int, gy: int) -> None:
        """
        Reveal surrounding cells if the cell at (gx, gy) is uncovered and the number of flagged cells matches the number of mines.

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        """
        if self.game_over:
            return
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell or not cell.uncovered:
            return
        counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
        if not counts[0]:
            return

        if cell.uncovered:
            if counts[0] != counts[1]:
                # self.notify("Flag count does not match mine count", severity="error")
                return

            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx: int = gx + dx
                    ny: int = gy + dy
                    self.reveal_cell(nx, ny)
        self.save()
        assert self.parent

        self.parent.refresh()

    def highlight_neighbors(self, gx: int, gy: int) -> None:
        """
        Highlight the cell neighbors around (gx, gy).
        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
        """
        if self.game_over:
            return
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell or not cell.uncovered:
            return
        counts: tuple[int, int] = self.count_adjacent_flags_mines(gx, gy)
        # if no neighboring mines do not highlight
        if not counts[1]:
            return

        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                cell = self.global_to_cell(gx + dx, gy + dy)
                if cell and not cell.uncovered:
                    cell.highlighted = True
        assert self.parent
        self.parent.refresh()

    def toggle_mark(self, gx: int, gy: int, surround: bool = False) -> None:
        """
        Toggle the mark (flag) on the cell at global coordinates (gx, gy).

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell
            surround (bool): Whether to reveal surrounding cells if the cell is already uncovered
        """
        cell: Cell | None = self.global_to_cell(gx, gy)
        if not cell:
            return
        if cell.uncovered:
            if not surround:
                return
            self.reveal_surround(gx, gy)
            return
        cell.marked = not cell.marked
        self.save()

        assert self.parent
        self.parent.refresh()

    def check_subgrid_solved(self, sg_coord: GridPos) -> None:
        """
        Mark a subgrid as solved if the all cells that dont contain a mine have been uncovered.

        Args:
            sg_coord (GridPos): The coordinates of the subgrid
        """
        subgrid: SubGrid = self.subgrids[sg_coord]
        if subgrid.solved:
            return
        for row in subgrid.cells:
            for cell in row:
                if not cell.is_mine and not cell.uncovered:
                    return
        subgrid.solved = True
        self.num_solved += 1
        for row in subgrid.cells:
            for cell in row:
                if cell.is_mine and not cell.marked:
                    cell.marked = True

    def get_cell_representation(self, gx: int, gy: int) -> str:
        """
        Return a string representation of the cell at global coordinates (gx, gy).

        Args:
            gx (int): The global x-coordinate of the cell
            gy (int): The global y-coordinate of the cell

        Returns:
            str: The string representation of the cell
        """
        # ARC-004: markup emission now lives in renderer.render_cell; this
        # method is a stable delegate so call sites don't change.
        return render_cell(self, gx, gy)

    def post_internet_score(self) -> PostScoreResult:
        """
        Post score to the internet leaderboard.
        Args:
            game_state (GameState): Game state containing user and score data.
        Returns:
            PostScoreResult: Result of the post operation.
        """
        # ARC-004: HTTP/score posting moved to leaderboard.post_internet_score.
        return post_internet_score(self)
