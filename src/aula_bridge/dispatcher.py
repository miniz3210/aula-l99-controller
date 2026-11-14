"""Deterministic offline action dispatcher for the AULA L99 bridge.

Uses dependency-injected Transport interface with no actual I/O.
Preserves ProviderEvent fields and deterministic ordering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Protocol, Sequence

from aula_bridge.provider import ProviderEvent
from aula_bridge.action_mapping import ActionMap, ActionMapEntry


class Transport(Protocol):
    """Dependency-injected transport interface. No actual I/O performed."""

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        """Send a command with payload, preserving the source event.

        Args:
            command: The action command to send.
            payload: The action payload.
            event: The source ProviderEvent (not mutated).
        """
        ...

    def flush(self) -> None:
        """Flush any buffered commands."""
        ...

    def close(self) -> None:
        """Close the transport."""
        ...


class MockTransport:
    """Mock transport for testing. Records all sent commands for verification."""

    def __init__(self) -> None:
        self._sent: List[_SentAction] = []

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        self._sent.append(_SentAction(command, payload, event))

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass

    @property
    def sent_actions(self) -> Sequence[_SentAction]:
        return tuple(self._sent)

    def clear(self) -> None:
        self._sent.clear()


@dataclass(frozen=True)
class _SentAction:
    command: str
    payload: str
    event: ProviderEvent


@dataclass(frozen=True)
class DispatchedAction:
    """Result of a successful dispatch, preserving all source event fields."""

    command: str
    payload: str
    source_event: ProviderEvent
    map_entry: ActionMapEntry


class ActionDispatcher:
    """Deterministic offline action dispatcher.

    Maps ProviderEvent to actions via ActionMap, sends via Transport.
    No mutation of ProviderEvent. Deterministic ordering preserved.
    """

    def __init__(
        self,
        transport: Transport,
        action_map: Optional[ActionMap] = None,
    ) -> None:
        """Initialize dispatcher with transport and optional custom action map.

        Args:
            transport: Dependency-injected transport (no actual I/O).
            action_map: Optional custom action map. Uses default if None.
        """
        self._transport = transport
        self._action_map = action_map if action_map is not None else ActionMap()

    def dispatch(self, event: ProviderEvent) -> Optional[DispatchedAction]:
        """Dispatch a single ProviderEvent to an action.

        Args:
            event: The ProviderEvent to dispatch. Not mutated.

        Returns:
            DispatchedAction if mapped and sent, None if no-op.
        """
        # Only process supported action events
        if event.event not in {"short_press", "hold", "secondary_hold"}:
            return None

        # Look up action mapping
        entry = self._action_map.lookup(event.key, event.event)
        if entry is None:
            return None

        # Send via transport (no mutation of event)
        self._transport.send(entry.command, entry.payload, event)

        return DispatchedAction(
            command=entry.command,
            payload=entry.payload,
            source_event=event,
            map_entry=entry,
        )

    def dispatch_batch(self, events: Sequence[ProviderEvent]) -> List[DispatchedAction]:
        """Dispatch a batch of events in deterministic order.

        Args:
            events: Sequence of ProviderEvent to dispatch.

        Returns:
            List of DispatchedAction for each successful dispatch.
        """
        results: List[DispatchedAction] = []
        for event in events:
            dispatched = self.dispatch(event)
            if dispatched is not None:
                results.append(dispatched)
        return results

    def flush(self) -> None:
        """Flush the underlying transport."""
        self._transport.flush()

    def close(self) -> None:
        """Close the underlying transport."""
        self._transport.close()

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def action_map(self) -> ActionMap:
        return self._action_map