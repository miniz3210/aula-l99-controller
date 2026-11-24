"""Dirty region tracking for DI-D1.

Internal backend contract. Each button has a logical region:
  Width: 80, Height: 120, Pixel format: RGB565 LE.

Does NOT assume physical L99 screen supports this region format.
"""

from __future__ import annotations

import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from enum import Enum

from .layout import LayoutModel
from .image_processor import ProcessedImage


class RegionStatus(str, Enum):
    CLEAN = "clean"
    DIRTY = "dirty"
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class DirtyRegion:
    """A single dirty region requiring a screen update."""
    position: int
    x: int
    y: int
    width: int
    height: int
    payload_sha256: str
    rgb565_payload: bytes
    sequence_number: int
    status: RegionStatus = RegionStatus.DIRTY
    first_dirty_at: float = field(default_factory=time.time)
    last_attempt_at: Optional[float] = None
    attempt_count: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["payload_length"] = len(self.rgb565_payload)
        return d


class DirtyRegionTracker:
    """Tracks dirty positions and manages the region update queue.

    Contract:
      - Position-to-region mapping (80x120 RGB565 LE)
      - Dirty position tracking
      - Region update queue with bounded capacity
      - Region payload SHA-256
      - Monotonic update sequence number
      - Duplicate suppression (same SHA -> skip)
    """

    MAX_POSITIONS = 16
    CELL_WIDTH = 80
    CELL_HEIGHT = 120

    def __init__(self, layout: Optional[LayoutModel] = None, max_pending: int = 64) -> None:
        self._layout = layout or LayoutModel()
        self._max_pending = max_pending
        self._regions: Dict[int, DirtyRegion] = {}  # position -> DirtyRegion
        self._dirty_positions: Set[int] = set()
        self._sequence_number = 0
        self._updates_sent = 0
        self._updates_suppressed = 0
        self._updates_failed = 0

    # -- position/region mapping ---------------------------------------
    def position_to_region(self, position: int) -> Optional[dict]:
        """Map position to region rect (x, y, width, height)."""
        if not self._layout.validate_position(position):
            return None
        btn = self._layout.get_button(position)
        if btn is None:
            return None
        return {
            "position": position,
            "x": btn.x,
            "y": btn.y,
            "width": btn.width,
            "height": btn.height,
        }

    def is_valid_position(self, position: int) -> bool:
        return self._layout.validate_position(position)

    # -- dirty tracking ------------------------------------------------
    def mark_dirty(self, position: int, processed_image: ProcessedImage) -> Optional[int]:
        """Mark a position dirty with its processed image.

        Returns the assigned sequence number, or None if suppressed (duplicate SHA).
        Duplicate suppression: if the region already has the same payload SHA-256,
        the update is suppressed.
        """
        if not self.is_valid_position(position):
            return None

        sha256 = processed_image.sha256
        rgb565 = processed_image.rgb565_data

        existing = self._regions.get(position)
        if existing is not None and existing.payload_sha256 == sha256:
            # Duplicate - same image already pending/sent for this position
            self._updates_suppressed += 1
            return None

        region = self._regions.get(position)
        if region is None:
            rect = self.position_to_region(position)
            region = DirtyRegion(
                position=position,
                x=rect["x"] if rect else 0,
                y=rect["y"] if rect else 0,
                width=self.CELL_WIDTH,
                height=self.CELL_HEIGHT,
                payload_sha256=sha256,
                rgb565_payload=rgb565,
                sequence_number=0,  # assigned on enqueue
            )
            self._regions[position] = region

        self._dirty_positions.add(position)
        region.payload_sha256 = sha256
        region.rgb565_payload = rgb565
        region.status = RegionStatus.DIRTY
        region.error_message = None

        # Assign a new monotonic sequence number
        self._sequence_number += 1
        region.sequence_number = self._sequence_number
        region.last_attempt_at = None
        region.attempt_count = 0

        return region.sequence_number

    def mark_clean(self, position: int) -> bool:
        """Mark a position clean (no longer dirty)."""
        if position in self._regions:
            self._regions[position].status = RegionStatus.CLEAN
            self._dirty_positions.discard(position)
            return True
        return False

    def is_dirty(self, position: int) -> bool:
        return position in self._dirty_positions

    def get_dirty_positions(self) -> List[int]:
        """Return sorted list of dirty positions."""
        return sorted(self._dirty_positions)

    def get_region(self, position: int) -> Optional[DirtyRegion]:
        return self._regions.get(position)

    def get_all_regions(self) -> Dict[int, DirtyRegion]:
        return dict(self._regions)

    # -- region update queue ------------------------------------------
    def pop_pending(self, limit: Optional[int] = None) -> List[DirtyRegion]:
        """Pop dirty regions marked DIRTY, transitioning them to PENDING.

        Bounded by max_pending and optional limit. Preserves position order.
        """
        pending: List[DirtyRegion] = []
        positions = self.get_dirty_positions()
        if limit is None:
            limit = self._max_pending
        count = 0
        for pos in positions:
            if count >= limit:
                break
            region = self._regions.get(pos)
            if region is None:
                continue
            region.status = RegionStatus.PENDING
            region.last_attempt_at = time.time()
            region.attempt_count += 1
            pending.append(region)
            count += 1
        return pending

    def mark_sent(self, position: int) -> bool:
        region = self._regions.get(position)
        if region is None:
            return False
        region.status = RegionStatus.SENT
        self._dirty_positions.discard(position)
        self._updates_sent += 1
        return True

    def mark_failed(self, position: int, error_message: str) -> bool:
        region = self._regions.get(position)
        if region is None:
            return False
        region.status = RegionStatus.FAILED
        region.error_message = error_message
        # Keep in dirty set so it can be retried via scheduler
        self._updates_failed += 1
        return True

    def clear_all(self) -> int:
        count = len(self._regions)
        self._regions.clear()
        self._dirty_positions.clear()
        return count

    def clear_profile(self) -> int:
        """Clear all dirty regions (profile switch invalidation)."""
        return self.clear_all()

    # -- diagnostics ---------------------------------------------------
    def get_diagnostics(self) -> dict:
        return {
            "max_positions": self.MAX_POSITIONS,
            "cell_width": self.CELL_WIDTH,
            "cell_height": self.CELL_HEIGHT,
            "max_pending": self._max_pending,
            "dirty_count": len(self._dirty_positions),
            "dirty_positions": sorted(self._dirty_positions),
            "total_regions": len(self._regions),
            "sequence_number": self._sequence_number,
            "updates_sent": self._updates_sent,
            "updates_suppressed": self._updates_suppressed,
            "updates_failed": self._updates_failed,
            "regions": {pos: r.to_dict() for pos, r in self._regions.items()},
        }

    def export_dirty_regions(self, path: str) -> None:
        data = {
            "max_positions": self.MAX_POSITIONS,
            "cell_width": self.CELL_WIDTH,
            "cell_height": self.CELL_HEIGHT,
            "dirty_positions": sorted(self._dirty_positions),
            "sequence_number": self._sequence_number,
            "regions": {pos: r.to_dict() for pos, r in self._regions.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
