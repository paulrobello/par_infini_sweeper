"""Pytest configuration for par_infini_sweeper.

Routes around the package's import-time side effects (ARC-007, a later phase,
eliminates them at the source). Until then we:

  * Point ``XDG_DATA_HOME`` at a session-scoped tmp dir BEFORE the package is
    imported, so ``par_infini_sweeper.db`` (which computes ``db_folder`` at
    import time) writes its SQLite files there instead of polluting the host.
  * Set ``USER`` so ``__main__`` / ``pim_app`` have a deterministic default.
  * Set ``PIM_LEADERBOARD_URL`` to a loopback sink so any test that
    accidentally reaches into the leaderboard client fails fast instead of
    hitting production.

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
