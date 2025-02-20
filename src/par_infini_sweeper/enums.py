from __future__ import annotations

from enum import StrEnum


class GameMode(StrEnum):
    INFINITE = "infinite"


class GameDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
