# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Nothing yet.

## [0.4.0] - 2026-07-18

Audit remediation (security, correctness, architecture, code quality, documentation) plus cross-platform cell flagging.

### Added

- **F key** to flag the cell under the mouse cursor, and **right-click** to flag a covered cell — terminal-independent flagging. Shift/Ctrl+click flagging was unreliable because terminals reserve Shift for text selection and don't always report Ctrl on mouse events; right-click works in most modern terminals and the F key works in every terminal on every OS.
- `pytest` + `pytest-asyncio` test harness with 39 tests covering the regression bugs below, `SubGrid` generation, flood-fill, scoring, save/load round-trips, nickname validation, DB migrations, and the full mouse/flagging pipeline. `make test` and CI now actually run tests.
- `docs/CONFIGURATION.md` documenting `PIM_LEADERBOARD_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, and `USER`.
- `CHANGELOG.md` (this file), migrated from the inline README history with duplicates and typos corrected.
- PKCE (`code_verifier` / `code_challenge=S256`) to the OAuth2 authorization-code flow (SEC-001).
- `SO_REUSEADDR` on the OAuth callback listener plus a surfaced `AuthServerError` UI message when port `1999` is already in use (ARC-018).
- One-time stderr warning when `AUTH0_CLIENT_ID` is unset (local dev hits the production Auth0 tenant by default) (ARC-019).
- Stderr warning from `pim --server` that the web server is unauthenticated and localhost-only (SEC-010).
- Stderr warning when nickname migration truncates an overlong stored nickname to the 20-char limit (SEC-009).

### Changed

- Decomposed the 865-LOC `data_structures.py` god module into `game/`, `persistence/leaderboard`, and `renderer` modules; `GameState` now consumes them instead of inlining game logic, OAuth HTTP, and Rich-rendering (ARC-004).
- Hoisted the per-connection DB backup check out of `get_db_connection` into a single `init_storage` call at app startup; per-click I/O no longer stats and copies the database (ARC-006).
- Moved `load_dotenv()` and `USER_AGENT` env mutation out of `par_infini_sweeper.__init__` into `__main__` so importing the package is side-effect-free (ARC-007).
- Deferred `PimApp` heavy DB I/O from `__init__` to `on_mount` so the event loop starts before SQLite/auth bootstrap runs (ARC-017).
- `make checkall` no longer auto-fixes files in CI: `lint`/`format` are split into check-only variants for the gate while keeping the fix-applying variants for local use (ARC-008).
- Centralized nickname validation in `models.validate_nickname` (one regex, one 20-char cap) and routed every call site through it (SEC-006). The previous code allowed 30 chars on some paths.
- Replaced eight bare `except Exception` blocks with specific exception types (`OAuth2Error`, `requests.RequestException`, `sqlite3.Error`) and routed failures through `logging` (QA-004).
- Rewrote `reveal_cell` flood fill as an explicit iterative BFS with a visited set, replacing the recursive depth-capped implementation (QA-003).
- OAuth callback handler no longer reflects the request `Host` header into `authorization_response` and matches the callback path exactly (SEC-004, SEC-005).
- Hardened on-disk token storage: DB folder `0o700`, DB and backup files `0o600` (SEC-002, SEC-008).

### Fixed

- `get_highscores()` now orders by `score DESC, created_ts DESC` so the local high-score tab shows the user's top 10 finishes instead of their 10 oldest games (ARC-002).
- `get_user()` no longer crashes with `TypeError` on an unrecognized username; it provisions the row and re-fetches the requested username (ARC-001).
- First-click safety now clears `first_click` before flood-fill recursion, so only the clicked cell is mine-scrubbed rather than every mine bordering the opening region (QA-002).
- `is_logged_in()` token-expiry check no longer inverted; stale access tokens are detected correctly (ARC-003 / SEC-007).
- OAuth callback handler returns a generic `Authentication failed` message instead of leaking raw exception text to anyone reaching the loopback listener (SEC-003).
- Removed `type: ignore[reportAttributeAccessIssue]` silencers in `data_structures.py` by giving the auth client a concrete return type (QA-005).
- `compute_board_center` no longer divides by zero when no subgrids exist (QA-010).
- Replaced `assert` runtime validation with explicit raises (QA-007), fixed the copy-paste "Par LLAMA TUI dialogs package." docstring (QA-009), resolved `# noqa: F821` root causes (QA-011), and aligned pre-commit's Python with 3.13 (QA-012).
- Removed the committed editor backup `pyproject.toml~` and gitignored `*~` (QA-006).

