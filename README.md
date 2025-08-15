# Par Infinite Minesweeper

[![PyPI](https://img.shields.io/pypi/v/par_infini_sweeper)](https://pypi.org/project/par_infini_sweeper/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/par_infini_sweeper.svg)](https://pypi.org/project/par_infini_sweeper/)  
![Runs on Linux | MacOS | Windows](https://img.shields.io/badge/runs%20on-Linux%20%7C%20MacOS%20%7C%20Windows-blue)
![Arch x86-63 | ARM | AppleSilicon](https://img.shields.io/badge/arch-x86--64%20%7C%20ARM%20%7C%20AppleSilicon-blue)
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
* Shift or Ctrl + Left-click to toggle flagging a covered cell as a mine.
* Shift or Ctrl + Left-click on an uncovered cell it will uncover all neighboring cells.
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
  * `Q` Quit.

## Scoring

The main grid consists of 8x8 sub grids.  
When all cells that are not mines in a sub grid are uncovered the sub grid is marked solved turns a darker gray and flags are placed on any mines that are not already flagged.
* Easy: 8 mines
* Medium: 12 mines
* Hard: 16 mines

When all cells that are not mines in a sub grid are uncovered the sub grid is marked solved and flags are placed on any mines that are not already flagged.  
Your score is the sum of all mines in the solved sub grids.  

## Storage

All data for the application is stored in a sqlite3 database located in $XDG_DATA_HOME/pim or appropriate folder for your OS  
The database is backed up each day you play to `game_data.sqlite.bak`  

## Internet Leaderboard

To use the internet leaderboard you must login to the server via a social provider such as google or facebook.  
This requires 2 things:
1. The game must listen on port 1999 for the authentication callback. (This may trigger a firewall warning which you must accept if you wish to continue)
2. The game must launch a browser so you can login.
- Only your hashed email is stored on the server.
- The port will only be opened for the duration of the login process.
- After you have logged in and reserved your nickname, you can then submit your scores to the server for the current game mode and difficulty.
- Nicknames may only contain the chars a-z A-Z 0-9 and . - _
- Only one score per user / game mode / difficulty is stored.
- You may submit scores for games that have not yet ended. If the score is higher than your existing one it will replace it.
- Scores are not posted to the internet automatically, so make sure you post your score before starting a new game!

See our [privacy policy](https://par-com.net/privacy_policy.html) for details on data handling.

## Prerequisites

- Python 3.11 - 3.13 (3.12 recommended)
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
--user                -u      TEXT  User name to use [default: logged in username]
--nick                -n      TEXT  Set user nickname [default: None]
--version             -v            Show version and exit.
--help                              Show this message and exit.
```

## Roadmap

- More game modes
- Optimize for more performance

## Whats New

- Version 0.3.7:
  - Fixed GitHub Actions workflows for correct project references
  - Added Python version matrix testing (3.11, 3.12, 3.13)
  - Updated build configuration to target Python 3.12
  - Improved Makefile with test and clean-all targets
  - Fixed duplicate dependencies in pyproject.toml
- Version 0.3.6:
  - Removed unused dependencies
  - Updated dependencies
  - Tested on Python 3.13
- Version 0.3.5:
  - Updated dependencies
  - Minor bug fixes
- Version 0.3.4:
  - Remove some unnecessary dependencies
  - Minor bug fixes
- Version 0.3.3:
  - Subgrids now have subtle checker background
  - Added `S` key to toggle subgrid highlighting
  - Fixed bug where hitting mine on 1st click after reloading game did not end game
- Version 0.3.2:
  - Ensure 1st click is always safe
- Version 0.3.1:
  - Use XDG specification for data paths
- Version 0.3.0:
  - Fix server mode not using other parameters such as user and nick
  - Limit username and nickname to no more than 30 characters
  - Fix help dialog content display issues
  - Added internet leaderboard!
  - Added `a` key to access authentication dialog for internet leaderboard
- Version 0.2.10:
  - Updated package metadata
  - Removed some unnecessary dependencies
- Version 0.2.9:
  - Fixed some first run db issues
- Version 0.2.8:
  - Addata game data backup
  - Updated readme and help
- Version 0.2.7:
  - Added pause key `p`
  - Fixed bug where sometimes newly generated sub grids would not get saved if no cells were uncovered
  - More optimizations
  - Support for future game modes
- Version 0.2.6:
  - Now only highlights unrevealed surrounding cells when shift/ctrl + left-click on uncovered cells
- Version 0.2.6:
  - Now stops timer on game over
  - Now highlights surrounding cells when shift/ctrl + left-click on uncovered cells
- Version 0.2.5:
  - Disabled some toasts to reduce clutter
  - Moved middle click function to shift/ctrl + left-click on uncovered cells
- Version 0.2.3:
  - Enabled multi user support
- Version 0.2.0:
  - Added webserver to play in a browser
- Version 0.1.0:
  - Initial release

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Shoutout

I would like to thank [Edward Jazzhands](http://edward-jazzhands.github.io/) for all his help testing and feedback / feature requests!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Paul Robello - probello@gmail.com
