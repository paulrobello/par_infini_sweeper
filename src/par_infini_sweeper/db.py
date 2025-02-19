import sqlite3
from pathlib import Path
from sqlite3 import Connection
from typing import Any

from par_infini_sweeper import __application_binary__
from par_infini_sweeper.enums import GameDifficulty


def get_db_connection() -> sqlite3.Connection:
    """Return a connection to the SQLite database with a 10 sec timeout."""
    db_path = Path(f"~/.{__application_binary__}").expanduser() / "game_data.sqlite"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: Connection, username: str = "user", nickname: str = "User") -> None:
    """Initialize the SQLite database with required tables and default user."""
    conn = conn or get_db_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                nickname TEXT UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_prefs (
                id INTEGER PRIMARY KEY,
                theme TEXT NOT NULL,
                difficulty TEXT NOT NULL CHECK(difficulty IN ('easy','medium','hard')),
                FOREIGN KEY(id) REFERENCES users(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_over BOOLEAN NOT NULL DEFAULT 0,
                play_duration INTEGER NOT NULL DEFAULT 0,
                board_offset TEXT NOT NULL DEFAULT '0,0',
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS highscores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
                FOREIGN KEY(game_id) REFERENCES games(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grids (
                game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                sub_grid_id TEXT NOT NULL,
                grid_data TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(game_id) REFERENCES games(id),
                PRIMARY KEY (game_id, user_id, sub_grid_id)
            )
        """)
        # Create default user "user" if not exists.
        cursor.execute("SELECT id FROM users WHERE username = ? AND nickname = ?", (username, nickname))
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO users (username, nickname) VALUES (?, ?)", (username, nickname))
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO user_prefs (id, theme, difficulty) VALUES (?,?,?)", (user_id, "textual-dark", "easy")
            )
            cursor.execute("INSERT INTO games (user_id) VALUES (?)", (user_id,))


def get_user(conn: Connection, username: str = "user", nickname: str = "User") -> dict[str, Any]:
    """Load default user."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = dict(cursor.fetchone())
    if user is None:
        # If default user not found, initialize the DB.
        init_db(conn, username, nickname)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", ("user",))
        user = dict(cursor.fetchone())

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
            user["game"]["id"],
            user_id,
        ),
    )
    highscores = cursor.fetchall()
    user["highscores"] = [dict(s) for s in highscores]

    return user


def get_highscores() -> list[dict[str, Any]]:
    """Return top 10 highscores."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT score, created_ts, u.nickname 
        FROM highscores h
        JOIN users u ON h.user_id = u.id
        ORDER BY score DESC, created_ts DESC LIMIT 10
        """)
        highscores = cursor.fetchall()
        return [dict(s) for s in highscores]
