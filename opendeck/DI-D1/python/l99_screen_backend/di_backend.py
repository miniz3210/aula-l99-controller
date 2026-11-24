"""DI-D1 Dynamic Icon Pipeline backend integration.

Wires together:
  - IconUpdateScheduler (bounded dynamic update scheduler)
  - DirtyRegionTracker (position->region mapping, dirty tracking)
  - MockScreenTransport (transport interface, SENT_UNCONFIRMED only)
  - Existing ScreenBackend (image processing, cache, state)

Reuses existing OD2-B-R2 Python backend modules unchanged.
No physical USB writes. No public TCP listener.
"""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .backend import ScreenBackend, ImageUpdateRequest, ImageUpdateResult
from .image_processor import ProcessedImage
from .layout import LayoutModel
from .state_manager import LogicalButtonState, PhysicalConfirmStatus
from .transport import MockScreenTransport, ScreenTransport
from .dirty_regions import DirtyRegionTracker, RegionStatus
from .scheduler import IconUpdateScheduler, UpdateStatus


@dataclass
class DynamicUpdateResult:
    """Result of a dynamic icon update request."""
    success: bool
    device_id: str
    profile_id: str
    position: int
    image_sha256: Optional[str]
    duplicate_suppressed: bool
    coalesced: bool
    sequence_number: Optional[int]
    status: str
    error: Optional[str] = None
    timestamp: float = 0.0


