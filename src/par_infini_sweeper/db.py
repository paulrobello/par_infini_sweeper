import base64
import os
import sqlite3
from pathlib import Path
from sqlite3 import Connection, Cursor
from typing import Any

import requests
from xdg_base_dirs import xdg_data_home

from par_infini_sweeper import __application_binary__
from par_infini_sweeper.db_migrations import migrate_db_to_1_1, migrate_legacy_db
from par_infini_sweeper.enums import GameDifficulty, GameMode
from par_infini_sweeper.models import (
    ScoreData,
    ScoreDataResponse,
    validate_nickname,
)

# Pure Path math at import time — no filesystem mutation. The legacy rename,
# mkdir, and backup previously ran HERE at import (ARC-007) and were then
# re-run inside every ``get_db_connection`` call (ARC-006). Both are now in
# ``init_storage`` / ``ensure_backup``, called once at app startup.
db_folder_old = Path(f"~/.{__application_binary__}").expanduser()
db_folder = xdg_data_home() / __application_binary__
db_path = db_folder / "game_data.sqlite"
db_bak_path = db_folder / "game_data.sqlite.bak"

# Refresh the .bak copy when it is older than the live DB by this margin.
# Hoisted from the inline 86400 literal so ensure_backup reads from one spot.
BACKUP_MAX_AGE_SECONDS = 86400


def init_storage() -> None:
    """Set up the on-disk storage layout and refresh the DB backup.

    Idempotent; call ONCE at app startup (``PimApp.on_mount``) before the first
    ``get_db_connection`` / ``init_db``. Previously this work ran at import time
    AND inside every ``get_db_connection`` (ARC-006/ARC-007):

      * Importing ``par_infini_sweeper.db`` used to ``mkdir`` the data folder
        and rename ``~/.pim`` → XDG — two concurrent ``pim`` processes would
        race the rename, and any test that imported the package mutated disk.
      * Every ``get_db_connection`` used to stat the DB and backup, compare
        mtimes, and periodically ``read_bytes``/``write_bytes`` the whole file.
        ``get_db_connection`` is called on every save/click, so per-click I/O
        was significant for an infinite game.
    """
    if not db_folder.parent.exists():
        db_folder.parent.mkdir(parents=True, exist_ok=True)
    if db_folder_old.exists() and not db_folder.exists():
        db_folder_old.rename(db_folder)
    ensure_backup()


def ensure_backup() -> None:
    """Maintain a recent backup of the SQLite DB. Cheap no-op once it's fresh.

    Runs once per launch via ``init_storage`` — NOT inside
    ``get_db_connection`` (see ARC-006).
    """
    # mode= alone is umask-affected on POSIX; chmod after to guarantee 0o700 so
    # other local users cannot read/overwrite the token-bearing DB folder.
    db_folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(db_folder, 0o700)
    if not db_path.exists():
        return
    if not db_bak_path.exists():
        db_bak_path.write_bytes(db_path.read_bytes())
        os.chmod(db_bak_path, 0o600)
        return
    # Refresh the backup if it's >1 day older than the live DB.
    if db_bak_path.stat().st_mtime < db_path.stat().st_mtime - BACKUP_MAX_AGE_SECONDS:
        db_bak_path.write_bytes(db_path.read_bytes())
        os.chmod(db_bak_path, 0o600)


