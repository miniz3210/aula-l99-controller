"""Companion Dispatch Adapter connecting ActionDispatcher to Companion HTTP Core.

Thin adapter that processes short_press events, looks up button locations,
and delegates HTTP press to CompanionHttpTransport.
"""

from __future__ import annotations

import logging
from typing import Mapping, Optional

from aula_bridge.provider import ProviderEvent
from aula_bridge.companion_types import ButtonLocation
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
)
from aula_bridge.dispatcher import Transport

logger = logging.getLogger(__name__)


class CompanionDispatchAdapter:
    """Adapter connecting ActionDispatcher to Companion HTTP Core.

    Implements the Transport protocol for the ActionDispatcher.
    Only processes short_press events. All other event types are ignored.
    """

    def __init__(
        self,
        http_transport: CompanionHttpTransport,
        button_mapping: Mapping[str, ButtonLocation],
    ) -> None:
        """Initialize the adapter.

        Args:
            http_transport: Companion HTTP transport for sending press requests.
            button_mapping: Immutable mapping from logical key to ButtonLocation.
        """
        self._http_transport = http_transport
        self._button_mapping = button_mapping

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        """Process an event from ActionDispatcher.

        Only short_press events are processed. All other event types are ignored.
        Button location is looked up from the mapping. Missing mapping produces
        no HTTP request. Event ordering is preserved, no mutation, no buffering.

        Args:
            command: Action command (ignored, derived from event).
            payload: Action payload (ignored).
            event: Source ProviderEvent (not mutated).
        """
        # Only process short_press events
        if event.event != "short_press":
            logger.debug(
                "Ignoring event type: key=%s device=%s seq=%d event=%s",
                event.key,
                event.device,
                event.seq,
                event.event,
            )
            return

        # Look up button location
        location = self._button_mapping.get(event.key)
        if location is None:
            logger.debug(
                "No button mapping: key=%s device=%s seq=%d event=%s",
                event.key,
                event.device,
                event.seq,
                event.event,
            )
            return

        # Send press request
        response = self._http_transport.press(location)

        # Log result
        self._log_response(event, response)

    def _log_response(self, event: ProviderEvent, response: HttpResponse) -> None:
        """Log the HTTP response with event context."""
        logger.info(
            "HTTP response: key=%s device=%s seq=%d event=%s status=%d success=%s error_code=%s",
            event.key,
            event.device,
            event.seq,
            event.event,
            response.status_code,
            response.success,
            response.error_code,
        )

    def flush(self) -> None:
        """Flush any buffered commands. No-op (no buffering)."""
        pass

    def close(self) -> None:
        """Close the transport. No-op (no persistent connections)."""
        pass