### Documentation

- Documented the `A` key (the only way to open the Authentication / Internet Leaderboard dialog) in both README and in-app help (DOC-001).
- Corrected the documented nickname/username length limit from 30 to 20 and documented the allowed charset (DOC-002).
- Fixed the OAuth provider list to "Google, Facebook, or GitHub" in README and in-app help (DOC-005).
- Added a Web Server Mode subsection to README with the listen URL/port and the OAuth callback port collision note (DOC-006).
- Mirrored the Storage section and the "post score before new game" warning into in-app help (DOC-011).
- Added a CI build-status badge, fixed the "x86-63" badge alt-text typo, fixed a duplicate Scoring sentence, added CLI usage examples, and made the roadmap concrete (DOC-012, DOC-013, DOC-014, DOC-015, DOC-016).
- Corrected `.aider.conventions.md` Python version from 3.12 to 3.13 (DOC-017).

## [0.3.8] - 2026

### Changed

- Updated dependencies.
- Ensured Python 3.13 compatibility.
- Updated build and CI/CD configuration to use Python 3.13 as default.

## [0.3.7]

### Changed

- Fixed GitHub Actions workflows for correct project references.
- Added Python version matrix testing (3.11, 3.12, 3.13).
- Updated build configuration to target Python 3.12.
- Improved Makefile with test and clean-all targets.
- Fixed duplicate dependencies in pyproject.toml.

## [0.3.6]

### Changed

- Removed unused dependencies.
- Updated dependencies.
- Tested on Python 3.13.

## [0.3.5]

### Changed

- Updated dependencies.
- Minor bug fixes.

## [0.3.4]

### Changed

- Removed some unnecessary dependencies.
- Minor bug fixes.

## [0.3.3]

### Added

- Subgrids now have a subtle checker background.
- Added `S` key to toggle subgrid highlighting.

### Fixed

- Bug where hitting a mine on the 1st click after reloading a saved game did not end the game.

## [0.3.2]

### Fixed

- Ensured the 1st click is always safe.

## [0.3.1]

### Changed

- Use XDG specification for data paths.

## [0.3.0]

### Added

- Internet leaderboard.
- `a` key to access the authentication dialog for the internet leaderboard.

### Changed

- Server mode now honors other parameters such as `--user` and `--nick`.
- Username and nickname are now limited to 20 characters (the previous README's "30 characters" was incorrect).

### Fixed

- Help dialog content display issues.

## [0.2.10]

### Changed

- Updated package metadata.
- Removed some unnecessary dependencies.

## [0.2.9]

### Fixed

- First-run database issues.

## [0.2.8]

### Added

- Added a game data backup.

### Changed

- Updated README and help.

## [0.2.7]

### Added

- Pause key `p`.
- Support for future game modes.

### Fixed

- Bug where sometimes newly generated sub grids would not get saved if no cells were uncovered.

### Changed

- More optimizations.

## [0.2.6]

### Changed

- Stops the timer on game over.
- Highlights surrounding cells when shift/ctrl + left-click on uncovered cells (later refined in 0.2.6+ to highlight only unrevealed surrounding cells).

## [0.2.5]

### Changed

- Disabled some toasts to reduce clutter.
- Moved the middle-click function to shift/ctrl + left-click on uncovered cells.

## [0.2.3]

### Added

- Multi-user support.

## [0.2.0]

### Added

- Webserver to play the game in a browser.

## [0.1.0]

- Initial release.
