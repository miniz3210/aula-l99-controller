"""Dynamic Icon Update Scheduler for DI-D1.

Bounded update scheduler that sits between icon callbacks and the transport.

Required features:
  1. Track desired image SHA per position.
  2. Track last submitted SHA per position.
  3. Suppress duplicate updates.
  4. Detect changed positions.
  5. Maintain bounded pending updates.
  6. Coalesce rapid updates for the same position.
  7. Preserve ordering where required.
  8. Prevent stale icon updates.
  9. Support cancellation.
  10. Expose scheduler diagnostics.

Maximum positions: 16 (logical 4x4 layout).
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from enum import Enum

from .image_processor import ProcessedImage
from .layout import LayoutModel


class UpdateStatus(str, Enum):
    REQUESTED = "requested"
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"
    SUPPRESSED = "suppressed"


@dataclass
class PendingUpdate:
    """A single pending icon update ready for transport delivery."""
    position: int
    sequence_number: int
    image_sha256: str
    rgb565_payload: bytes
    profile_id: str
    requested_at: float = field(default_factory=time.time)
    submitted_at: Optional[float] = None
    status: UpdateStatus = UpdateStatus.PENDING
    attempt_count: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["payload_length"] = len(self.rgb565_payload)
        return d


class IconUpdateScheduler:
    """Bounded dynamic icon update scheduler.

    Contract:
      - desired_sha[position] = latest SHA requested by OpenDeck
      - submitted_sha[position] = last SHA actually handed to transport
      - Only one pending update per position (coalescing rapid updates)
      - Stale updates: if desired_sha changed after a pending update was
        created but before it was sent, the pending update uses the latest
        desired image (not a stale one).
      - Cancellation removes a pending update and clears submitted state.
      - Bounded queue: max_pending updates across all positions.
    """

    MAX_POSITIONS = 16

    def __init__(
        self,
        layout: Optional[LayoutModel] = None,
        max_pending: int = 32,
        profile_id: str = "default",
    ) -> None:
        self._layout = layout or LayoutModel()
        self._max_pending = max_pending
        self._profile_id = profile_id
        self._device_id: Optional[str] = None

        # Desired state per position (latest OpenDeck request)
        self._desired_sha: Dict[int, str] = {}
        self._desired_image: Dict[int, ProcessedImage] = {}

        # Last submitted state per position
        self._submitted_sha: Dict[int, str] = {}

        # Coalesced pending updates: one per position (latest wins)
        self._pending: Dict[int, PendingUpdate] = {}

        # Cancellation tracking
        self._cancelled: Set[int] = set()

        # Monotonic sequence
        self._sequence_number = 0
        self._profile_history: Dict[str, Dict[int, str]] = {}  # profile -> pos -> sha

        # Stats
        self._updates_requested = 0
        self._updates_suppressed = 0
        self._updates_coalesced = 0
        self._updates_sent = 0
        self._updates_failed = 0
        self._updates_cancelled = 0
        self._stale_prevented = 0

    # -- configuration -------------------------------------------------
    @property
    def profile_id(self) -> str:
        return self._profile_id

    def set_profile_id(self, profile_id: str) -> None:
        self._profile_id = profile_id

    def set_device_id(self, device_id: str) -> None:
        self._device_id = device_id

    def is_valid_position(self, position: int) -> bool:
        return self._layout.validate_position(position)

    # -- core: request an update --------------------------------------
    def request_update(
        self,
        position: int,
        processed_image: ProcessedImage,
        profile_id: Optional[str] = None,
    ) -> Optional[int]:
        """Request an icon update for a position.

        Returns the sequence number assigned, or None if suppressed (duplicate
        SHA already desired/submitted) or invalid position.

        Coalescing: if a pending update already exists for this position, it is
        replaced with the latest image (rapid updates coalesce to latest).
        """
        if not self.is_valid_position(position):
            return None

        pid = profile_id or self._profile_id
        sha = processed_image.sha256

        # Track desired state
        prev_desired_sha = self._desired_sha.get(position)
        self._desired_sha[position] = sha
        self._desired_image[position] = processed_image

        # Duplicate suppression: same SHA already desired and submitted
        if (
            prev_desired_sha == sha
            and self._submitted_sha.get(position) == sha
            and position not in self._pending
        ):
            self._updates_suppressed += 1
            return None

        # If there's an existing pending update for this position, coalesce
        # (replace with latest). Rapid updates -> only latest matters.
        if position in self._pending:
            existing = self._pending[position]
            existing.image_sha256 = sha
            existing.rgb565_payload = processed_image.rgb565_data
            existing.profile_id = pid
            existing.status = UpdateStatus.PENDING
            existing.error_message = None
            existing.attempt_count = 0
            # Keep original sequence number to preserve ordering position
            self._updates_coalesced += 1
            return existing.sequence_number

        # Enforce bounded pending queue
        if len(self._pending) >= self._max_pending:
            # Reject: queue full. The desired state is still recorded so a
            # later retry (or reconnect rebuild) can pick it up.
            self._updates_failed += 1
            return None

        # Assign a new monotonic sequence number
        self._sequence_number += 1
        pending = PendingUpdate(
            position=position,
            sequence_number=self._sequence_number,
            image_sha256=sha,
            rgb565_payload=processed_image.rgb565_data,
            profile_id=pid,
            status=UpdateStatus.PENDING,
        )
        self._pending[position] = pending
        self._updates_requested += 1
        return pending.sequence_number

    # -- cancellation --------------------------------------------------
    def cancel(self, position: int) -> bool:
        """Cancel a pending update for a position. Returns True if cancelled."""
        if position not in self._pending:
            return False
        pending = self._pending.pop(position)
        pending.status = UpdateStatus.CANCELLED
        self._cancelled.add(position)
        # Clear submitted + desired so a future re-request is not suppressed
        self._submitted_sha.pop(position, None)
        self._desired_sha.pop(position, None)
        self._desired_image.pop(position, None)
        self._updates_cancelled += 1
        return True

    # -- pop pending for transport -------------------------------------
    def pop_pending(self, limit: Optional[int] = None) -> List[PendingUpdate]:
        """Pop pending updates ready for transport delivery.

        Returns updates sorted by sequence number (preserves ordering).
        Only one update per position (coalesced). Stale updates are
        refreshed to the latest desired image before sending.
        """
        if limit is None:
            limit = self._max_pending

        ready: List[PendingUpdate] = []
        # Sort by sequence number to preserve ordering
        for position in sorted(self._pending.keys(), key=lambda p: self._pending[p].sequence_number):
            if len(ready) >= limit:
                break
            if position in self._cancelled:
                continue
            pending = self._pending[position]
            pending.status = UpdateStatus.PENDING
            pending.attempt_count += 1

            # Stale prevention: if desired image changed since this pending
            # was created, send the latest desired image instead.
            desired_sha = self._desired_sha.get(position)
            if desired_sha is not None and desired_sha != pending.image_sha256:
                desired_image = self._desired_image.get(position)
                if desired_image is not None:
                    pending.image_sha256 = desired_image.sha256
                    pending.rgb565_payload = desired_image.rgb565_data
                    self._stale_prevented += 1

            ready.append(pending)
        return ready

    # -- confirm sent / failed -----------------------------------------
    def confirm_sent(self, position: int, sha: str) -> bool:
        """Mark a position's update as sent to transport."""
        pending = self._pending.pop(position, None)
        if pending is not None:
            pending.status = UpdateStatus.SENT
            pending.submitted_at = time.time()
        self._submitted_sha[position] = sha
        self._cancelled.discard(position)
        self._updates_sent += 1
        return True

    def confirm_failed(self, position: int, error_message: str) -> bool:
        """Mark a pending update as failed; desired state preserved for retry."""
        pending = self._pending.get(position)
        if pending is not None:
            pending.status = UpdateStatus.FAILED
            pending.error_message = error_message
        self._updates_failed += 1
        # Desired state remains; scheduler will resubmit on next pop_pending
        return True

    # -- profile handling ----------------------------------------------
    def switch_profile(self, new_profile_id: str) -> List[int]:
        """Handle a profile change.

        1. Invalidate obsolete queued updates (clear pending for old profile).
        2. Preserve profile-specific desired cache.
        3. Clear positions without images in the new profile.
        4. Avoid sending icons from the previous profile.

        Returns list of positions cleared.
        """
        old_profile = self._profile_id
        # Save old profile's desired state
        if old_profile:
            self._profile_history[old_profile] = dict(self._desired_sha)

        # Invalidate pending updates (they belonged to old profile)
        cleared_positions: List[int] = []
        for position in list(self._pending.keys()):
            pending = self._pending.pop(position)
            pending.status = UpdateStatus.CANCELLED
            self._cancelled.add(position)
            cleared_positions.append(position)
            self._updates_cancelled += 1

        # Reset submitted state so old-profile icons aren't resent
        self._submitted_sha.clear()

        # Reset desired state for the new profile (positions without images
        # are effectively cleared - no desired state carried over)
        self._desired_sha.clear()
        self._desired_image.clear()

        self._profile_id = new_profile_id
        return sorted(cleared_positions)

    def get_profile_history(self) -> Dict[str, Dict[int, str]]:
        return {k: dict(v) for k, v in self._profile_history.items()}

    # -- reconnect recovery --------------------------------------------
    def rebuild_desired_state(self) -> List[int]:
        """After reconnect, mark all desired positions dirty for resubmission.

        Returns positions that need resubmission (desired != submitted).
        """
        resubmit: List[int] = []
        for position, sha in self._desired_sha.items():
            submitted = self._submitted_sha.get(position)
            if submitted != sha:
                resubmit.append(position)
                # Re-create a pending update from desired image
                image = self._desired_image.get(position)
                if image is not None and position not in self._pending:
                    if len(self._pending) < self._max_pending:
                        self._sequence_number += 1
                        self._pending[position] = PendingUpdate(
                            position=position,
                            sequence_number=self._sequence_number,
                            image_sha256=sha,
                            rgb565_payload=image.rgb565_data,
                            profile_id=self._profile_id,
                            status=UpdateStatus.PENDING,
                        )
        return sorted(resubmit)

    # -- query helpers -------------------------------------------------
    def get_desired_sha(self, position: int) -> Optional[str]:
        return self._desired_sha.get(position)

    def get_submitted_sha(self, position: int) -> Optional[str]:
        return self._submitted_sha.get(position)

    def is_dirty(self, position: int) -> bool:
        """A position is dirty if desired != submitted (needs update)."""
        desired = self._desired_sha.get(position)
        submitted = self._submitted_sha.get(position)
        return desired is not None and desired != submitted

    def get_dirty_positions(self) -> List[int]:
        return sorted(p for p in self._desired_sha if self.is_dirty(p))

    def get_pending_positions(self) -> List[int]:
        return sorted(self._pending.keys())

    def get_pending(self, position: int) -> Optional[PendingUpdate]:
        return self._pending.get(position)

    # -- diagnostics ---------------------------------------------------
    def get_diagnostics(self) -> dict:
        return {
            "max_positions": self.MAX_POSITIONS,
            "max_pending": self._max_pending,
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "desired_count": len(self._desired_sha),
            "submitted_count": len(self._submitted_sha),
            "pending_count": len(self._pending),
            "dirty_count": len(self.get_dirty_positions()),
            "dirty_positions": self.get_dirty_positions(),
            "pending_positions": self.get_pending_positions(),
            "sequence_number": self._sequence_number,
            "updates_requested": self._updates_requested,
            "updates_suppressed": self._updates_suppressed,
            "updates_coalesced": self._updates_coalesced,
            "updates_sent": self._updates_sent,
            "updates_failed": self._updates_failed,
            "updates_cancelled": self._updates_cancelled,
            "stale_prevented": self._stale_prevented,
            "desired": dict(self._desired_sha),
            "submitted": dict(self._submitted_sha),
            "pending": {pos: p.to_dict() for pos, p in self._pending.items()},
        }

    def export_scheduler_trace(self, path: str) -> None:
        data = {
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "max_positions": self.MAX_POSITIONS,
            "max_pending": self._max_pending,
            "sequence_number": self._sequence_number,
            "desired": dict(self._desired_sha),
            "submitted": dict(self._submitted_sha),
            "pending": {pos: p.to_dict() for pos, p in self._pending.items()},
            "stats": {
                "requested": self._updates_requested,
                "suppressed": self._updates_suppressed,
                "coalesced": self._updates_coalesced,
                "sent": self._updates_sent,
                "failed": self._updates_failed,
                "cancelled": self._updates_cancelled,
                "stale_prevented": self._stale_prevented,
            },
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
