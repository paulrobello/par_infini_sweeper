# Security Policy

Par Infinite Minesweeper (`par_infini_sweeper`, command `pim`) is a local-first Textual TUI game. This document describes what the application does and does not handle, how OAuth tokens are stored, the scope of the `--server` mode, and how to report a vulnerability.

## Table of Contents

- [Scope](#scope)
- [What the Application Touches](#what-the-application-touches)
- [OAuth Token Storage Model](#oauth-token-storage-model)
- [Web Server Mode (`--server`)](#web-server-mode---server)
- [Supported Versions](#supported-versions)
- [Reporting a Vulnerability](#reporting-a-vulnerability)
- [Disclosure Policy](#disclosure-policy)
- [Related Documentation](#related-documentation)

## Scope

`pim` is a single-user desktop application:

- It runs locally on your machine and reads/writes data under your XDG data directory (`xdg_data_home() / "pim"`).
- It does not run as a server, daemon, or network service in normal use.
- It does not listen on any port in normal TUI play.
- The only outbound network calls are to the OAuth/Auth0 tenant (login, token refresh) and to the leaderboard API (score submission, nickname change, leaderboard fetch).

Out of scope: server-side leaderboard code, the Auth0 tenant configuration, and anything outside this repository. Those are operated by the project maintainer and have their own security posture.

## What the Application Touches

| Resource | Where | Notes |
|---|---|---|
| Game save data | `xdg_data_home() / "pim" / "game_data.sqlite"` | SQLite. Contains subgrids, highscores, preferences, OAuth tokens. |
| DB backup | `…/game_data.sqlite.bak` | Refreshed once per launch via `ensure_backup()` if older than 1 day. |
| OAuth tokens | Columns on the `users` table in the same SQLite DB | `id_token`, `access_token`, `refresh_token`, `expires_at`. |
| Configuration | `.env` in the working directory (if present) | Read via `python-dotenv` at startup; only `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `PIM_LEADERBOARD_URL`, `USER` are consulted. |

The application does **not** read, write, or transmit anything else: no keychain, no cloud sync, no telemetry, no crash reporting.

## OAuth Token Storage Model

On login, `pim` stores the Auth0-issued `id_token`, `access_token`, and `refresh_token` as columns on the `users` row in `game_data.sqlite`. These tokens authorize leaderboard calls and let the app transparently refresh the access token via the long-lived `refresh_token` (the `offline_access` OAuth scope).

Hardening in place:

- The SQLite database file is `chmod 0o600` (owner read/write only) on every connection.
- The containing folder is `chmod 0o700`.
- The backup file is `chmod 0o600`.
- The OAuth2 Authorization Code flow uses **PKCE** (RFC 7636): a `code_verifier` is generated per login, used to derive the `code_challenge` sent with `create_authorization_url`, and redeemed at `fetch_token`. This prevents authorization-code interception on public clients.
- The OAuth loopback callback on `127.0.0.1:1999` validates the callback path exactly (`/oauth/callback`) and does not reflect the request's `Host` header into `authorization_response`, preventing authority injection from a forged Host header.
- Error responses from the loopback callback return only `"Authentication failed"` — raw exception text is logged locally, never echoed to the HTTP body.

Known limitation (tracked as a TODO in `db.py`): the `refresh_token` is a long-lived credential stored in SQLite rather than in the OS keychain. The file-mode hardening above is a stopgap. A future change will move the `refresh_token` to the OS keychain via the `keyring` library. On a single-user machine this is mostly defense-in-depth; on a shared multi-user host it is meaningful.

To clear stored tokens (sign out completely):

- In the app: use the authentication dialog's logout option.
- From disk: stop `pim`, then in a Python REPL with `sqlite3` set `access_token = ''`, `refresh_token = ''`, `id_token = ''`, `expires_at = 0` on the relevant `users` row. The tokens are then also invalid — to revoke them at the Auth0 tenant, log out from the social provider's account page.

## Web Server Mode (`--server`)

`pim --server` / `pim -s` runs the TUI under `textual-serve`, serving it as an HTTP page so it can be played in a browser. This mode is for **single-user, single-machine convenience** and has no authentication, no rate limiting, and no encryption.

- The textual-serve server binds to localhost.
- Anything that can reach your localhost can view and control the running game. This includes other local users on shared machines, peers on the same NAT network if your host forwards the port, SSH-tunneled clients, and browser extensions proxying the served origin.
- The CLI prints a warning to stderr at startup to make this explicit.

Do not run `--server` on a shared or untrusted host, expose its port to the internet (port forwarding, tunnel, reverse proxy), or run it while logged into the OAuth leaderboard with credentials you would not share.

For remote play, run `pim` as a normal TUI over an SSH session instead — that authenticates via SSH and does not expose an unauthenticated HTTP surface.

## Supported Versions

Only the latest released version of `pim` receives security fixes. If you are running an older version, upgrade before reporting.

| Version | Supported |
|---|---|
| Latest PyPI release (`pip install --upgrade par_infini_sweeper`) | Yes |
| `main` branch HEAD | Best-effort (may be ahead of the released version) |
| Anything older | No — upgrade first |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security reports.**

Instead, report privately using one of these channels, in order of preference:

1. **GitHub Security Advisories** (preferred): go to <https://github.com/paulrobello/par_infini_sweeper/security/advisories/new> and click "Report a vulnerability". This uses GitHub's private vulnerability reporting and lets the maintainer coordinate a fix and CVE before public disclosure.
2. **Email**: send details to `probello@gmail.com` with the subject line `[SECURITY] par_infini_sweeper`. If your report contains sensitive tokens or exploit details, encrypt to the maintainer's key if one is published on their GitHub profile.

Please include in your report:

- The `pim` version (`pim --version`) and how you installed it (`pip`, `uv`, `uv tool`, from source).
- The OS and Python version.
- A minimal reproduction (commands, inputs, or a script).
- The impact: what an attacker could do, what data is exposed, what privilege is required (local user, network position, OAuth state).
- Suggested fix if you have one.

You will receive an acknowledgement within 5 business days. If the report is accepted, the maintainer will coordinate a disclosure timeline with you (default: 90 days from acknowledgement, or after a fixed release is published, whichever is sooner).

## Disclosure Policy

- Reports are kept private until a fix is available.
- Once a fix is released, a GitHub Security Advisory is published with credit to the reporter (unless they prefer to remain anonymous).
- The `CHANGELOG.md` entry for the fixing release notes the security impact.

## Related Documentation

- [Architecture: OAuth2 / Auth0 Flow](ARCHITECTURE.md#oauth2--auth0-flow) — flow diagram and design points.
- [Troubleshooting: Login / OAuth](TROUBLESHOOTING.md#login--oauth) — port 1999 prompts and listener failures.
- [Troubleshooting: Web Server Mode](TROUBLESHOOTING.md#web-server-mode---server) — `--server` exposure details.
- [Code of Conduct](CODE_OF_CONDUCT.md) — community standards.
