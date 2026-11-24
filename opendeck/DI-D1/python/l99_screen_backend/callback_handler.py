"""OpenDeck SetImageEvent -> ImageUpdateRequest callback handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .backend import ImageUpdateRequest


@dataclass(frozen=True)
class SetImageCallback:
    """Represents a genuine OpenDeck SetImageEvent callback."""

    device_id: str
    position: Optional[int]
    image: Optional[str]  # PNG Data URL, None means clear

    @property
    def is_clear(self) -> bool:
        """True when this callback requests a clear operation."""
        return self.image is None


@dataclass(frozen=True)
class CallbackResult:
    """Result of processing a SetImage callback."""

    accepted: bool
    device_id: str
    position: Optional[int]
    image: Optional[str]
    backend_result: object  # ImageUpdateResult
    error: Optional[str] = None


class CallbackHandler:
    """Translates OpenDeck SetImageEvent callbacks into OD2-B backend requests.

    Contract (OpenAction 2.8 SetImageEvent):
      - device: str   - must equal al-l99-0001
      - position: Optional[int] - 0..15
      - image: Optional[str] - PNG Data URL, None = clear
    """

    DEVICE_ID = "al-l99-0001"
    UNKNOWN_PROFILE = "UNKNOWN_PROFILE"

    def __init__(self, backend, profile_id: Optional[str] = None) -> None:
        self._backend = backend
        self._profile_id = profile_id or self.UNKNOWN_PROFILE

    @property
    def profile_id(self) -> str:
        """Resolved profile identity.

        Profile identity must be resolved from actual available context.
        If unavailable, UNKNOWN_PROFILE is used and the limitation is recorded.
        """
        return self._profile_id

    def handle_callback(self, device_id: str, position: Optional[int], image: Optional[str]) -> CallbackResult:
        """Handle a genuine OpenDeck setImage callback.

        Handles:
          - Some(position), Some(image)  -> set image
          - Some(position), None         -> clear position
          - None, None                   -> clear all
        """
        # Validate device ID
        if device_id != self.DEVICE_ID:
            return CallbackResult(
                accepted=False,
                device_id=device_id,
                position=position,
                image=image,
                backend_result=None,
                error=f"Invalid device ID: {device_id}. Expected {self.DEVICE_ID}"
            )

        # Handle clear all: None, None
        if position is None and image is None:
            return self._handle_clear_all(device_id)

        # Handle clear one: Some(position), None
        if position is not None and image is None:
            return self._handle_clear_position(device_id, position)

        # Handle set image: Some(position), Some(image)
        if position is not None and image is not None:
            return self._handle_set_image(device_id, position, image)

        # Any other combination (e.g. None, Some(image)) is invalid
        return CallbackResult(
            accepted=False,
            device_id=device_id,
            position=position,
            image=image,
            backend_result=None,
            error=f"Invalid callback state: position={position}, image={'present' if image else 'none'}"
        )

    def _handle_set_image(self, device_id: str, position: int, image: str) -> CallbackResult:
        """Process a set-image callback."""
        request = ImageUpdateRequest(
            device_id=device_id,
            profile_id=self.profile_id,
            position=position,
            data_url=image
        )
        result = self._backend.process_image_update(request)
        return CallbackResult(
            accepted=result.success,
            device_id=device_id,
            position=position,
            image=image,
            backend_result=result,
            error=result.error
        )

    def _handle_clear_position(self, device_id: str, position: int) -> CallbackResult:
        """Process a clear-position callback."""
        request = ImageUpdateRequest(
            device_id=device_id,
            profile_id=self.profile_id,
            position=position,
            data_url=None
        )
        result = self._backend.process_image_update(request)
        return CallbackResult(
            accepted=result.success,
            device_id=device_id,
            position=position,
            image=None,
            backend_result=result,
            error=result.error
        )

    def _handle_clear_all(self, device_id: str) -> CallbackResult:
        """Process a clear-all callback (None, None)."""
        results = self._backend.process_clear_all(device_id, self.profile_id)
        all_success = all(r.success for r in results)
        return CallbackResult(
            accepted=all_success,
            device_id=device_id,
            position=None,
            image=None,
            backend_result=results,
            error=None if all_success else "Some clears failed"
        )

    def set_profile_id(self, profile_id: str) -> None:
        """Update the resolved profile identity."""
        self._profile_id = profile_id
