from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

NICKNAME_MIN_LENGTH = 2
NICKNAME_MAX_LENGTH = 20
# Letters, digits, dot, dash, underscore. Matches the prompt already shown in
# dialogs/login_dialog.py ("letters, numbers and . - _").
_NICKNAME_PATTERN = re.compile(r"\A[A-Za-z0-9._-]+\Z")


def validate_nickname(name: str) -> str:
    """Validate a nickname against the canonical length and charset rules.

    Args:
        name: Nickname to validate.

    Returns:
        The validated nickname.

    Raises:
        ValueError: If the nickname is too short, too long, or contains
            characters outside the allowed charset.
    """
    if len(name) < NICKNAME_MIN_LENGTH:
        raise ValueError(f"Nickname must be at least {NICKNAME_MIN_LENGTH} characters")
    if len(name) > NICKNAME_MAX_LENGTH:
        raise ValueError(f"Nickname must be {NICKNAME_MAX_LENGTH} characters or less")
    if not _NICKNAME_PATTERN.match(name):
        raise ValueError("Nickname may only contain letters, numbers, and . - _")
    return name


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
    nickname: str = Field(..., min_length=NICKNAME_MIN_LENGTH, max_length=NICKNAME_MAX_LENGTH)
    created_ts: datetime

    @field_validator("nickname")
    @classmethod
    def _validate_nickname_field(cls, v: str) -> str:
        return validate_nickname(v)


class ScoreDataResponse(PostScoreResult):
    scores: list[ScoreData]


class ChangeNicknameRequest(BaseModel):
    nickname: str = Field(..., min_length=NICKNAME_MIN_LENGTH, max_length=NICKNAME_MAX_LENGTH)

    @field_validator("nickname")
    @classmethod
    def _validate_nickname_field(cls, v: str) -> str:
        return validate_nickname(v)


class ChangeNicknameResponse(PimResult):
    pass
