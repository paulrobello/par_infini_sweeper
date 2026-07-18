"""Regression tests for ``par_infini_sweeper.db``.

Covers the two Critical correctness bugs:
  * ARC-001 — ``get_user`` crashed with ``TypeError`` on any unrecognized
    username because ``dict(cursor.fetchone())`` ran before the ``None``
    check, making the self-heal branch unreachable. The fallback also
    hard-coded ``"user"`` instead of the requested username.
  * ARC-002 — the per-user highscores query ordered by ``created_ts`` (ASC)
    with ``LIMIT 10``, returning the 10 OLDEST finishes instead of the 10
    HIGHEST scores.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from par_infini_sweeper.db import get_user, init_db


def _insert_highscores(conn: sqlite3.Connection, game_id: int, user_id: int, scores: list[int]) -> None:
    for score in scores:
        conn.execute(
            "INSERT INTO highscores (game_id, user_id, score) VALUES (?, ?, ?)",
            (game_id, user_id, score),
        )
    conn.commit()


# --- ARC-001 ----------------------------------------------------------------


def test_get_user_provisions_missing_user(fresh_db_conn: sqlite3.Connection) -> None:
    """A first-time / mistyped username must self-heal instead of crashing."""
    # The fixture initialises the DB with username="user"; ask for someone else.
    user = get_user(fresh_db_conn, "newcomer", None)
    assert user["username"] == "newcomer"
    # Row must be a real user dict, not None / partial.
    assert isinstance(user["id"], int)
    assert user["id"] > 0
    assert "prefs" in user
    assert "game" in user
    assert "highscores" in user


def test_get_user_missing_with_nickname_persists(fresh_db_conn: sqlite3.Connection) -> None:
    """The self-heal path must also accept the requested nickname."""
    user = get_user(fresh_db_conn, "stranger", "Bob")
    assert user["username"] == "stranger"
    assert user["nickname"] == "Bob"


def test_get_user_re_fetches_requested_username_not_hardcoded(
    fresh_db_conn: sqlite3.Connection,
) -> None:
    """ARC-001 also fixed the fallback query hard-coding "user" instead of the
    requested username — a subsequent lookup must find the requested name."""
    get_user(fresh_db_conn, "alice", None)
    # A fresh connection reading the same DB file should find alice, not "user".
    db_path = Path(fresh_db_conn.execute("PRAGMA database_list").fetchone()["file"])
    fresh_db_conn.close()
    conn2 = sqlite3.connect(db_path, timeout=5)
    conn2.row_factory = sqlite3.Row
    try:
        user = get_user(conn2, "alice", None)
    finally:
        conn2.close()
    assert user["username"] == "alice"


def test_get_user_existing_user_round_trip(fresh_db_conn: sqlite3.Connection) -> None:
    """A user that already exists is returned without re-creating or crashing."""
    get_user(fresh_db_conn, "stable", None)
    again = get_user(fresh_db_conn, "stable", None)
    assert again["username"] == "stable"


# --- ARC-002 ----------------------------------------------------------------


def test_get_user_highscores_returns_10_highest_descending(
    fresh_db_conn: sqlite3.Connection,
) -> None:
    """Insert 12 distinct scores out of value-order and assert the user dict
    carries exactly the 10 highest in descending score order."""
    user = get_user(fresh_db_conn, "scorer", None)
    game_id = user["game"]["id"]
    user_id = user["id"]

    inserted = [10, 50, 20, 100, 30, 80, 40, 70, 60, 90, 110, 5]
    _insert_highscores(fresh_db_conn, game_id, user_id, inserted)

    refreshed = get_user(fresh_db_conn, "scorer", None)
    scores = [row["score"] for row in refreshed["highscores"]]

    expected = sorted(inserted, reverse=True)[:10]
    assert scores == expected
    assert scores[0] == 110
    assert scores[-1] == 20
    assert len(scores) == 10


def test_get_user_highscores_descending_score_then_created_ts(
    fresh_db_conn: sqlite3.Connection,
) -> None:
    """Equal scores break ties by created_ts DESC (most recent first)."""
    user = get_user(fresh_db_conn, "ties", None)
    game_id = user["game"]["id"]
    user_id = user["id"]

    # Three identical scores inserted in sequence — most recent should come first.
    for _ in range(3):
        _insert_highscores(fresh_db_conn, game_id, user_id, [42])

    refreshed = get_user(fresh_db_conn, "ties", None)
    rows = refreshed["highscores"]
    assert len(rows) == 3
    assert all(r["score"] == 42 for r in rows)
    created_ts = [r["created_ts"] for r in rows]
    assert created_ts == sorted(created_ts, reverse=True)


def test_get_user_highscores_fewer_than_ten(fresh_db_conn: sqlite3.Connection) -> None:
    """With only 3 scores, get_user returns all 3 in descending order."""
    user = get_user(fresh_db_conn, "few", None)
    game_id = user["game"]["id"]
    user_id = user["id"]
    _insert_highscores(fresh_db_conn, game_id, user_id, [7, 77, 17])

    refreshed = get_user(fresh_db_conn, "few", None)
    scores = [r["score"] for r in refreshed["highscores"]]
    assert scores == [77, 17, 7]


# --- init_db behaviour needed by the regressions above ----------------------


def test_init_db_creates_default_user(tmp_path: Path) -> None:
    """init_db on a fresh connection must seed the requested user + a game row
    (the regression tests above rely on this so get_user has a game_id to join)."""
    db_path = tmp_path / "fresh.sqlite"
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn, "solo", None)
        row = conn.execute("SELECT username FROM users WHERE username = ?", ("solo",)).fetchone()
        assert row is not None
        assert row["username"] == "solo"
    finally:
        conn.close()


def test_init_db_rejects_overlong_username(tmp_path: Path) -> None:
    """SEC-006 / models.validate_nickname canonical length cap is 20 chars."""
    db_path = tmp_path / "fresh.sqlite"
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        with pytest.raises(ValueError):
            init_db(conn, "x" * 21, None)
    finally:
        conn.close()
