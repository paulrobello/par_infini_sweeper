from sqlite3 import Connection


def migrate_db_to_1_1(conn: Connection) -> None:
    """
    Migrate the SQLite database from version 1.0 to 1.1.

    Args:
        conn (Connection): SQLite connection object.
    """
    with conn:
        cursor = conn.cursor()

        # Add created_ts column to users table if it doesn't exist
        cursor.execute("PRAGMA table_info(games)")
        columns = [col[1] for col in cursor.fetchall()]

        if "duration" not in columns:
            cursor.execute("ALTER TABLE games ADD COLUMN duration INTEGER NOT NULL DEFAULT 0")
            cursor.execute("UPDATE games SET duration = play_duration")
            cursor.execute("ALTER TABLE games DROP COLUMN play_duration")

        if "mode" not in columns:
            cursor.execute("ALTER TABLE games ADD COLUMN mode TEXT NOT NULL DEFAULT 'infinite'")
            cursor.execute("UPDATE games SET mode = game_mode")
            cursor.execute("ALTER TABLE games DROP COLUMN game_mode")

        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if "net_nickname" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN net_nickname TEXT DEFAULT ''")
            cursor.execute("UPDATE users SET net_nickname = ''")

        if "id_token" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN id_token TEXT DEFAULT ''")
            cursor.execute("UPDATE users SET id_token = ''")
        if "access_token" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN access_token TEXT DEFAULT ''")
            cursor.execute("UPDATE users SET access_token = ''")
        if "refresh_token" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN refresh_token TEXT DEFAULT ''")
            cursor.execute("UPDATE users SET refresh_token = ''")
        if "expires_at" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN expires_at INTEGER DEFAULT 0")
            cursor.execute("UPDATE users SET expires_at = 0")

        cursor.execute("UPDATE pim_db_info set version = ?", ("1.1",))


def migrate_legacy_db(conn: Connection) -> None:
    """
    Migrate the SQLite database to the current schema.

    Args:
        conn (Connection): SQLite connection object.
    """
    with conn:
        cursor = conn.cursor()

        # Add created_ts column to users table if it doesn't exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if "created_ts" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN created_ts TIMESTAMP")
            cursor.execute("UPDATE users SET created_ts = CURRENT_TIMESTAMP WHERE created_ts IS NULL")

        # Add game_mode column to games table if it doesn't exist
        cursor.execute("PRAGMA table_info(games)")
        columns = [col[1] for col in cursor.fetchall()]
        if "game_mode" not in columns:
            cursor.execute("ALTER TABLE games ADD COLUMN game_mode TEXT NOT NULL DEFAULT 'infinite'")

        # Add ON DELETE CASCADE to foreign keys if not present
        cursor.execute("PRAGMA foreign_key_list(user_prefs)")
        foreign_keys = cursor.fetchall()
        if not any(fk[5] == "CASCADE" for fk in foreign_keys):
            cursor.execute("""
                CREATE TABLE user_prefs_new (
                    id INTEGER PRIMARY KEY,
                    theme TEXT NOT NULL,
                    difficulty TEXT NOT NULL CHECK(difficulty IN ('easy','medium','hard')),
                    FOREIGN KEY(id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("INSERT INTO user_prefs_new SELECT * FROM user_prefs")
            cursor.execute("DROP TABLE user_prefs")
            cursor.execute("ALTER TABLE user_prefs_new RENAME TO user_prefs")

        cursor.execute("PRAGMA foreign_key_list(games)")
        foreign_keys = cursor.fetchall()
        if not any(fk[5] == "CASCADE" for fk in foreign_keys):
            cursor.execute("""
                CREATE TABLE games_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    game_mode TEXT NOT NULL DEFAULT 'infinite',
                    game_over BOOLEAN NOT NULL DEFAULT 0,
                    duration INTEGER NOT NULL DEFAULT 0,
                    board_offset TEXT NOT NULL DEFAULT '0,0',
                    created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute(
                "INSERT INTO games_new (id, user_id, game_mode, game_over, duration, board_offset) SELECT id, user_id, game_mode, game_over, duration, board_offset FROM games"
            )
            cursor.execute("DROP TABLE games")
            cursor.execute("ALTER TABLE games_new RENAME TO games")

        cursor.execute("PRAGMA foreign_key_list(highscores)")
        foreign_keys = cursor.fetchall()
        if not any(fk[5] == "CASCADE" for fk in foreign_keys):
            cursor.execute("""
                CREATE TABLE highscores_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    game_id INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("INSERT INTO highscores_new SELECT * FROM highscores")
            cursor.execute("DROP TABLE highscores")
            cursor.execute("ALTER TABLE highscores_new RENAME TO highscores")

        cursor.execute("PRAGMA foreign_key_list(grids)")
        foreign_keys = cursor.fetchall()
        if not any(fk[5] == "CASCADE" for fk in foreign_keys):
            cursor.execute("""
                CREATE TABLE grids_new (
                    game_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    sub_grid_id TEXT NOT NULL,
                    grid_data TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
                    PRIMARY KEY (game_id, user_id, sub_grid_id)
                )
            """)
            cursor.execute("INSERT INTO grids_new SELECT * FROM grids")
            cursor.execute("DROP TABLE grids")
            cursor.execute("ALTER TABLE grids_new RENAME TO grids")
