"""Logical state management for OpenDeck buttons (separate from physical confirmation)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum
from collections import OrderedDict

from .layout import LayoutModel, ButtonLayout


class LogicalButtonState(str, Enum):
    """Logical button states from OpenDeck perspective."""
    OFF = "off"
    ON = "on"
    ERROR = "error"
    UNKNOWN = "unknown"


class PhysicalConfirmStatus(str, Enum):
    """Physical screen confirmation status."""
    PENDING = "pending"
    SENT_UNCONFIRMED = "sent_unconfirmed"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class ButtonStateRecord:
    """Complete state record for a single button."""
    position: int
    logical_state: LogicalButtonState = LogicalButtonState.UNKNOWN
    physical_status: PhysicalConfirmStatus = PhysicalConfirmStatus.NOT_APPLICABLE
    image_sha256: Optional[str] = None
    profile_id: str = ""
    device_id: str = ""
    last_updated: float = field(default_factory=time.time)
    update_count: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "position": self.position,
            "logical_state": self.logical_state.value,
            "physical_status": self.physical_status.value,
            "image_sha256": self.image_sha256,
            "profile_id": self.profile_id,
            "device_id": self.device_id,
            "last_updated": self.last_updated,
            "update_count": self.update_count,
            "error_message": self.error_message
        }


class StateManager:
    """Manages logical button states separate from physical confirmation."""

    def __init__(self, layout: LayoutModel) -> None:
        self._layout = layout
        self._states: Dict[str, Dict[str, Dict[int, ButtonStateRecord]]] = {}  # device -> profile -> position -> state

    def _get_device_states(self, device_id: str) -> Dict[str, Dict[int, ButtonStateRecord]]:
        if device_id not in self._states:
            self._states[device_id] = {}
        return self._states[device_id]

    def _get_profile_states(self, device_id: str, profile_id: str) -> Dict[int, ButtonStateRecord]:
        device_states = self._get_device_states(device_id)
        if profile_id not in device_states:
            device_states[profile_id] = {}
            # Initialize all positions to UNKNOWN
            for pos in range(self._layout.TOTAL_POSITIONS):
                device_states[profile_id][pos] = ButtonStateRecord(
                    position=pos,
                    logical_state=LogicalButtonState.UNKNOWN,
                    profile_id=profile_id,
                    device_id=device_id
                )
        return device_states[profile_id]

    def set_logical_state(
        self,
        device_id: str,
        profile_id: str,
        position: int,
        state: LogicalButtonState,
        image_sha256: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Set logical button state (from OpenDeck image update)."""
        if not self._layout.validate_position(position):
            return False

        profile_states = self._get_profile_states(device_id, profile_id)
        record = profile_states[position]
        record.logical_state = state
        record.image_sha256 = image_sha256
        record.last_updated = time.time()
        record.update_count += 1
        if error_message:
            record.error_message = error_message
        else:
            record.error_message = None
        # Physical status resets to PENDING when logical state changes
        record.physical_status = PhysicalConfirmStatus.PENDING
        return True

    def set_physical_status(
        self,
        device_id: str,
        profile_id: str,
        position: int,
        status: PhysicalConfirmStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """Set physical confirmation status (from mock transport)."""
        if not self._layout.validate_position(position):
            return False

        profile_states = self._get_profile_states(device_id, profile_id)
        record = profile_states[position]
        record.physical_status = status
        record.last_updated = time.time()
        if error_message:
            record.error_message = error_message
            record.logical_state = LogicalButtonState.ERROR
        return True

    def mark_sent_unconfirmed(
        self,
        device_id: str,
        profile_id: str,
        position: int
    ) -> bool:
        """Mark image as sent to mock transport but not physically confirmed."""
        return self.set_physical_status(
            device_id, profile_id, position,
            PhysicalConfirmStatus.SENT_UNCONFIRMED
        )

    def mark_confirmed(
        self,
        device_id: str,
        profile_id: str,
        position: int
    ) -> bool:
        """Mark image as physically confirmed (not used in mock - for future)."""
        return self.set_physical_status(
            device_id, profile_id, position,
            PhysicalConfirmStatus.CONFIRMED
        )

    def clear_image(
        self,
        device_id: str,
        profile_id: str,
        position: int
    ) -> bool:
        """Clear image - set to OFF state."""
        if not self._layout.validate_position(position):
            return False

        profile_states = self._get_profile_states(device_id, profile_id)
        record = profile_states[position]
        record.logical_state = LogicalButtonState.OFF
        record.image_sha256 = None
        record.last_updated = time.time()
        record.update_count += 1
        record.physical_status = PhysicalConfirmStatus.PENDING
        record.error_message = None
        return True

    def clear_all(
        self,
        device_id: str,
        profile_id: str
    ) -> int:
        """Clear all images for a profile."""
        count = 0
        for pos in range(self._layout.TOTAL_POSITIONS):
            if self.clear_image(device_id, profile_id, pos):
                count += 1
        return count

    def get_state(
        self,
        device_id: str,
        profile_id: str,
        position: int
    ) -> Optional[ButtonStateRecord]:
        """Get button state."""
        device_states = self._states.get(device_id)
        if not device_states:
            return None
        profile_states = device_states.get(profile_id)
        if not profile_states:
            return None
        return profile_states.get(position)

    def get_all_states(self, device_id: str, profile_id: str) -> Dict[int, ButtonStateRecord]:
        """Get all button states for a profile."""
        return self._get_profile_states(device_id, profile_id).copy()

    def get_states_for_transport(self, device_id: str, profile_id: str) -> List[ButtonStateRecord]:
        """Get states that need to be sent to transport (pending)."""
        profile_states = self._get_profile_states(device_id, profile_id)
        result = []
        for pos in range(self._layout.TOTAL_POSITIONS):
            record = profile_states[pos]
            if record.physical_status == PhysicalConfirmStatus.PENDING:
                result.append(record)
        return result

    def get_device_profiles(self, device_id: str) -> List[str]:
        """Get all profile IDs for a device."""
        return list(self._get_device_states(device_id).keys())

    def get_stats(self) -> dict:
        """Get state statistics."""
        stats = {
            "devices": {}
        }
        for device_id, device_states in self._states.items():
            device_stats = {
                "profiles": {},
                "total_buttons": 0,
                "states": {
                    "off": 0,
                    "on": 0,
                    "error": 0,
                    "unknown": 0
                },
                "physical": {
                    "pending": 0,
                    "sent_unconfirmed": 0,
                    "confirmed": 0,
                    "failed": 0,
                    "not_applicable": 0
                }
            }
            for profile_id, profile_states in device_states.items():
                profile_stats = {
                    "positions": {}
                }
                for pos, record in profile_states.items():
                    device_stats["states"][record.logical_state.value] += 1
                    device_stats["physical"][record.physical_status.value] += 1
                    profile_stats["positions"][pos] = record.to_dict()
                device_stats["profiles"][profile_id] = profile_stats
                device_stats["total_buttons"] += len(profile_states)
            stats["devices"][device_id] = device_stats
        return stats