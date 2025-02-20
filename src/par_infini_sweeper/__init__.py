"""Par Infinite Minesweeper."""

from __future__ import annotations

import os

__author__ = "Paul Robello"
__credits__ = ["Paul Robello"]
__maintainer__ = "Paul Robello"
__email__ = "probello@gmail.com"
__version__ = "0.2.10"
__application_title__ = "Par Infinite Minesweeper"
__application_binary__ = "pim"
__licence__ = "MIT"

from par_infini_sweeper.minesweeper_app import MinesweeperApp

os.environ["USER_AGENT"] = f"{__application_title__} {__version__}"


__all__: list[str] = [
    "__author__",
    "__credits__",
    "__maintainer__",
    "__email__",
    "__version__",
    "__application_binary__",
    "__licence__",
    "__application_title__",
    "MinesweeperApp",
]