class DIDynamicBackend:
    """DI-D1 dynamic icon delivery backend.

    Flow:
      Icon callback -> scheduler.request_update -> dirty_regions.mark_dirty
      -> pop_pending -> transport.send_region -> scheduler.confirm_sent
      -> dirty_regions.mark_sent
    """

    def __init__(
        self,
        device_id: str = "al-l99-0001",
        profile_id: str = "default",
        layout: Optional[LayoutModel] = None,
        max_pending: int = 32,
        max_dirty_pending: int = 64,
    ) -> None:
        self._device_id = device_id
        self._profile_id = profile_id
        self._layout = layout or LayoutModel()

        # Existing backend (image processing + cache + state + legacy transport)
        self._backend = ScreenBackend(layout=self._layout)

        # New DI-D1 components
        self._transport = MockScreenTransport(self._layout, self._backend.state_manager)
        self._dirty_regions = DirtyRegionTracker(self._layout, max_pending=max_dirty_pending)
        self._scheduler = IconUpdateScheduler(
            layout=self._layout, max_pending=max_pending, profile_id=profile_id
        )
        self._scheduler.set_device_id(device_id)

        # Connect transport
        self._transport.connect(device_id, profile_id)

        # Diagnostics
        self._update_count = 0

    # -- properties ----------------------------------------------------
    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def profile_id(self) -> str:
        return self._profile_id

    @property
    def backend(self) -> ScreenBackend:
        return self._backend

    @property
    def transport(self) -> MockScreenTransport:
        return self._transport

    @property
    def scheduler(self) -> IconUpdateScheduler:
        return self._scheduler

    @property
    def dirty_regions(self) -> DirtyRegionTracker:
        return self._dirty_regions

    @property
    def layout(self) -> LayoutModel:
        return self._layout

    # -- core update flow ----------------------------------------------
    def request_icon_update(
        self,
        position: int,
        processed_image: ProcessedImage,
        profile_id: Optional[str] = None,
    ) -> DynamicUpdateResult:
        """Request a dynamic icon update.

        This is the entry point replacing direct backend.process_image_update
        for the dynamic pipeline. It records desired state, suppresses
        duplicates, marks dirty regions, and queues via the scheduler.
        """
        timestamp = time.time()
        pid = profile_id or self._profile_id

        if not self._layout.validate_position(position):
            return DynamicUpdateResult(
                success=False, device_id=self._device_id, profile_id=pid,
                position=position, image_sha256=None, duplicate_suppressed=False,
                coalesced=False, sequence_number=None, status="invalid_position",
                error=f"Invalid position {position}", timestamp=timestamp,
            )

        sha = processed_image.sha256

        # Request via scheduler (handles desired state, duplicate suppression,
        # coalescing, bounded queue)
        seq = self._scheduler.request_update(position, processed_image, pid)

        if seq is None:
            # Suppressed (duplicate) - check why
            desired = self._scheduler.get_desired_sha(position)
            submitted = self._scheduler.get_submitted_sha(position)
            suppressed = (desired == sha and submitted == sha)
            return DynamicUpdateResult(
                success=True, device_id=self._device_id, profile_id=pid,
                position=position, image_sha256=sha,
                duplicate_suppressed=suppressed, coalesced=False,
                sequence_number=None, status="suppressed",
                error=None if suppressed else "queue_full",
                timestamp=timestamp,
            )

        # Mark dirty region (duplicate SHA already suppressed by scheduler,
        # but dirty_regions also does its own duplicate check - harmless)
        self._dirty_regions.mark_dirty(position, processed_image)

        self._update_count += 1
        return DynamicUpdateResult(
            success=True, device_id=self._device_id, profile_id=pid,
            position=position, image_sha256=sha, duplicate_suppressed=False,
            coalesced=False, sequence_number=seq, status="queued",
            error=None, timestamp=timestamp,
        )

    def flush_pending(self) -> List[DynamicUpdateResult]:
        """Flush all pending updates to the transport.

        Pops pending updates from scheduler, sends via transport, marks
        dirty regions sent/failed. Returns per-update results.
        """
        results: List[DynamicUpdateResult] = []
        pending = self._scheduler.pop_pending()
        for p in pending:
            ok = self._transport.send_region(
                p.position, p.rgb565_payload, p.image_sha256
            )
            if ok:
                self._scheduler.confirm_sent(p.position, p.image_sha256)
                self._dirty_regions.mark_sent(p.position)
                results.append(DynamicUpdateResult(
                    success=True, device_id=self._device_id,
                    profile_id=p.profile_id, position=p.position,
                    image_sha256=p.image_sha256, duplicate_suppressed=False,
                    coalesced=False, sequence_number=p.sequence_number,
                    status="sent", timestamp=time.time(),
                ))
            else:
                self._scheduler.confirm_failed(p.position, "transport send failed")
                self._dirty_regions.mark_failed(p.position, "transport send failed")
                results.append(DynamicUpdateResult(
                    success=False, device_id=self._device_id,
                    profile_id=p.profile_id, position=p.position,
                    image_sha256=p.image_sha256, duplicate_suppressed=False,
                    coalesced=False, sequence_number=p.sequence_number,
                    status="failed", error="transport send failed",
                    timestamp=time.time(),
                ))
        return results

    def process_callback(
        self,
        position: int,
        processed_image: ProcessedImage,
        flush: bool = True,
    ) -> DynamicUpdateResult:
        """Process a single icon callback end-to-end (request + optional flush)."""
        result = self.request_icon_update(position, processed_image)
        if flush and result.success and result.sequence_number is not None:
            self.flush_pending()
        return result

    # -- clear operations ----------------------------------------------
    def clear_position(self, position: int) -> DynamicUpdateResult:
        """Clear a single position (dirty region + scheduler)."""
        timestamp = time.time()
        if not self._layout.validate_position(position):
            return DynamicUpdateResult(
                success=False, device_id=self._device_id, profile_id=self._profile_id,
                position=position, image_sha256=None, duplicate_suppressed=False,
                coalesced=False, sequence_number=None, status="invalid_position",
                error=f"Invalid position {position}", timestamp=timestamp,
            )

        # Cancel any pending update for this position
        self._scheduler.cancel(position)

        # Mark dirty with a clear payload (black RGB565)
        from .image_processor import ImageProcessor
        processor = ImageProcessor()
        clear_image = processor.process_clear(position, timestamp)
        self._dirty_regions.mark_dirty(position, clear_image)

        # Send clear via transport
        ok = self._transport.clear_region(position)
        if ok:
            self._dirty_regions.mark_sent(position)
            self._scheduler.confirm_sent(position, clear_image.sha256)
            # Also clear in legacy backend cache/state
            self._backend.icon_cache.clear_position(
                self._device_id, self._profile_id, position
            )
            self._backend.state_manager.clear_image(
                self._device_id, self._profile_id, position
            )
        return DynamicUpdateResult(
            success=ok, device_id=self._device_id, profile_id=self._profile_id,
            position=position, image_sha256=clear_image.sha256,
            duplicate_suppressed=False, coalesced=False, sequence_number=None,
            status="cleared" if ok else "failed",
            error=None if ok else "clear failed", timestamp=timestamp,
        )

    def clear_all(self) -> List[DynamicUpdateResult]:
        """Clear all positions."""
        results = []
        for pos in range(self._layout.TOTAL_POSITIONS):
            results.append(self.clear_position(pos))
        return results

    # -- profile handling ----------------------------------------------
    def switch_profile(self, new_profile_id: str) -> List[int]:
        """Handle profile change: invalidate stale updates, clear positions."""
        cleared = self._scheduler.switch_profile(new_profile_id)
        # Clear dirty regions for old profile
        self._dirty_regions.clear_profile()
        # Clear legacy backend cache for old profile
        self._backend.icon_cache.clear_profile(self._device_id, self._profile_id)
        self._profile_id = new_profile_id
        self._scheduler.set_profile_id(new_profile_id)
        # Reconnect transport with new profile
        self._transport.disconnect()
        self._transport.connect(self._device_id, new_profile_id)
        return sorted(cleared)

    # -- reconnect recovery --------------------------------------------
    def handle_reconnect(self) -> dict:
        """Handle transport reconnect recovery.

        1. Preserve desired icon state (scheduler desired_sha unchanged).
        2. Detect transport reconnect.
        3. Rebuild dirty positions (desired != submitted).
        4. Resubmit latest desired state.
        5. Suppress stale updates.
        """
        before_connected = self._transport.is_connected()
        self._transport.disconnect()
        self._transport.connect(self._device_id, self._profile_id)

        # Rebuild desired state: positions where desired != submitted
        resubmit_positions = self._scheduler.rebuild_desired_state()

        # Flush pending (which now includes rebuilt desired state)
        results = self.flush_pending()

        return {
            "reconnected": True,
            "was_connected_before": before_connected,
            "resubmit_positions": resubmit_positions,
            "results": [
                {
                    "position": r.position,
                    "success": r.success,
                    "sha": r.image_sha256,
                    "status": r.status,
                }
                for r in results
            ],
        }

    # -- diagnostics & traces ------------------------------------------
    def get_diagnostics(self) -> dict:
        return {
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "transport": self._transport.get_diagnostics(),
            "scheduler": self._scheduler.get_diagnostics(),
            "dirty_regions": self._dirty_regions.get_diagnostics(),
            "update_count": self._update_count,
        }

    def export_transport_trace(self, path: str) -> None:
        self._transport.export_trace(path)

    def export_scheduler_trace(self, path: str) -> None:
        self._scheduler.export_scheduler_trace(path)

    def export_dirty_regions(self, path: str) -> None:
        self._dirty_regions.export_dirty_regions(path)