def get_db_connection() -> sqlite3.Connection:
    """
    Return a connection to the SQLite database with a 5 sec timeout.

    Backup is NOT checked here — see ``init_storage`` / ``ensure_backup``,
    which run once at app startup. The previous implementation ran a
    stat/read/write backup check on every call (ARC-006), and
    ``get_db_connection`` is hit on every save/click.
    """
    # mkdir kept as a defensive minimum so callers that bypass init_storage
    # (tests, helpers) still get a usable folder. The backup check is NOT
    # restored here — see init_storage / ensure_backup.
    db_folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(db_folder, 0o700)
    conn = sqlite3.connect(db_path, timeout=5)
    # Restrict the live DB to owner-only — it stores OAuth access / refresh /
    # id tokens (refresh_token is long-lived via offline_access). chmod after
    # connect so an already-existing file is also tightened.
    # TODO(keyring): move refresh_token out of SQLite entirely and into the OS
    #   keychain (`keyring` library) — file-mode hardening is a stopgap.
    os.chmod(db_path, 0o600)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Connection, username: str = "user", nickname: str | None = None) -> None:
    """
    Initialize the SQLite database with required tables and default user.

    Args:
        conn (Connection): SQLite connection object. Required — every caller
            passes a live connection (no implicit ``get_db_connection`` fallback).
        username (str): Default username.
        nickname (str | None): Default nickname.

    """

    if len(username) > 20:
        raise ValueError("Username must be 20 characters or less")

    if nickname:
        validate_nickname(nickname)

    # ARC-010: conn is required — the previous ``conn = conn or get_db_connection()``
    # fallback implied None was a valid argument, but every call site passes a
    # real connection. Removed so the signature reflects the contract.
    with conn:
        cursor = conn.cursor()

        # Check if pim_db_info and users tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pim_db_info'")
        pim_db_info_exists = cursor.fetchone() is not None

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        users_exists = cursor.fetchone() is not None

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pim_db_info (
                version TEXT PRIMARY KEY
            )
        """)

        # update usernames and nicknames to be no longer than 30 characters
        if users_exists:
            cursor.execute("UPDATE users SET username = substr(username, 1, 30), nickname = substr(nickname, 1, 30)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                nickname TEXT UNIQUE NOT NULL,
                net_nickname TEXT NOT NULL DEFAULT '',
                id_token TEXT DEFAULT '',
                access_token TEXT DEFAULT '',
                refresh_token TEXT DEFAULT '',
                expires_at INTEGER NOT NULL DEFAULT 0,
                created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                id INTEGER PRIMARY KEY,
                theme TEXT NOT NULL,
                difficulty TEXT NOT NULL CHECK(difficulty IN ('easy','medium','hard')),
                FOREIGN KEY(id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL DEFAULT 'infinite',
                game_over BOOLEAN NOT NULL DEFAULT 0,
                duration INTEGER NOT NULL DEFAULT 0,
                board_offset TEXT NOT NULL DEFAULT '0,0',
                created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS highscores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grids (
                game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                sub_grid_id TEXT NOT NULL,
                grid_data TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                PRIMARY KEY (game_id, user_id, sub_grid_id)
            )
        """)

        # If users table exists but pim_db_info does not, run migrate_db
        if users_exists and not pim_db_info_exists:
            migrate_legacy_db(conn)

        cursor.execute("SELECT version FROM pim_db_info")
        db_version = cursor.fetchone()
        if db_version:
            db_version = db_version[0]
        if db_version is None:
            db_version = "1.0"
            cursor.execute("INSERT INTO pim_db_info (version) VALUES (?)", (db_version,))
        if db_version == "1.0":
            migrate_db_to_1_1(conn)
            db_version = "1.1"

        # Create default user "user" if not exists.
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone() is None:
            cursor.execute(
                "INSERT INTO users (username, nickname) VALUES (?, ?)", (username, nickname or username.capitalize())
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO user_prefs (id, theme, difficulty) VALUES (?,?,?)", (user_id, "textual-dark", "easy")
            )
            cursor.execute("INSERT INTO games (user_id) VALUES (?)", (user_id,))


