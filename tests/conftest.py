"""Pytest configuration for par_infini_sweeper.

ARC-007 has landed: ``import par_infini_sweeper`` no longer has filesystem /
env side effects (load_dotenv, mkdir, legacy rename, USER_AGENT write, PimApp
re-export all moved out of ``__init__.py``). The env setup below stays as a
defensive safety net for any test code that DOES touch the package's storage
layer (e.g. via ``get_db_connection`` or ``GameState.load``):

  * ``XDG_DATA_HOME`` → session tmp dir, set BEFORE any par_infini_sweeper
    import so ``par_infini_sweeper.db.db_folder`` (still computed at import
    time as pure Path math) resolves under it.
  * ``USER`` → deterministic default for any code path that reads it.
  * ``PIM_LEADERBOARD_URL`` → loopback sink so an accidental reach into the
    leaderboard client fails fast instead of hitting production.

Tests that need a per-test SQLite file should use the ``fresh_db_conn``
fixture rather than touching the package-level data dir directly.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# --- env setup MUST happen before any `import par_infini_sweeper` ------------
_TMP_DATA_HOME = Path(tempfile.mkdtemp(prefix="pim-test-xdg-"))
os.environ["XDG_DATA_HOME"] = str(_TMP_DATA_HOME)
os.environ.setdefault("USER", "testuser")
os.environ.setdefault("PIM_LEADERBOARD_URL", "http://127.0.0.1:1")

import pytest  # noqa: E402


@pytest.fixture()
def fresh_db_conn(tmp_path: Path):
    """Return a fresh sqlite3 Connection to an initialised DB at ``tmp_path``.

    The connection uses ``sqlite3.Row`` so dict() works on rows the same way
    the production code expects. Tables are created via ``init_db`` so the
    schema (and migration story) matches what ``get_user`` etc. rely on.
    """
    import sqlite3

    from par_infini_sweeper.db import init_db

    db_path = tmp_path / "test_game_data.sqlite"
    conn = sqlite3.connect(db_path, timeout=5)
    conn.row_factory = sqlite3.Row
    init_db(conn, "user", None)
    return conn
