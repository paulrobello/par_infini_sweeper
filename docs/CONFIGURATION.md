# Configuration

Reference for the environment variables read by Par Infinite Minesweeper, the `.env` file mechanism, and where user data is stored on disk.

## Table of Contents

- [Quick Reference](#quick-reference)
- [Loading Order](#loading-order)
- [Environment Variables](#environment-variables)
- [The .env File](#the-env-file)
- [On-Disk Storage](#on-disk-storage)
- [Related Documentation](#related-documentation)

## Quick Reference

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `USER` | No | `"user"` | Default username when `--user` is not passed. Read from the OS environment. |
| `PIM_LEADERBOARD_URL` | No | `https://pim.pardev.net` | Base URL of the internet leaderboard API. |
| `AUTH0_DOMAIN` | No | `par-dev.us.auth0.com` | Auth0 tenant used for the OAuth2 login flow. |
| `AUTH0_CLIENT_ID` | No | Production client ID (hardcoded) | Auth0 client ID. If unset, a one-time stderr warning fires (see below). |

## Loading Order

`pim` reads environment variables in this order; later wins:

1. The process environment inherited from the shell (or launcher).
2. A local `.env` file in the current working directory, loaded by `python-dotenv` (`__main__.py` calls `load_dotenv()` before the rest of the package imports fire). `python-dotenv` does **not** overwrite variables that are already set in the environment.

CLI flags override environment-derived defaults:

- `--user` / `-u` overrides the `USER`-derived default username.
- `--nick` / `-n` is validated against the same rules as the in-app nickname dialog (2–20 chars, `[A-Za-z0-9._-]`).

## Environment Variables

### `USER`

- **Default:** `"user"`
- **Required:** No
- **Read by:** `__main__.py` (CLI default for `--user`) and `pim_app.py` (fallback when no username is passed to `PimApp`).
- **Purpose:** Selects which row in the local `users` table the game loads — each username gets its own save slot, preferences, and local high scores. Override with `--user` to keep multiple profiles on one machine.
- **Example:**

  ```shell
  USER=alice pim
  ```

### `PIM_LEADERBOARD_URL`

- **Default:** `https://pim.pardev.net`
- **Required:** No
- **Read by:** `db.get_internet_highscores`, `persistence.leaderboard.post_internet_score`, `persistence.leaderboard.change_internet_nickname`.
- **Purpose:** Base URL for the internet leaderboard HTTP API. The game appends `/score` or `/nickname` to this value. Set it to point at a test/staging leaderboard during development.
- **Example:**

  ```shell
  PIM_LEADERBOARD_URL=http://localhost:1988 pim
  ```

### `AUTH0_DOMAIN`

- **Default:** `par-dev.us.auth0.com`
- **Required:** No
- **Read by:** `auth.py` at module load (the OAuth2 authorize/token/refresh URLs are built from it).
- **Purpose:** Auth0 tenant hostname. Override to point login at a sandbox tenant instead of production. Must match the tenant that issued `AUTH0_CLIENT_ID`.
- **Example:**

  ```shell
  AUTH0_DOMAIN=your-tenant.us.auth0.com pim
  ```

### `AUTH0_CLIENT_ID`

- **Default:** Production Auth0 client ID (hardcoded in `auth.py`).
- **Required:** No
- **Read by:** `auth.py` at module load; `warn_if_default_auth0_client_id()` (called from `__main__.main`).
- **Purpose:** Auth0 client ID identifying this native/desktop OAuth2 client. If unset, the game falls back to the production client ID and prints a one-time stderr warning so developers know their local login is hitting the production auth tenant.
- **Example:**

  ```shell
  AUTH0_CLIENT_ID=your-local-client-id pim
  ```

- **Warning when unset** (printed once to stderr):

  ```text
  warning: AUTH0_CLIENT_ID not set; using the production Auth0 tenant
  (par-dev.us.auth0.com). Set AUTH0_CLIENT_ID (and AUTH0_DOMAIN) for local dev.
  ```

## The .env File

`pim` loads variables from a `.env` file in the current working directory using `python-dotenv`. This is convenient for local development — keep your dev overrides there and `pim` will pick them up automatically.

```ini
# Example .env for local leaderboard development
PIM_LEADERBOARD_URL=http://localhost:1988
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-local-client-id
```

> **Security:** `.env` is gitignored and is **not** packaged into the built wheel. Never commit real credentials to it. The repository's `.env` ships only a commented-out `PIM_LEADERBOARD_URL` example.

## On-Disk Storage

Game data lives under the XDG data directory:

- **Linux:** `~/.local/share/pim/`
- **macOS:** `~/Library/Application Support/pim/`
- **Windows:** `%LOCALAPPDATA%\pim\`

Files written there:

| File | Purpose |
| --- | --- |
| `game_data.sqlite` | Live database: users, preferences, games, high scores, subgrid state, OAuth tokens. Mode `0600`. |
| `game_data.sqlite.bak` | Rolling backup, refreshed when the live DB is more than a day newer. Mode `0600`. |

The data folder is created with mode `0700`. A legacy `~/.pim/` directory from older releases is moved to the XDG location on first run. The OAuth `access_token`, `refresh_token`, and `id_token` columns live inside the SQLite database; restricting file permissions is the current protection, and a follow-up roadmap item is to move `refresh_token` to the OS keychain.

## Related Documentation

- [README.md](../README.md) — install, controls, scoring, internet leaderboard overview.
- [CHANGELOG.md](../CHANGELOG.md) — version history.
