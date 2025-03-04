from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PimResult(BaseModel):
    status: Literal["success", "error"]
    message: str | None = None


class PostScoreResult(PimResult):
    pass


class PostScoreRequest(BaseModel):
    mode: Literal["infinite"]
    difficulty: Literal["easy", "medium", "hard"]
    score: int = Field(..., gt=0)
    duration: int = Field(..., gt=0)


class ScoreData(PostScoreRequest):
    nickname: str = Field(..., min_length=2, max_length=30)
    created_ts: datetime


class ScoreDataResponse(PostScoreResult):
    scores: list[ScoreData]


class ChangeNicknameRequest(BaseModel):
    nickname: str = Field(..., min_length=2, max_length=30)


class ChangeNicknameResponse(PimResult):
    pass