def get_user(conn: Connection, username: str = "user", nickname: str | None = None) -> dict[str, Any]:
    """
    Load or create requested user.

    Args:
        conn (Connection): SQLite connection object.
        username (str): Username to load or create.
        nickname (str | None): Nickname to load or create.

    Returns:
        dict[str, Any]: User data including preferences and game state.

    """
    cursor: Cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    if row is None:
        # First-time username / typo / missing row: provision it instead of crashing
        # on dict(None) (ARC-001). The previously-hardcoded "user" lookup is also
        # fixed to re-fetch the *requested* username.
        init_db(conn, username, nickname)
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
    user = dict(row)
    # ARC-011: previously this UPDATE ran on every read, even when the value
    # was unchanged. Only write when the caller actually supplied a new
    # nickname that differs from the row's current value.
    if nickname and nickname != user["nickname"]:
        user["nickname"] = nickname
        cursor.execute("UPDATE users SET nickname = ? WHERE id = ?", (nickname, user["id"]))

    user_id = user["id"]
    cursor.execute("SELECT theme, difficulty FROM user_prefs WHERE id = ?", (user_id,))
    prefs = dict(cursor.fetchone())
    prefs["difficulty"] = GameDifficulty(prefs["difficulty"])
    user["prefs"] = prefs

    cursor.execute("SELECT * FROM games WHERE user_id = ?", (user_id,))
    game = dict(cursor.fetchone())
    user["game"] = game

    cursor.execute(
        # ARC-002: order by score DESC (then created_ts DESC as tiebreaker) so we
        # return the 10 HIGHEST scores, not the 10 OLDEST.
        "SELECT * FROM highscores WHERE game_id=? AND user_id = ? ORDER BY score DESC, created_ts DESC LIMIT 10",
        (
            game["id"],
            user_id,
        ),
    )
    highscores = cursor.fetchall()
    user["highscores"] = [dict(s) for s in highscores]

    return user


def get_highscores(num_scores: int = 10) -> dict[GameMode, list[dict[str, Any]]]:
    """
    Return top num_scores highscores for each mode.

    Args:
        num_scores (int): Number of top scores to return for each game mode.

    Returns:
        dict[GameMode,list[dict[str, Any]]]: List of top 10 highscore records for each game mode

    """
    if num_scores < 1:
        raise ValueError("num_scores must be at least 1")
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
        WITH RankedScores AS (
            SELECT
                score,
                h.created_ts,
                u.nickname,
                g.mode,
                g.duration,
                ROW_NUMBER() OVER (PARTITION BY g.mode ORDER BY score DESC, h.created_ts DESC) as rank
            FROM highscores h
            JOIN users u ON h.user_id = u.id
            JOIN games g ON g.id = h.game_id
        )
        SELECT
            score,
            created_ts,
            nickname,
            mode,
            duration
        FROM RankedScores
        WHERE rank <= ?
        ORDER BY mode, rank;
        """,
            (num_scores,),
        )
        highscores = cursor.fetchall()
        highscores = [dict(s) for s in highscores]
        result: dict[GameMode, list[dict[str, Any]]] = {}
        for gm in GameMode:
            result[gm] = []
        for h in highscores:
            if h["mode"] not in result:
                result[GameMode(h["mode"])] = []
            result[GameMode(h["mode"])].append(h)
        return result


def get_internet_highscores() -> dict[GameMode, list[ScoreData]]:
    ret: dict[GameMode, list[ScoreData]] = {}
    for mode in GameMode:
        ret[mode] = []

    url = os.environ.get("PIM_LEADERBOARD_URL", "https://pim.pardev.net") + "/score"
    # yes i know this is bad, but it helps keep random bots from hitting the api
    headers = {"api-key": base64.b64decode("V29vdFdvb3RXb290").decode(encoding="utf-8")}
    res = requests.request("GET", url, headers=headers, timeout=5).json()
    if "detail" in res:
        raise Exception(res["detail"] or "Unknown server error")
    response: ScoreDataResponse = ScoreDataResponse.model_validate(res)
    if response.status == "error":
        raise Exception(response.message or "Unknown server error")
    for item in response.scores:
        ret[GameMode(item.mode)].append(item)

    return ret


def save_user(user: dict[str, Any]) -> None:
    """
    Save user data to the database.
    Args:
        user (dict[str, Any]): User data containing id_token and access_token.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE users
            SET id_token = ?, access_token = ?, refresh_token = ?, expires_at = ?, nickname=?, net_nickname=?
            WHERE id = ?""",
            (
                user["id_token"],
                user["access_token"],
                user["refresh_token"],
                user["expires_at"],
                user["nickname"],
                user["net_nickname"],
                user["id"],
            ),
        )
