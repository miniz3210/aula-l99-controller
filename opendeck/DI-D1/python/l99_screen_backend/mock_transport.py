"""Mock screen transport for recording image sends without hardware commands."""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum

from .image_processor import ProcessedImage
from .state_manager import StateManager, PhysicalConfirmStatus
from .layout import LayoutModel


class TransportStatus(str, Enum):
    """Mock transport operation status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CLEARED = "cleared"


@dataclass
class TransportRecord:
    """Record of a single transport operation."""
    timestamp: float
    device_id: str
    profile_id: str
    position: int
    image_sha256: str
    payload_length: int
    operation: str  # "send_image" or "clear_image"
    status: TransportStatus
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class MockScreenTransport:
    """Mock screen transport that records operations without issuing hardware commands.
    
    Does NOT implement unknown L99 serial commands.
    Does NOT claim arbitrary runtime image upload is supported.
    """

    def __init__(self, layout: LayoutModel, state_manager: StateManager) -> None:
        self._layout = layout
        self._state_manager = state_manager
        self._connected = False
        self._device_id: Optional[str] = None
        self._profile_id: Optional[str] = None
        self._records: List[TransportRecord] = []
        self._max_records = 1000

    def connect(self, device_id: str, profile_id: str) -> bool:
        """Simulate connection to screen."""
        if self._connected:
            return False
        self._connected = True
        self._device_id = device_id
        self._profile_id = profile_id
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=device_id,
            profile_id=profile_id,
            position=-1,
            image_sha256="",
            payload_length=0,
            operation="connect",
            status=TransportStatus.CONNECTED
        ))
        return True

    def disconnect(self) -> bool:
        """Simulate disconnection."""
        if not self._connected:
            return False
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "",
            profile_id=self._profile_id or "",
            position=-1,
            image_sha256="",
            payload_length=0,
            operation="disconnect",
            status=TransportStatus.DISCONNECTED
        ))
        self._connected = False
        self._device_id = None
        self._profile_id = None
        return True

    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected

    def send_image(self, position: int, processed_image: ProcessedImage) -> bool:
        """Record image send operation (mock - no actual hardware command).
        
        Returns True if recorded successfully.
        """
        if not self._connected:
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "",
                profile_id=self._profile_id or "",
                position=position,
                image_sha256=processed_image.sha256,
                payload_length=len(processed_image.rgb565_data),
                operation="send_image",
                status=TransportStatus.FAILED,
                error_message="Transport not connected"
            ))
            return False

        if not self._layout.validate_position(position):
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "",
                profile_id=self._profile_id or "",
                position=position,
                image_sha256=processed_image.sha256,
                payload_length=len(processed_image.rgb565_data),
                operation="send_image",
                status=TransportStatus.FAILED,
                error_message=f"Invalid position {position}"
            ))
            return False

        # Record the send
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "",
            profile_id=self._profile_id or "",
            position=position,
            image_sha256=processed_image.sha256,
            payload_length=len(processed_image.rgb565_data),
            operation="send_image",
            status=TransportStatus.SENT
        ))

        # Update state manager to SENT_UNCONFIRMED
        if self._device_id and self._profile_id:
            self._state_manager.mark_sent_unconfirmed(
                self._device_id, self._profile_id, position
            )

        return True

    def clear_image(self, position: int) -> bool:
        """Record clear image operation."""
        if not self._connected:
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "",
                profile_id=self._profile_id or "",
                position=position,
                image_sha256="",
                payload_length=0,
                operation="clear_image",
                status=TransportStatus.FAILED,
                error_message="Transport not connected"
            ))
            return False

        if not self._layout.validate_position(position):
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "",
                profile_id=self._profile_id or "",
                position=position,
                image_sha256="",
                payload_length=0,
                operation="clear_image",
                status=TransportStatus.FAILED,
                error_message=f"Invalid position {position}"
            ))
            return False

        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "",
            profile_id=self._profile_id or "",
            position=position,
            image_sha256="",
            payload_length=0,
            operation="clear_image",
            status=TransportStatus.CLEARED
        ))

        if self._device_id and self._profile_id:
            self._state_manager.set_physical_status(
                self._device_id, self._profile_id, position,
                PhysicalConfirmStatus.SENT_UNCONFIRMED
            )

        return True

    def restore_cached_state(
        self,
        device_id: str,
        profile_id: str,
        cached_images: Optional[Dict[int, 'ProcessedImage']] = None
    ) -> int:
        """Simulate restoring all cached images on reconnect.
        
        Returns number of images restored.
        
        Args:
            device_id: Device identifier
            profile_id: Profile identifier
            cached_images: Optional position -> ProcessedImage mapping.
                           When provided, resends actual cached payloads on reconnect.
        """
        if not self._connected or self._device_id != device_id or self._profile_id != profile_id:
            return 0

        restored = 0

        if cached_images:
            # Re-submit cached image payloads on reconnect (desired state preserved)
            for position in sorted(cached_images.keys()):
                processed_image = cached_images[position]
                self._record(TransportRecord(
                    timestamp=time.time(),
                    device_id=device_id,
                    profile_id=profile_id,
                    position=position,
                    image_sha256=processed_image.sha256,
                    payload_length=len(processed_image.rgb565_data),
                    operation="restore_image",
                    status=TransportStatus.SENT
                ))
                restored += 1
        else:
            # Fallback: restore from PENDING states
            states = self._state_manager.get_states_for_transport(device_id, profile_id)
            for record in states:
                if record.image_sha256 and record.logical_state.value != "off":
                    self._record(TransportRecord(
                        timestamp=time.time(),
                        device_id=device_id,
                        profile_id=profile_id,
                        position=record.position,
                        image_sha256=record.image_sha256,
                        payload_length=0,
                        operation="restore_image",
                        status=TransportStatus.SENT
                    ))
                    restored += 1

        return restored

    def _record(self, record: TransportRecord) -> None:
        """Add record to history with size limit."""
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)

    def get_records(self) -> List[TransportRecord]:
        """Get all transport records."""
        return list(self._records)

    def get_records_for_device(self, device_id: str) -> List[TransportRecord]:
        """Get records for a specific device."""
        return [r for r in self._records if r.device_id == device_id]

    def get_records_for_profile(self, device_id: str, profile_id: str) -> List[TransportRecord]:
        """Get records for a specific device and profile."""
        return [r for r in self._records if r.device_id == device_id and r.profile_id == profile_id]

    def export_trace(self, path: str) -> None:
        """Export transport trace to JSON file."""
        data = {
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "connected": self._connected,
            "record_count": len(self._records),
            "records": [r.to_dict() for r in self._records]
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_stats(self) -> dict:
        """Get transport statistics."""
        stats = {
            "connected": self._connected,
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "total_records": len(self._records),
            "operations": {}
        }
        for record in self._records:
            op = record.operation
            if op not in stats["operations"]:
                stats["operations"][op] = {"sent": 0, "failed": 0, "cleared": 0}
            stats["operations"][op][record.status.value] = stats["operations"][op].get(record.status.value, 0) + 1
        return stats