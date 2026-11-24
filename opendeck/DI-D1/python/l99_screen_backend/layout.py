"""4x4 Layout model for L99 logical screen preview."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class ButtonState(str, Enum):
    """Logical button states for preview."""
    OFF = "off"
    ON = "on"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ButtonLayout:
    """Single button layout info."""
    position: int
    x: int
    y: int
    width: int
    height: int
    row: int
    col: int


@dataclass
class LayoutModel:
    """4x4 logical layout model for L99 screen preview.
    
    Canvas: 320x480
    Logical positions: 0-15 (row-major order)
    Cell size: 80x120
    
    WARNING: This layout overlaps stock Home Navigation area.
    Use for offline preview only. Do not approve for physical deployment.
    """

    # Screen dimensions
    SCREEN_WIDTH: int = 320
    SCREEN_HEIGHT: int = 480
    ROWS: int = 4
    COLS: int = 4
    CELL_WIDTH: int = 80
    CELL_HEIGHT: int = 120
    TOTAL_POSITIONS: int = 16

    # Button layouts (computed once)
    _buttons: List[ButtonLayout] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if not self._buttons:
            self._buttons = self._compute_buttons()

    def _compute_buttons(self) -> List[ButtonLayout]:
        """Compute button layouts in row-major order (0-15)."""
        buttons = []
        for row in range(self.ROWS):
            for col in range(self.COLS):
                position = row * self.COLS + col
                x = col * self.CELL_WIDTH
                y = row * self.CELL_HEIGHT
                buttons.append(ButtonLayout(
                    position=position,
                    x=x,
                    y=y,
                    width=self.CELL_WIDTH,
                    height=self.CELL_HEIGHT,
                    row=row,
                    col=col
                ))
        return buttons

    def get_button(self, position: int) -> Optional[ButtonLayout]:
        """Get button layout by position (0-15)."""
        if 0 <= position < self.TOTAL_POSITIONS:
            return self._buttons[position]
        return None

    def get_button_at(self, x: int, y: int) -> Optional[ButtonLayout]:
        """Get button layout at screen coordinates."""
        col = x // self.CELL_WIDTH
        row = y // self.CELL_HEIGHT
        if 0 <= row < self.ROWS and 0 <= col < self.COLS:
            return self.get_button(row * self.COLS + col)
        return None

    def get_all_buttons(self) -> List[ButtonLayout]:
        """Get all button layouts."""
        return list(self._buttons)

    def position_to_row_col(self, position: int) -> Optional[Tuple[int, int]]:
        """Convert position to (row, col)."""
        if 0 <= position < self.TOTAL_POSITIONS:
            return (position // self.COLS, position % self.COLS)
        return None

    def row_col_to_position(self, row: int, col: int) -> Optional[int]:
        """Convert (row, col) to position."""
        if 0 <= row < self.ROWS and 0 <= col < self.COLS:
            return row * self.COLS + col
        return None

    def validate_position(self, position: int) -> bool:
        """Validate position is in range."""
        return 0 <= position < self.TOTAL_POSITIONS

    def get_cell_rect(self, position: int) -> Optional[Tuple[int, int, int, int]]:
        """Get (x, y, width, height) for position."""
        btn = self.get_button(position)
        if btn:
            return (btn.x, btn.y, btn.width, btn.height)
        return None

    def to_dict(self) -> dict:
        """Serialize layout for debugging."""
        return {
            "screen_width": self.SCREEN_WIDTH,
            "screen_height": self.SCREEN_HEIGHT,
            "rows": self.ROWS,
            "cols": self.COLS,
            "cell_width": self.CELL_WIDTH,
            "cell_height": self.CELL_HEIGHT,
            "total_positions": self.TOTAL_POSITIONS,
            "buttons": [
                {
                    "position": b.position,
                    "row": b.row,
                    "col": b.col,
                    "x": b.x,
                    "y": b.y,
                    "width": b.width,
                    "height": b.height
                }
                for b in self._buttons
            ],
            "warning": "This 4x4 layout overlaps stock Home Navigation area. Use for offline preview only."
        }


# Default layout instance
DEFAULT_LAYOUT = LayoutModel()