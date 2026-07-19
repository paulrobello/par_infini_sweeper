# Par Infinite Minesweeper

[![PyPI](https://img.shields.io/pypi/v/par_infini_sweeper)](https://pypi.org/project/par_infini_sweeper/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/par_infini_sweeper.svg)](https://pypi.org/project/par_infini_sweeper/)
[![Build and Test](https://github.com/paulrobello/par_infini_sweeper/actions/workflows/build.yml/badge.svg)](https://github.com/paulrobello/par_infini_sweeper/actions/workflows/build.yml)
![Runs on Linux | MacOS | Windows](https://img.shields.io/badge/runs%20on-Linux%20%7C%20MacOS%20%7C%20Windows-blue)
![Arch x86-64 | ARM | AppleSilicon](https://img.shields.io/badge/arch-x86--64%20%7C%20ARM%20%7C%20AppleSilicon-blue)
![PyPI - Downloads](https://img.shields.io/pypi/dm/par_infini_sweeper)



![PyPI - License](https://img.shields.io/pypi/l/par_infini_sweeper)

## Description

Infinite Minesweeper TUI. Play a game of minesweeper with infinite board size!

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/probello3)

## Screenshots

![Par Infinite Minesweeper](https://raw.githubusercontent.com/paulrobello/par_infini_sweeper/main/Screenshot.png)

## Technology

- Python
- Textual
- Sqlite3
- OAuth2 (For Internet Leaderboard)

## Key Features:

* Infinite board size
* Local high scores
* Internet high scores
* Auto saves and can be resumed

## Objective

The goal of the game is to uncover all the cells that do not contain mines.
If you uncover a mine, you lose the game. Your 1st click is always safe.
If you uncover a cell that is not a mine, it will show a number indicating how many mines are in the neighboring cells.
Use this information to determine which cells are safe to uncover.

## Controls

* Left click to uncover a cell. If a cell is flagged as a mine, it will not be uncovered.
* Sub grids can only be unlocked when cells neighboring the sub grid are uncovered.
* Press **F** (or Right-click / Shift/Ctrl + Left-click) to toggle flagging a covered cell as a mine.
* Right-click (or Shift/Ctrl + Left-click) on an uncovered cell to uncover all neighboring cells.
  * As a safety you must have same number of flags as mines in the neighboring cells.
* Drag to pan the board.
* Keys:
  * `F1` Help.
  * `N` New game.
  * `O` Move view to origin.
  * `C` Move view to board center (computed as center of exposed sub grids).
  * `P` Pause.
  * `S` Toggle highlighting of sub grid under the mouse
  * `H` Highscores.
  * `T` Change theme.
  * `A` Authentication / Internet Leaderboard (login, register nickname, upload score).
  * `Q` Quit.

## Scoring

The main grid consists of 8x8 sub grids.
Depending on the difficulty level, the number of mines in each sub grid will vary.
* Easy: 8 mines
* Medium: 12 mines
* Hard: 16 mines

When every non-mine cell in a sub grid has been uncovered, the sub grid is marked solved (it turns a darker gray) and flags are automatically placed on any mines in it that are not already flagged.
Your score is the sum of all mines in the solved sub grids.

## Storage

All data for the application is stored in a sqlite3 database located in $XDG_DATA_HOME/pim or appropriate folder for your OS  
The database is backed up each day you play to `game_data.sqlite.bak`  

## Internet Leaderboard

To use the internet leaderboard you must login to the server via a social provider such as Google, Facebook, or GitHub.
This requires 2 things:
1. The game must listen on port 1999 for the authentication callback. (This may trigger a firewall warning which you must accept if you wish to continue)
2. The game must launch a browser so you can login.
- Only your hashed email is stored on the server.
- The port will only be opened for the duration of the login process.
- After you have logged in and reserved your nickname, you can then submit your scores to the server for the current game mode and difficulty.
- Nicknames and usernames are limited to 20 characters and may only contain the chars `a-z` `A-Z` `0-9` and `.` `-` `_`.
- Only one score per user / game mode / difficulty is stored.
- You may submit scores for games that have not yet ended. If the score is higher than your existing one it will replace it.
- Scores are not posted to the internet automatically, so make sure you post your score before starting a new game!

See our [privacy policy](https://par-com.net/privacy_policy.html) for details on data handling.

## Prerequisites

- Python 3.11 - 3.13 (3.13 recommended)
- The instructions assume you have `uv` installed.

## Installation

### PyPi
```shell
uv tool install par_infini_sweeper
```

### GitHub
```shell
uv tool install git+https://github.com/paulrobello/par_infini_sweeper
```

## Update

### PyPi
```shell
uv tool install par_infini_sweeper -U --force
```

### GitHub
```shell
uv tool install git+https://github.com/paulrobello/par_infini_sweeper -U --force
```


## Installed Usage
```shell
pim [OPTIONS]
```

## From source Usage
```shell
uv run pim [OPTIONS]
```

### CLI Options
```
--server              -s            Start webserver that allows app to be played in a browser
--user                -u      TEXT  User name to use [default: logged in username]; max 20 chars
--nick                -n      TEXT  Set user nickname [default: None]; 2-20 chars, chars a-z A-Z 0-9 . - _
--version             -v            Show version and exit.
--help                              Show this message and exit.
```

### CLI Examples

```shell
# Default: launch the TUI for the current OS user
pim

# Play under a specific user name (selects its own save slot and high scores)
pim --user alice

# Set your leaderboard nickname up front (validates the same way as the in-app dialog)
pim --nick alice_92

# Serve the game over HTTP so it can be played in a browser (see Web Server Mode)
pim --server

# Combine: serve the game, pre-selecting the user and nickname
pim --server --user alice --nick alice_92
```

### Web Server Mode

`pim --server` (or `pim -s`) wraps the TUI with [`textual-serve`](https://textual.textualize.io/webapp/) and serves it over HTTP. By default it listens on `http://localhost:8000` — open that URL in a browser to play. The server only binds to `localhost`, so it is reachable from the same machine only (see the warning below).

```text
warning: --server mode serves the TUI via an unauthenticated web server
(localhost-only). Anyone who can reach this host can view and control the
game — do not expose it to untrusted networks.
```

> **Warning:** Internet-leaderboard login and `--server` mode both rely on loopback ports on the host running `pim`. Pressing `A` (Authentication) starts a temporary listener on port `1999` that Auth0 redirects back to as `http://127.0.0.1:1999/oauth/callback`. If another `pim` process is mid-login, or anything else is bound to port `1999`, the auth listener will fail with a port-in-use error. Because the callback targets the server's own loopback, leaderboard login only completes from the same machine running `pim` — a remote browser client reaching the game through `--server` cannot finish the OAuth flow.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the environment variables that control the leaderboard URL, Auth0 tenant, and default user.

## Roadmap

- Additional game modes (the data model already supports a `GameMode` enum beyond `infinite`; the UI and score-posting paths need wiring up).
- Performance work for large revealed regions (the flood-fill currently runs as an iterative BFS with a depth cap; very large empty opens can still stall the frame).
- Move OAuth refresh tokens out of SQLite and into the OS keychain.

## Whats New

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Shoutout

I would like to thank [Edward Jazzhands](http://edward-jazzhands.github.io/) for all his help testing and feedback / feature requests!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Paul Robello - probello@gmail.com
