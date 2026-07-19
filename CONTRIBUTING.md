# Contributing to Par Infinite Minesweeper

Thanks for your interest in contributing. This guide covers the development setup, the inner loop, and the conventions the project follows. The project is a Python 3.13 Textual TUI, packaged with `uv` + `hatchling`, and verified with `ruff` + `pyright` + `pytest`.

## Table of Contents

- [Prerequisites](#prerequisites)
- [First-Time Setup](#first-time-setup)
- [The Inner Loop](#the-inner-loop)
- [Running the App](#running-the-app)
- [Tests](#tests)
- [Pre-Commit](#pre-commit)
- [Project Conventions](#project-conventions)
- [Commit Messages](#commit-messages)
- [Pull Requests](#pull-requests)
- [Need Help](#need-help)

## Prerequisites

- **Python 3.13** (the project targets `>=3.11` but CI and pre-commit run on 3.13).
- **[uv](https://docs.astral.sh/uv/)** for environment and dependency management. Install with `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux) or `winget install astral-sh.uv` (Windows).
- **GNU Make**. On macOS it ships with Xcode Command Line Tools; on Windows use `winget install GnuWin32.Make` or run targets through WSL.
- **Git** with your `user.name` and `user.email` configured.

## First-Time Setup

Clone the repository and bootstrap the environment:

```bash
git clone https://github.com/paulrobello/par_infini_sweeper.git
cd par_infini_sweeper
make setup
```

`make setup` runs `uv lock` followed by `uv sync`, which creates a `.venv/` with all runtime and dev dependencies pinned in `uv.lock`. If anything goes wrong, `make resetup` deletes `.venv/` and re-creates it from scratch.

Install the git hooks so lint, format, typecheck, and secret scanning run on every commit:

```bash
make pre-commit
uv run pre-commit install
```

`make pre-commit` runs all hooks once across the repo (`pre-commit run --all-files`). `pre-commit install` wires them into `git commit` so future commits are gated.

To update hooks to their latest versions later:

```bash
make pre-commit-update
```

## The Inner Loop

The CI-safe gate is `make checkall`. It runs four read-only checks against the committed tree — it does **not** mutate files:

```bash
make checkall
```

This runs:

1. `make format-check` — `ruff format --check` (fails if files are not formatted).
2. `make lint-check` — `ruff check` (fails on lint errors).
3. `make typecheck` — `pyright` (fails on type errors).
4. `make test` — `pytest`.

Before pushing, run `make checkall` and ensure it is green. CI runs the same command, so a green local gate means a green CI build.

When you want to **fix** formatting and lint issues in-place (local use only — these mutate files):

```bash
make format
make lint
```

Never run `make format` or `make lint` inside CI: they rewrite the tree before typecheck runs and hide real failures. CI uses `format-check` and `lint-check` for this reason.

## Running the App

```bash
make run        # uv run pim — the installed entry point
make dev        # uv run textual run --dev -c pim — Textual dev mode with live reload
```

`make dev` runs the app under `textual run --dev`, which enables Textual's devtools and reloads on file changes.

## Tests

Tests live in `tests/` and use `pytest` with `pytest-asyncio`:

```bash
make test
```

Run a single test file or test:

```bash
uv run pytest tests/test_db.py
uv run pytest tests/test_game.py::test_subgrid_round_trip
```

Add regression tests for any bug fix. The existing tests cover `SubGrid` round-trips, `GameState` serialization, the database layer, and the Phase 2 critical bug fixes (`get_user` `None` guard, highscores `DESC` ordering, first-click flood-fill safety, `is_logged_in` expiry). When fixing a gameplay bug, write the test that would have caught it.

## Pre-Commit

The repo's `.pre-commit-config.yaml` wires these hooks into every commit:

- **gitleaks** + **detect-private-key** — block committed secrets.
- **pre-commit-hooks** — `end-of-file-fixer`, `trailing-whitespace`, `check-toml`, `check-yaml`, `check-json`, `check-merge-conflict`, `check-docstring-first`.
- **Local hooks** — `make typecheck`, `make format`, `make lint`.

Run all hooks on demand:

```bash
make pre-commit
```

If a hook modifies a file, stage the changes and re-commit. Hooks target Python 3.13 (set in `default_language_version`).

## Project Conventions

- **Python 3.13** — use the modern syntax it enables (`type` statements, `X | Y` unions, `from __future__ import annotations` is already pervasive).
- **Line length 120** — enforced by `ruff.toml`.
- **Formatter**: `ruff format`.
- **Linter**: `ruff check`.
- **Type checker**: `pyright` in strict mode against `src/`. The project ships `py.typed` and is classified `Typing :: Typed` on PyPI — keep the public surface fully typed and avoid `# type: ignore` suppressions.
- **Docstrings**: Google style with `Args:` / `Returns:` / `Raises:` sections. See the existing docstrings on `game/state.py` methods (`reveal_cell`, `is_logged_in`, `compute_board_center`) for the established pattern.
- **SQL**: always parameterized. The codebase uses `?` placeholders throughout `db.py`, `db_migrations.py`, and `persistence.py` — never f-strings or `%` formatting for SQL.
- **Architecture**: the model lives in `src/par_infini_sweeper/game/` (`cells.py`, `subgrid.py`, `state.py`, `types.py`). Cross-cutting concerns are split into `persistence.py` (SQLite), `leaderboard.py` (OAuth/HTTP), and `renderer.py` (Rich markup). See `docs/ARCHITECTURE.md` for the full picture.
- **Exceptions**: catch specific exceptions (`requests.RequestException`, `jose.JWTError`, `sqlite3.Error`, `authlib.oauth2.OAuth2Error`) — not bare `except Exception`. Log via `logging.exception(...)` before deciding to swallow.
- **No import-time side effects**: do not perform filesystem mutation, network calls, or `os.environ` writes at module top level. Use `init_storage()` or `__main__.main()` instead. See `db.init_storage` and `__main__.main` for the pattern.

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>
```

Common `type` values: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`, `security`. Scope is optional but encouraged (e.g. `auth`, `db`, `game`, `leaderboard`).

Examples from this repo's history:

```text
fix(correctness): guard get_user None, highscores DESC, first_click ordering, is_logged_in expiry + pytest harness
refactor(architecture): decompose 881-LOC god module into game/ + persistence/leaderboard/renderer
docs: add comprehensive project audit (AUDIT.md)
```

Keep the subject line under 72 characters, imperative mood (`add`, `fix`, `remove` — not `added`, `fixes`). Reference the audit issue ID (e.g. `ARC-004`, `SEC-001`) in the body when the change resolves one.

## Pull Requests

1. **Branch from `main`** (or use a git worktree for non-trivial work — `git worktree add ../pim-feature -b feat/your-feature`).
2. **One concern per PR** — keep the diff focused so review is fast and revert is clean.
3. **Rebase onto the latest `main`** before opening: `git fetch && git rebase origin/main`.
4. **Run `make checkall` locally** — it must be green before you push. CI runs the same command.
5. **Open the PR against `main`** with:
   - A clear title in Conventional Commits form.
   - A description that says **what changed** and **why**, and links any audit IDs resolved.
   - For gameplay or auth changes, note how the change was tested (new tests added, manual verification steps).
6. **Respond to review feedback** with further commits; do not force-push mid-review unless asked.

PRs that touch public APIs, persistence schema, or auth flow will get a closer review — explain the tradeoffs in the description.

## Need Help

- Bugs and feature requests: [open a GitHub issue](https://github.com/paulrobello/par_infini_sweeper/issues).
- Architecture questions: see `docs/ARCHITECTURE.md` first.
- Troubleshooting: see `docs/TROUBLESHOOTING.md`.
- Discussions: [GitHub Discussions](https://github.com/paulrobello/par_infini_sweeper/discussions).

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE), and that you will follow the [Code of Conduct](CODE_OF_CONDUCT.md).
