# Par Infinite Minesweeper

## Description

Infinite Minesweeper TUI. Play a game of minesweeper with infinite board size!

![Par Infinite Minesweeper](https://raw.githubusercontent.com/paulrobello/par_infini_sweeper/main/Screenshot.png)

## Technology
- Python
- Textual
- Sqlite3

## Objective
The goal of the game is to uncover all the cells that do not contain mines. 
If you uncover a mine, you lose the game. 
If you uncover a cell that is not a mine, it will show a number indicating how many mines are in the neighboring cells. 
Use this information to determine which cells are safe to uncover.

## Controls
Left click to uncover a cell. If a cell is flagged as a mine, it will not be uncovered.  
Sub grids can only be unlocked when cells neighboring the sub grid are uncovered.  
Shift or Ctrl + Left-click to toggle flagging a covered cell as a mine. On an uncovered cell it will uncover all neighboring cells. As a safety you must have same number of flags as mines in the neighboring cells.  
Drag to pan the board.  
Keys:  
* `F1` help.
* `N` new game.
* `O` move view to origin.
* `C` move view to board center (computed as center of exposed sub grids).
* `H` highscores.
* `T` change theme.
* `Q` quit game.

## Scoring

The main grid consists of 8x8 sub grids.  
Depending the difficulty level, the number of mines in each sub grid will vary.  
* Easy: 8 mines
* Medium: 12 mines
* Hard: 16 mines

When all cells that are not mines in a sub grid are uncovered the sub grid is marked solved and flags are placed on any mines that are not already flagged.  
Your score is the sum of all mines in the solved sub grids.  


## Prerequisites

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
par_infini_sweeper [OPTIONS]
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
--version             -v
--help                              Show this message and exit.
```

## Roadmap

- Optimize for more performance

## Whats New
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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Paul Robello - probello@gmail.com
