
## Objective
The goal of the game is to uncover all the cells that do not contain mines. 
If you uncover a mine, you lose the game. 
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
  * `H` Highscores.
  * `T` Change theme.
  * `Q` Quit.

## Scoring

The main grid consists of 8x8 sub grids.  
Depending the difficulty level, the number of mines in each sub grid will vary.  
* Easy: 8 mines
* Medium: 12 mines
* Hard: 16 mines

When all cells that are not mines in a sub grid are uncovered the sub grid is marked solved and flags are placed on any mines that are not already flagged.  
Your score is the sum of all mines in the solved sub grids.  
