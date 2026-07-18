"""Leaderboard / OAuth-protected HTTP helpers (ARC-004 decomposition).

Posting a score and changing a nickname are the only two HTTP calls the model
previously made against the leaderboard service. They've been pulled out of
``GameState`` so the model class is no longer wired to ``os.environ`` /
``authlib`` / the request/response models. ``GameState.post_internet_score``
and ``GameState.change_internet_nickname`` are now one-line delegates.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

import requests

from par_infini_sweeper.models import ChangeNicknameRequest, ChangeNicknameResponse, PostScoreRequest, PostScoreResult

if TYPE_CHECKING:
    # TYPE_CHECKING-only so leaderboard.py has no runtime dependency on the
    # model module — breaks the otherwise-circular ``game.state ↔ leaderboard`` edge.
    from par_infini_sweeper.game.state import GameState


def _auth_post(state: GameState, url: str, *, data: str) -> requests.Response:
    """POST ``data`` to ``url`` using ``state``'s auth-bearing session.

    QA-005: ``authlib.integrations.requests_client.OAuth2Session`` proxies
    ``requests.Session`` at runtime (so ``.post`` is callable) but its type
    stubs do not surface that inheritance, which left per-call-site
    ``# type: ignore[reportAttributeAccessIssue]`` markers on every leaderboard
    HTTP call. Routing through here narrows once via ``cast`` so call sites
    get a typed ``requests.Response`` and no suppressions are needed.

    Args:
        state (GameState): Game state whose ``auth_client`` carries the bearer token.
        url (str): Absolute leaderboard URL.
        data (str): JSON body to send.

    Returns:
        requests.Response: The HTTP response.
    """
    return cast(requests.Session, state.auth_client).post(url, data=data)


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

    res = _auth_post(
        state,
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

    res = _auth_post(state, url, data=ChangeNicknameRequest(nickname=nickname).model_dump_json()).json()
    if "detail" in res:
        raise Exception(res["detail"] or "Unknown server error")

    result = ChangeNicknameResponse.model_validate(res)
    if not result.status == "success":
        raise Exception(result.message or "Unknown server error")
    state.user["net_nickname"] = nickname
    state.save_user()
    return result
