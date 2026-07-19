# Troubleshooting: Par Infinite Minesweeper

This guide covers the most common failure modes for `pim`: the OAuth callback listener, the `--server` web mode, nickname validation, and a few setup pitfalls. If you are reporting a bug, please skim the matching entry first — it often contains the fix or the information needed to file a useful issue.

## Table of Contents

- [Login / OAuth](#login--oauth)
- [Web Server Mode (`--server`)](#web-server-mode---server)
- [Nicknames and Usernames](#nicknames-and-usernames)
- [Saves and Data](#saves-and-data)
- [Installation / Environment](#installation--environment)
- [Reporting Bugs](#reporting-bugs)

## Login / OAuth

### Symptom: OS prompt to allow incoming connections on port 1999

**Impact:** On first login (macOS, sometimes Windows Firewall), the OS asks whether to allow `pim` / Python to accept incoming network connections on port 1999.

**Cause:** This is expected and required. The OAuth2 flow listens on `http://127.0.0.1:1999/oauth/callback` for the Auth0 redirect that delivers the authorization code. The listener is bound to loopback only — it is not reachable from other machines — but the OS still prompts because it is an inbound socket.

**Fix:** Click **Allow** (macOS) or **Allow access** (Windows Firewall). Login will then complete in the browser.

If you clicked **Deny**, login will hang with the browser never returning to the app. Quit the app (`Q` or close the terminal), allow Python through the firewall (System Settings → Network → Firewall on macOS, or Windows Defender Firewall settings), and try again.

**Verify:** After clicking Allow, the browser shows "Logged in. You may close this window." and the app shows you as logged in.

### Symptom: "Could not start the OAuth callback listener on port 1999"

**Impact:** Login fails with an `AuthServerError` notification: the listener could not bind.

**Likely causes:**

- Another `pim` process is already mid-login (the loopback socket is held by the OS for that process).
- A previous `pim` process crashed during login and left the socket in `TIME_WAIT`.

**Diagnosis:** Check what is listening on the port:

```bash
lsof -nP -iTCP:1999 -sTCP:LISTEN
```

**Fix:**

- If the holder is another live `pim`, complete or cancel that login first.
- If the holder is a zombie Python process, kill it: `kill <pid>` from the `lsof` output.
- The codebase already sets `SO_REUSEADDR` on the listener, so a socket in `TIME_WAIT` will not block the next launch — but a still-listening process will. Wait it out or kill the process.

Then retry login.

**Verify:** `lsof -nP -iTCP:1999 -sTCP:LISTEN` shows the new `pim` PID after you press `A` → login.

### Symptom: Browser did not open on the Auth0 login page

**Impact:** After pressing `A` and choosing to log in, no browser tab appears.

**Cause:** The host has no default browser configured, or the browser failed to launch.

**Fix:** The app posts a `ShowURL` message with the authorization URL. Copy the URL it displays and paste it into a browser manually. Login then proceeds normally.

### Symptom: Login screen mentions only Google or Facebook

**Impact:** The docs and dialog text are out of date — GitHub is also supported.

**Fix:** Choose **Login** and you will see Google, Facebook, and GitHub on the Auth0 hosted page. This is a documentation lag; see `docs/ARCHITECTURE.md` for the current provider list.

## Web Server Mode (`--server`)

### Symptom: Started `pim --server` and the game is accessible from another machine

**Impact:** Anyone who can reach your machine on its local network (or via port forwarding, NAT, or a browser extension proxying the same origin) can view and control the game.

**Cause:** `--server` launches the app under `textual-serve`, which serves the TUI as an HTTP page. The server binds to localhost by default, but anything that can reach your localhost (other local users on shared machines, SSH-tunneled peers, malicious browser extensions on the served origin) can drive it.

**Fix:** Treat `--server` as a single-user, single-machine convenience feature. Do not run it on a shared or untrusted host, and do not expose the served port to the internet (no port forwarding, no Cloudflare Tunnel, no `ngrok`). On startup the CLI prints a warning to this effect.

If you need to play `pim` remotely, run it as a normal TUI inside an SSH session instead.

**Verify:** With `pim --server` running, `lsof -nP -iTCP | grep LISTEN` should show the textual-serve port bound to `127.0.0.1` (localhost only), not `0.0.0.0` (all interfaces).

## Nicknames and Usernames

### Symptom: `pim --nick <name>` fails with "Nickname must be 20 characters or less"

**Impact:** The CLI exits before the app starts.

**Cause:** Nickname length is capped at 20 characters. Older release notes mentioned 30, but the canonical limit enforced by `validate_nickname` (in `models.py`) is 20.

**Fix:** Choose a nickname of 2–20 characters.

### Symptom: "Nickname must be at least 2 characters"

**Cause:** Nicknames must be 2 characters or longer.

**Fix:** Use a longer nickname.

### Symptom: "Nickname may only contain letters, numbers, and . - _"

**Cause:** The nickname charset is restricted to ASCII letters, digits, dot (`.`), dash (`-`), and underscore (`_`). Spaces, emoji, and other punctuation are rejected to prevent display spoofing and stored-XSS in clients that render the leaderboard without escaping.

**Fix:** Use only the allowed characters. The restriction applies at CLI parse, at the login dialog, and at the leaderboard nickname-change endpoint.

### Symptom: `pim --user <name>` fails with "User name must be 20 characters or less"

**Impact:** The CLI exits before the app starts.

**Cause:** Username length is capped at 20 characters (the `--user` / `-u` flag is the local profile name, not the OAuth identity).

**Fix:** Choose a username of 20 characters or fewer.

### Symptom: Nickname migration warning at startup ("truncating N nickname(s) to the 20-char limit")

**Impact:** A stderr warning prints on startup; the app then starts normally.

**Cause:** A pre-existing `users` row has a `nickname` longer than 20 characters (from an older release where 30 was the implicit limit). On startup `init_db` truncates such rows to 20 so the validator stops rejecting them, and prints this one-time warning for visibility.

**Fix:** No action required — the warning is informational. If you want a different nickname, use `pim --nick <new>` to set one.

## Saves and Data

### Symptom: Save file location after upgrade from ≤0.2.x

**Impact:** After upgrading, the save file appears to have moved.

**Cause:** Since 0.3.1 the app uses the XDG Base Directory specification (`xdg_data_home() / "pim" / "game_data.sqlite"`). The first launch on the new version renames the legacy `~/.pim/` folder to the XDG path automatically.

**Verify:**

```bash
ls -la "$(python3 -c 'from xdg_base_dirs import xdg_data_home; print(xdg_data_home() / "pim")')"
```

Typical paths:

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/pim/game_data.sqlite` |
| Linux | `~/.local/share/pim/game_data.sqlite` |
| Windows | `%LOCALAPPDATA%\pim\game_data.sqlite` |

### Symptom: Highscores dialog shows the same old scores and never updates

**Status:** Fixed in 0.3.9 (audit ARC-002). The local highscores query was returning the 10 **oldest** scores instead of the 10 **highest**; the fix is `ORDER BY score DESC, created_ts DESC LIMIT 10`. If you are running an older version, upgrade.

### Symptom: Game state did not save before quit

**Impact:** A few moves are missing on next launch.

**Cause:** `pim` saves on every cell click (dirty-flag incremental save), but the last in-flight click during a fast quit can occasionally miss its write.

**Fix:** Wait one second between your last move and quitting. If progress is consistently lost across sessions, file an issue with the contents of `~/Library/Application Support/pim/game_data.sqlite.bak` (do not share the main DB file — it contains OAuth tokens).

## Installation / Environment

### Symptom: `make: command not found` on Windows

**Fix:** Install Make (`winget install GnuWin32.Make`) or run the underlying `uv` commands directly. Each Make target is a thin wrapper — see the `Makefile` for the exact command.

### Symptom: `uv: command not found`

**Fix:** Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then re-run `make setup`.

### Symptom: Pyright or ruff report errors on freshly cloned code

**Fix:** Ensure you ran `make setup` (which runs `uv sync` and installs all dev dependencies including `pyright`, `ruff`, `pytest`, `textual-dev`). If still failing, run `make resetup` to rebuild the venv from scratch.

### Symptom: `make checkall` passes locally but CI fails (or vice versa)

**Cause:** Local `make checkall` is CI-safe (`format-check` / `lint-check` do not mutate files). If you instead ran `make format` or `make lint` locally, your tree was rewritten in-place and the committed version differs from the validated version. CI's `format-check` then fails.

**Fix:** Commit the reformatted files (`make format && make lint && git add -u && git commit`).

### Symptom: `AUTH0_CLIENT_ID not set` warning on every launch

**Impact:** A stderr warning fires once per launch: you are hitting the production Auth0 tenant.

**Cause:** The hardcoded default client ID points at production. Local development should override it.

**Fix:** Set `AUTH0_CLIENT_ID` (and optionally `AUTH0_DOMAIN`) in your environment or `.env` file to point at a test tenant. The warning is idempotent per process and only routes to stderr — it does not affect the TUI.

## Reporting Bugs

If none of the above matches:

1. Reproduce with the latest version (`uv tool install --upgrade par_infini_sweeper` or `uv sync -U` from a checkout).
2. Run `pim --version` and record the version.
3. Note the OS, Python version, and terminal.
4. Capture any stderr output — the app routes diagnostic warnings there, separate from the TUI.
5. Open an issue at <https://github.com/paulrobello/par_infini_sweeper/issues> with the reproduction steps.

> **Security:** If you found something that compromises user data, OAuth tokens, or the leaderboard, do not open a public issue. See [SECURITY.md](../SECURITY.md) for the private disclosure process.
