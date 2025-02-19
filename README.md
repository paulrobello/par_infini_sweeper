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
Middle click or SHIFT + Left click to toggle flagging a cell as a mine.  
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
* Easy: 5 mines
* Medium: 10 mines
* Hard: 15 mines

When all cells that are not mines in a sub grid are uncovered the sub grid is marked solved and flags are placed on any mines that are not already flagged.  
Your score is the number of solved sub grids times the difficulty level.  
* Easy: x1
* Medium: x2
* Hard: x3

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
- `-s`, `--server`: Start webserver that allows app to be played in a browser              
- `-h`, `--help`: Show this help message and exit
- `--version`, `-v`: Print version information and exit

## Roadmap

- Add multi user support
- Add multi game support
- Optimize for more performance

## Whats New

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
