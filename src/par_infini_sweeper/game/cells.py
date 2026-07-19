"""``Cell`` — a single tile in a subgrid (ARC-004 extraction).

Pure model class moved out of ``data_structures.py``. No I/O, no Textual
dependency — only references its parent ``SubGrid`` and (transitively) the
``GameState``'s ``highlighted_cells`` set via that parent.

The ``SubGrid`` import is TYPE_CHECKING-only so the ``cells ↔ subgrid`` edge
doesn't form a runtime cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from par_infini_sweeper.game.subgrid import SubGrid


class Cell:
    """Represents a single cell in a subgrid.

    Carries the mine / flag / uncovered / highlighted bits plus a ``changed``
    dirty flag that propagates up to its parent ``SubGrid`` (and from there to
    ``GameState.changed_subgrids``) so the incremental save only writes
    subgrids that actually mutated.
    """

    def __init__(self, parent: SubGrid, is_mine: bool, marked: bool = False, uncovered: bool = False) -> None:
        """Initialize a cell.

        Args:
            parent: The ``SubGrid`` that owns this cell.
            is_mine: Whether this cell hides a mine.
            marked: Whether the player has flagged this cell as a mine.
            uncovered: Whether this cell has already been revealed.
        """
        self._parent = parent
        self._is_mine: bool = is_mine
        self._marked: bool = marked
        self._uncovered: bool = uncovered
        self._changed: bool = False
        self._highlighted: bool = False

    @property
    def is_mine(self) -> bool:
        """Return whether this cell hides a mine. Setting it marks the cell dirty."""
        return self._is_mine

    @is_mine.setter
    def is_mine(self, value: bool) -> None:
        if self._is_mine != value:
            self._is_mine = value
            self.changed = True

    @property
    def marked(self) -> bool:
        """Return whether the cell is flagged. Setting it marks the cell dirty."""
        return self._marked

    @marked.setter
    def marked(self, value: bool) -> None:
        if self._marked != value:
            self._marked = value
            self.changed = True

    @property
    def uncovered(self) -> bool:
        """Return whether the cell has been revealed. Setting it marks the cell dirty."""
        return self._uncovered

    @uncovered.setter
    def uncovered(self, value: bool) -> None:
        if self._uncovered != value:
            self._uncovered = value
            self.changed = True

    @property
    def highlighted(self) -> bool:
        """Return whether the cell is currently mouse-hover-highlighted.

        Setting it adds/removes the cell from
        ``GameState.highlighted_cells`` via ``self.parent.parent`` — this is
        the ``Cell → SubGrid → GameState`` path the dirty-flag system does
        not cover, because highlight state is transient and not persisted.
        """
        return self._highlighted

    @highlighted.setter
    def highlighted(self, value: bool) -> None:
        if self._highlighted != value:
            self._highlighted = value
            self.parent.parent.highlighted_cells.add(self) if value else self.parent.parent.highlighted_cells.discard(
                self
            )

    @property
    def parent(self) -> SubGrid:
        """Return the ``SubGrid`` that owns this cell."""
        return self._parent

    @property
    def changed(self) -> bool:
        """Return the dirty flag. Setting to ``True`` propagates up to the parent ``SubGrid``."""
        return self._changed

    @changed.setter
    def changed(self, value: bool) -> None:
        if self._changed != value:
            self._changed = value
            if value:
                self._parent.changed = True

    def to_dict(self) -> dict[str, bool]:
        """Return a dictionary representation of this cell."""
        return {"is_mine": self.is_mine, "marked": self.marked, "uncovered": self.uncovered}

    @staticmethod
    def from_dict(parent: SubGrid, data: dict[str, bool]) -> Cell:
        """Create a Cell instance from its dictionary representation."""
        return Cell(parent, data["is_mine"], data["marked"], data["uncovered"])
