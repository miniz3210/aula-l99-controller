"""Mock Bitfocus Companion transport for offline testing.

Deterministic mock transport that records dispatched requests without network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from aula_bridge.provider import ProviderEvent


@dataclass(frozen=True)
class CompanionRequest:
    """Record of a request sent to the mock transport."""

    action_id: str
    event: ProviderEvent
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompanionResponse:
    """Mock response from the transport."""

    success: bool
    action_id: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class MockCompanionTransport:
    """Deterministic mock transport for Bitfocus Companion integration.

    Records all dispatched requests in order. Supports configurable
    success/failure/timeout responses for testing. No network I/O.
    """

    def __init__(
        self,
        default_success: bool = True,
        fail_on_action_ids: Optional[List[str]] = None,
        timeout_on_action_ids: Optional[List[str]] = None,
    ) -> None:
        """Initialize mock transport.

        Args:
            default_success: Default response for unmatched action IDs.
            fail_on_action_ids: Action IDs that should return failure.
            timeout_on_action_ids: Action IDs that should simulate timeout.
        """
        self._sent: List[CompanionRequest] = []
        self._responses: Dict[str, CompanionResponse] = {}
        self._default_success = default_success
        self._fail_on_action_ids = set(fail_on_action_ids or [])
        self._timeout_on_action_ids = set(timeout_on_action_ids or [])

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        """Record a dispatched action.

        Args:
            command: The action command (e.g., "numpad_1_press").
            payload: The action payload (currently unused, kept for compatibility).
            event: The source ProviderEvent.
        """
        # Determine response for this action
        action_id = command

        # Use pre-configured response if it exists, otherwise compute from config
        if action_id not in self._responses:
            if action_id in self._fail_on_action_ids:
                response = CompanionResponse(
                    success=False,
                    action_id=action_id,
                    error_code="ACTION_FAILED",
                    error_message=f"Mock failure for {action_id}",
                )
            elif action_id in self._timeout_on_action_ids:
                response = CompanionResponse(
                    success=False,
                    action_id=action_id,
                    error_code="TIMEOUT",
                    error_message=f"Mock timeout for {action_id}",
                )
            else:
                response = CompanionResponse(
                    success=self._default_success,
                    action_id=action_id,
                )
            self._responses[action_id] = response

        # Record the request with full metadata
        metadata = {
            "payload": payload,
            "event_type": event.event,
            "duration_ms": event.duration_ms,
            "device": event.device,
            "seq": event.seq,
        }
        request = CompanionRequest(
            action_id=action_id,
            event=event,
            metadata=metadata,
        )
        self._sent.append(request)

    def flush(self) -> None:
        """Flush any buffered commands (no-op for mock)."""
        pass

    def close(self) -> None:
        """Close the transport (no-op for mock)."""
        pass

    @property
    def sent_requests(self) -> Sequence[CompanionRequest]:
        """Return all recorded requests in dispatch order."""
        return tuple(self._sent)

    @property
    def sent_action_ids(self) -> List[str]:
        """Return action IDs in dispatch order."""
        return [req.action_id for req in self._sent]

    def get_response(self, action_id: str) -> CompanionResponse:
        """Get the mock response for an action ID."""
        return self._responses.get(
            action_id,
            CompanionResponse(success=self._default_success, action_id=action_id),
        )

    def clear(self) -> None:
        """Clear all recorded requests and responses."""
        self._sent.clear()
        self._responses.clear()

    def set_failure(self, action_id: str, error_code: str = "ACTION_FAILED", error_message: str = "") -> None:
        """Configure a specific action ID to return failure."""
        self._fail_on_action_ids.add(action_id)
        self._responses[action_id] = CompanionResponse(
            success=False,
            action_id=action_id,
            error_code=error_code,
            error_message=error_message or f"Mock failure for {action_id}",
        )

    def set_timeout(self, action_id: str, error_message: str = "") -> None:
        """Configure a specific action ID to return timeout."""
        self._timeout_on_action_ids.add(action_id)
        self._responses[action_id] = CompanionResponse(
            success=False,
            action_id=action_id,
            error_code="TIMEOUT",
            error_message=error_message or f"Mock timeout for {action_id}",
        )

    def set_success(self, action_id: str) -> None:
        """Configure a specific action ID to return success."""
        self._fail_on_action_ids.discard(action_id)
        self._timeout_on_action_ids.discard(action_id)
        self._responses[action_id] = CompanionResponse(
            success=True,
            action_id=action_id,
        )

    def verify_request_sequence(self, expected_action_ids: List[str]) -> bool:
        """Verify that dispatched actions match expected sequence."""
        actual = self.sent_action_ids
        return actual == expected_action_ids

    def count_requests_for_key(self, logical_key: str) -> int:
        """Count how many requests were sent for a specific logical key."""
        return sum(1 for req in self._sent if req.event.key == logical_key)

    def get_requests_for_device(self, device: str) -> List[CompanionRequest]:
        """Get all requests from a specific device."""
        return [req for req in self._sent if req.event.device == device]

    def get_last_request(self) -> Optional[CompanionRequest]:
        """Get the most recent request, or None if none sent."""
        return self._sent[-1] if self._sent else None

    def __len__(self) -> int:
        return len(self._sent)