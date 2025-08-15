
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
Depending the difficulty level, the number of mines in each sub grid will vary.  
* Easy: 8 mines
* Medium: 12 mines
* Hard: 16 mines

When all cells that are not mines in a sub grid are uncovered the sub grid is marked solved turns a darker gray and flags are placed on any mines that are not already flagged.  
Your score is the sum of all mines in the solved sub grids.  

## Internet Leaderboard

To use the internet leaderboard you must login to the server via a social provider such as google or facebook.  
This requires 2 things:
1. The game must listen on port 1999 for the authentication callback.
2. The game must launch a browser so you can login.
- Only your hashed email is stored on the server.
- The port will only be opened for the duration of the login process.
- After you have logged in and reserved your nickname, you can then submit your scores to the server for the current game mode and difficulty.

See our [privacy policy](https://par-com.net/privacy_policy.html) for details on data handling.
