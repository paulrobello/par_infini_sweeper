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

import logging
import time
from collections import deque
from collections.abc import Iterator
from typing import Any

from authlib.integrations.requests_client import OAuth2Session
from jose import JWTError, jwt
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

logger = logging.getLogger(__name__)

# QA-003: safety bound on the reveal flood-fill BFS. Natural queue draining
# handles normal openings; this caps pathological inputs (e.g. a corrupted
# board where every cell thinks it has zero mine neighbours) so the loop
# cannot run away. It is NOT a recursion limit and never silently truncates a
# legitimate reveal — the visited set is the real termination guarantee.
MAX_REVEAL_ITERATIONS = 250

_CELL_OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


class GameState:
    """Represents the overall game state including difficulty and all subgrids."""

    def __init__(self, parent: Widget | None, user: dict[str, Any]) -> None:
        """Initialize game state for a loaded user.

        Args:
            parent: The owning Textual widget (``MainGrid``) used for
                ``notify`` / ``refresh`` calls, or ``None`` for headless tests.
                See ``GameState.parent`` and the model↔UI coupling note in the
                module docstring — this bridge is intentional pending a
                Message-based decoupling.
            user: User row dict from ``db.get_user`` (or the load path's
                ``init_db`` fallback). Must carry ``prefs``, ``game``, and the
                OAuth token columns; the dict is held by reference and mutated
                in place by ``save_user`` / leaderboard helpers.
        """
        self.parent = parent
        self.mode: GameMode = GameMode.INFINITE
        self.user: dict[str, Any] = user
        self.difficulty: GameDifficulty = user["prefs"]["difficulty"]
        self.theme: str = user["prefs"]["theme"]
        self.subgrids: dict[GridPos, SubGrid] = {}
        self.subgrids[(0, 0)] = SubGrid(self, (0, 0), self.difficulty)
        game: dict[str, Any] = user["game"]
        offset: list[str] = game["board_offset"].split(",")
        # QA-007: runtime validation must survive ``python -O`` (assert is stripped).
        if len(offset) != 2:
            raise ValueError(f"board_offset must be 'x,y', got {game['board_offset']!r} ({len(offset)} parts)")
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
        """Return an authenticated ``OAuth2Session``, building/refreshing it on demand.

        If the cached session is missing or the access token is no longer valid,
                this rebuilds it via ``build_auth_client`` (which transparently
                refreshes the token if a ``refresh_token`` is available, or starts
                the interactive OAuth loopback login flow otherwise).

        Raises:
            RuntimeError: If ``self.parent`` is ``None`` or has no running app
                (the OAuth flow needs the app to post ``ShowURL`` /
                ``WebServerStarted`` / ``WebServerStopped`` messages).
        """
        if not self._auth_client or not self.is_logged_in():
            # QA-007: parent + app are required to build the OAuth session; raise
            # rather than assert so the check survives ``python -O``.
            if self.parent is None or self.parent.app is None:
                raise RuntimeError("auth_client requires a parent widget with a running app")
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
        except JWTError:
            # QA-004: malformed / tampered / unparsable JWT means the session
            # is invalid — log and tear it down rather than silently swallowing.
            logger.exception("access token failed JWT parsing; logging out")
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
            ChangeNicknameResponse: Result of the change operation.
        """
        # ARC-004: HTTP/nickname logic moved to leaderboard.change_internet_nickname.
        return change_internet_nickname(self, nickname)

    def new_game(self) -> None:
        """Start a new game by resetting the game state.

        Clears all subgrids back to a single fresh ``(0, 0)`` subgrid, resets
        score / duration / game_over / first_click / highlight state, deletes
        the persisted ``grids`` rows for the current user, and saves the fresh
        state. Existing OAuth tokens and user preferences are preserved.
        """

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
        """Compute the cell-coordinate at which ``action_center`` should anchor.

        QA-010: returns ``Offset(0, 0)`` when there are no subgrids rather than
        dividing by zero (this state is reachable mid-reset between
        ``new_game`` clearing ``self.subgrids`` and the first subgrid being
        inserted).

        The ``+5`` / ``-3`` are the same viewport anchor ``MainGrid.action_origin``
        uses to centre on the (0,0) subgrid alone: they bias the multi-subgrid
        centroid so the origin subgrid's centre sits in a comfortable quadrant
        of the viewport instead of flush at the corner. With only the origin
        subgrid present the centroid is (0, 0) and the result reduces to
        ``Offset(5, -3)`` — identical to ``action_origin``'s anchor.
        """
        if not self.subgrids:
            return Offset(0, 0)
        total_x = sum(k[0] * 8 for k in self.subgrids)
        total_y = sum(k[1] * 8 for k in self.subgrids)
        n = len(self.subgrids)
        return Offset(total_x // n + 5, total_y // n - 3)

    @property
    def num_changed(self) -> int:
        """Return the count of subgrids currently marked dirty (pending save)."""
        return sum(1 for sg in self.subgrids.values() if sg.changed)

    @property
    def num_subgrids(self) -> int:
        """Return the total number of subgrids in the game (solved + unsolved)."""
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

    @staticmethod
    def _iter_neighbor_coords(gx: int, gy: int) -> Iterator[tuple[int, int]]:
        """Yield the 8 global neighbour coordinates of ``(gx, gy)``.

        QA-008: the nested ``for dx in [-1, 0, 1]: for dy in [-1, 0, 1]``
        pattern with the ``dx == 0 and dy == 0`` skip was copy-pasted through
        every neighbour walk. Routing through one generator keeps the
        off-by-one skip in a single place and gives call sites a flat
        ``for nx, ny in ...`` loop.
        """
        for dx, dy in _CELL_OFFSETS:
            yield gx + dx, gy + dy

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
        for nx, ny in self._iter_neighbor_coords(gx, gy):
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
        for nx, ny in self._iter_neighbor_coords(gx, gy):
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
        """Reveal the cell at global coordinates ``(gx, gy)``.

        If the cell is a mine the game ends, unless it is the user's first
        click — in which case the mine is relocated to a neighbouring non-mine
        cell so the opening never loses on the first click. Cells with zero
        adjacent mines trigger a flood-fill that reveals every connected empty
        cell via an iterative BFS (QA-003: replaces the depth-bounded
        recursion — no recursion-limit risk, no magic depth cap silently
        truncating large openings).

        Args:
            gx (int): The global x-coordinate of the cell.
            gy (int): The global y-coordinate of the cell.
            depth (int): Reserved. Pre-BFS this was the recursion depth; the
                BFS rewrite ignores it but the parameter is retained so
                external callers (and tests) that pass ``depth=N`` to simulate
                an in-flood-fill state keep working.
        """
        if self.game_over:
            return
        sg_coord: GridPos = (gx // 8, gy // 8)
        # QA-007: parent is required for UI notifications; raise rather than
        # assert so the check survives ``python -O``.
        if self.parent is None:
            raise RuntimeError("reveal_cell requires a parent widget for UI notifications")
        # For non-initial subgrids, only allow a reveal if at least one neighbor is uncovered.
        if sg_coord != (0, 0) and not self.cell_has_uncovered_neighbor(gx, gy):
            self.parent.notify("No uncovered neighbors")
            return

        cell: Cell | None = self.global_to_cell(gx, gy, True)
        # Do nothing if cell is marked or uncovered.
        if not cell or cell.marked or cell.uncovered:
            return

        cell.uncovered = True
        if cell.is_mine:
            if not self.first_click:
                self._end_game()
                return
            # ARC-015: relocate the mine to the first surrounding non-mine cell.
            # Pre-QA-003 this inline loop declared ``border_cell`` at both the
            # outer scope and again inside the inner loop (shadowing); extracted
            # helper uses ``target`` (accumulator) / ``candidate`` (each
            # inspected neighbour) so the names stay distinct.
            self._relocate_first_click_mine(gx, gy, cell)

        # Generate any adjacent subgrids.
        self._ensure_neighbor_subgrids(gx, gy)

        # QA-002: on the entry call (depth==0) the originally-clicked cell has
        # already been through the first-click mine-relocation branch above, so
        # clear the flag NOW — before the flood fill — so mines encountered
        # during expansion end the game instead of being silently relocated.
        # The caller used to clear this only after reveal_cell returned,
        # leaving it True for the entire opening region.
        if depth == 0:
            self.first_click = False

        # QA-003: BFS flood-fill — no recursion, no depth cap on legitimate
        # openings. Returns the set of subgrids it revealed into so the
        # orchestrator can run ``check_subgrid_solved`` on each (mirroring the
        # pre-BFS behaviour where every recursive call ended with a solve
        # check on its own subgrid).
        touched_subgrids = self._flood_fill_reveal(gx, gy)
        self.check_subgrid_solved(sg_coord)
        for touched_sg in touched_subgrids:
            self.check_subgrid_solved(touched_sg)

    def _end_game(self) -> None:
        """Mark the game as over, persist the final state, and refresh the UI."""
        self.game_over = True
        self.save()
        self.save_score()
        if self.parent is not None:
            self.parent.refresh()

    def _relocate_first_click_mine(self, gx: int, gy: int, clicked: Cell) -> None:
        """Move the mine off the first-clicked cell to a neighbouring non-mine cell.

        ARC-015: the original code declared ``border_cell: Cell | None`` twice
        (outer scope + inner loop), which reads as shadowing. Renamed so the
        accumulator (``target``) and each inspected neighbour (``candidate``)
        are distinct variables; logic is byte-for-byte identical.

        Args:
            gx (int): The global x-coordinate of the clicked cell.
            gy (int): The global y-coordinate of the clicked cell.
            clicked (Cell): The clicked cell whose mine flag is being relocated.
        """
        clicked.is_mine = False
        target: Cell | None = None
        for nx, ny in self._iter_neighbor_coords(gx, gy):
            if target is not None:
                break
            candidate: Cell | None = self.global_to_cell(nx, ny, True)
            if candidate is not None and not candidate.is_mine:
                candidate.is_mine = True
                target = candidate

    def _ensure_neighbor_subgrids(self, gx: int, gy: int) -> None:
        """Create the 8 neighbour subgrids of ``(gx, gy)`` if they don't yet exist.

        Preserves the pre-BFS side effect where ``reveal_cell`` materialised
        adjacent subgrids regardless of whether the flood fill expanded into
        them, so subsequent ``count_adjacent_flags_mines`` /
        ``cell_has_uncovered_neighbor`` queries don't silently no-op on
        missing subgrids.
        """
        for nx, ny in self._iter_neighbor_coords(gx, gy):
            n_sg: GridPos = (nx // 8, ny // 8)
            if n_sg not in self.subgrids:
                self.subgrids[n_sg] = SubGrid(self, n_sg, self.difficulty)
                self.subgrids[n_sg].changed = True

    def _flood_fill_reveal(self, start_gx: int, start_gy: int) -> set[GridPos]:
        """BFS-reveal every empty cell reachable from ``(start_gx, start_gy)``.

        QA-003: replaces the depth-bounded recursion (magic ``250`` cap that
        silently truncated large openings, plus recursion-limit risk). Uses an
        explicit visited set + BFS queue; ``MAX_REVEAL_ITERATIONS`` is a safety
        bound against pathological inputs (corrupted board where every cell
        reports zero mine neighbours), not a recursion limit, and never
        truncates a legitimate reveal — the visited set alone guarantees
        termination on a well-formed board.

        First-click safety is preserved by the caller: ``first_click`` is
        cleared at the entry call (``depth == 0``) before this method runs,
        so any mine encountered here is a real mine hit and ends the game
        rather than being silently relocated.

        Args:
            start_gx (int): The global x-coordinate to flood from (the cell the
                user clicked, already revealed by the caller).
            start_gy (int): The global y-coordinate to flood from.

        Returns:
            set[GridPos]: The subgrid coordinates that had at least one cell
            revealed by this flood, so the caller can run ``check_subgrid_solved``
            on each (mirroring the pre-BFS per-call solve check).
        """
        visited: set[tuple[int, int]] = {(start_gx, start_gy)}
        queue: deque[tuple[int, int]] = deque([(start_gx, start_gy)])
        touched_subgrids: set[GridPos] = set()
        iterations = 0
        while queue:
            iterations += 1
            if iterations > MAX_REVEAL_ITERATIONS:
                logger.warning(
                    "reveal flood-fill hit %d-iteration safety bound; this indicates a corrupted board",
                    MAX_REVEAL_ITERATIONS,
                )
                break
            cx, cy = queue.popleft()
            # Stop expanding once the game has ended (mine hit) — recursive
            # calls would no-op on the game_over guard anyway.
            if self.game_over:
                break
            _, mine_count = self.count_adjacent_flags_mines(cx, cy)
            # Only expand through cells whose neighbours are all mine-free.
            if mine_count != 0:
                continue
            for nx, ny in self._iter_neighbor_coords(cx, cy):
                if (nx, ny) in visited:
                    continue
                n_cell: Cell | None = self.global_to_cell(nx, ny, True)
                if n_cell is None or n_cell.marked or n_cell.uncovered:
                    continue
                n_cell.uncovered = True
                visited.add((nx, ny))
                touched_subgrids.add((nx // 8, ny // 8))
                # QA-002: first_click was cleared before the flood started, so
                # a mine here is a real mine hit — end the game rather than
                # relocate.
                if n_cell.is_mine:
                    self._end_game()
                    return touched_subgrids
                # Preserve the per-cell "generate neighbour subgrids" side effect.
                self._ensure_neighbor_subgrids(nx, ny)
                queue.append((nx, ny))
        return touched_subgrids

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

            for nx, ny in self._iter_neighbor_coords(gx, gy):
                self.reveal_cell(nx, ny)
        self.save()
        # QA-007: parent is required for refresh; raise rather than assert.
        if self.parent is None:
            raise RuntimeError("reveal_surround requires a parent widget for UI refresh")
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

        for nx, ny in self._iter_neighbor_coords(gx, gy):
            n_cell: Cell | None = self.global_to_cell(nx, ny)
            if n_cell and not n_cell.uncovered:
                n_cell.highlighted = True
        # QA-007: parent is required for refresh; raise rather than assert.
        if self.parent is None:
            raise RuntimeError("highlight_neighbors requires a parent widget for UI refresh")
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

        # QA-007: parent is required for refresh; raise rather than assert.
        if self.parent is None:
            raise RuntimeError("toggle_mark requires a parent widget for UI refresh")
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

        Returns:
            PostScoreResult: Result of the post operation.
        """
        # ARC-004: HTTP/score posting moved to leaderboard.post_internet_score.
        return post_internet_score(self)
