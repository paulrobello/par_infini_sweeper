"""Leaderboard / OAuth-protected HTTP helpers (ARC-004 decomposition).

Posting a score and changing a nickname are the only two HTTP calls the model
previously made against the leaderboard service. They've been pulled out of
``GameState`` so the model class is no longer wired to ``os.environ`` /
``authlib`` / the request/response models. ``GameState.post_internet_score``
and ``GameState.change_internet_nickname`` are now one-line delegates.

Bodies are byte-for-byte equivalent to the originals — including the
``# type: ignore[reportAttributeAccessIssue]`` notes on ``auth_client.post``
(``auth_client`` is typed as the return of ``build_auth_client``, which
pyright can't narrow to a method-bearing type).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from par_infini_sweeper.models import ChangeNicknameRequest, ChangeNicknameResponse, PostScoreRequest, PostScoreResult

if TYPE_CHECKING:
    # TYPE_CHECKING-only so leaderboard.py has no runtime dependency on the
    # model module — breaks the otherwise-circular ``game.state ↔ leaderboard`` edge.
    from par_infini_sweeper.game.state import GameState


def post_internet_score(state: GameState) -> PostScoreResult:
    """Post ``state``'s current score to the leaderboard service.

    Args:
        state (GameState): Game state carrying the user / score / mode / difficulty.

    Returns:
        PostScoreResult: Result of the post operation.
    """
    if not state.is_logged_in():
        raise Exception("User is not logged in")
    url = os.environ.get("PIM_LEADERBOARD_URL", "https://pim.pardev.net") + "/score"

    res = state.auth_client.post(  # type: ignore[reportAttributeAccessIssue]
        url,
        data=PostScoreRequest(
            mode=state.mode.value,
            difficulty=state.difficulty.value,
            score=state.score(),
            duration=state.duration,
        ).model_dump_json(),
    ).json()

    if "detail" in res:
        raise Exception(res["detail"] or "Unknown server error")

    return PostScoreResult.model_validate(res)


def change_internet_nickname(state: GameState, nickname: str) -> ChangeNicknameResponse:
    """Change the user's nickname on the leaderboard service.

    Args:
        state (GameState): Game state carrying the auth client / user dict.
        nickname (str): New nickname to set.

    Returns:
        ChangeNicknameResponse: Result of the change operation.
    """
    if not state.is_logged_in():
        raise Exception("User is not logged in")
    url = os.environ.get("PIM_LEADERBOARD_URL", "https://pim.pardev.net") + "/nickname"

    res = state.auth_client.post(url, data=ChangeNicknameRequest(nickname=nickname).model_dump_json()).json()  # type: ignore[reportAttributeAccessIssue]
    if "detail" in res:
        raise Exception(res["detail"] or "Unknown server error")

    result = ChangeNicknameResponse.model_validate(res)
    if not result.status == "success":
        raise Exception(result.message or "Unknown server error")
    state.user["net_nickname"] = nickname
    state.save_user()
    return result
