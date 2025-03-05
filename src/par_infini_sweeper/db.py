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
)

db_folder_old = Path(f"~/.{__application_binary__}").expanduser()
db_folder = xdg_data_home() / __application_binary__

if not db_folder.parent.exists():
    db_folder.parent.mkdir(parents=True, exist_ok=True)


if db_folder_old.exists() and not db_folder.exists():
    db_folder = db_folder_old.rename(db_folder)


db_path = db_folder / "game_data.sqlite"
db_bak_path = db_folder / "game_data.sqlite.bak"


def get_db_connection() -> sqlite3.Connection:
    """
    Return a connection to the SQLite database with a 5 sec timeout.
    Also creates a backup of the database if it doesn't exist or if it's older than 1 day.
    """
    db_folder.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        if not db_bak_path.exists():
            db_bak_path.write_bytes(db_path.read_bytes())
        else:
            # if backup is older than 1 day, replace it with the current db
            if db_bak_path.stat().st_mtime < (db_path.stat().st_mtime - 86400):
                db_bak_path.write_bytes(db_path.read_bytes())

    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Connection, username: str = "user", nickname: str | None = None) -> None:
    """
    Initialize the SQLite database with required tables and default user.

    Args:
        conn (Connection): SQLite connection object.
        username (str): Default username.
        nickname (str | None): Default nickname.

    """

    if len(username) > 20:
        raise ValueError("Username must be 20 characters or less")

    if nickname and len(nickname) > 20:
        raise ValueError("Nickname must be 20 characters or less")

    conn = conn or get_db_connection()
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
    user = dict(cursor.fetchone())
    if user is None:
        # If default user not found, initialize the DB.
        init_db(conn, username, nickname)
        cursor.execute("SELECT id FROM users WHERE username = ?", ("user",))
        user = dict(cursor.fetchone())
    else:
        user["nickname"] = nickname or user["nickname"]
        cursor.execute("UPDATE users SET nickname = ? WHERE id = ?", (user["nickname"], user["id"]))

    user_id = user["id"]
    cursor.execute("SELECT theme, difficulty FROM user_prefs WHERE id = ?", (user_id,))
    prefs = dict(cursor.fetchone())
    prefs["difficulty"] = GameDifficulty(prefs["difficulty"])
    user["prefs"] = prefs

    cursor.execute("SELECT * FROM games WHERE user_id = ?", (user_id,))
    game = dict(cursor.fetchone())
    user["game"] = game

    cursor.execute(
        "SELECT * FROM highscores WHERE game_id=? AND user_id = ? order by created_ts limit 10",
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
