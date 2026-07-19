"""Par Infinite Minesweeper."""

from __future__ import annotations

__author__ = "Paul Robello"
__credits__ = ["Paul Robello"]
__maintainer__ = "Paul Robello"
__email__ = "probello@gmail.com"
__version__ = "0.4.1"
__application_title__ = "Par Infinite Minesweeper"
__application_binary__ = "pim"
__licence__ = "MIT"

# ARC-007: importing the package no longer has import-time side effects.
# Previously this module also:
#   * called ``load_dotenv()`` — pulled in python-dotenv and read .env on import
#   * wrote ``os.environ["USER_AGENT"]`` — env mutation on import
#   * imported ``PimApp`` — dragged the entire Textual/UI tree into any caller
#     that touched the package (and triggered the heavy ``PimApp`` module load).
# ``load_dotenv`` and ``USER_AGENT`` now live in ``__main__`` (module-level),
# and ``PimApp`` is imported directly from ``par_infini_sweeper.pim_app``.

__all__: list[str] = [
    "__author__",
    "__credits__",
    "__maintainer__",
    "__email__",
    "__version__",
    "__application_binary__",
    "__licence__",
    "__application_title__",
]
