from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PostScoreRequest(BaseModel):
    mode: Literal["infinite"]
    difficulty: Literal["easy", "medium", "hard"]
    username: str
    nickname: str
    score: int
    duration: int


class PostScoreResult(BaseModel):
    status: Literal["success", "error"]
    message: str | None = None
