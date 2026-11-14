"""Unit tests for CompanionDispatchAdapter.

Uses fake HTTP sender only. No real network access, no Companion connection.
"""

import os
import sys
import unittest
import logging
from typing import Mapping

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.provider import ProviderEvent
from aula_bridge.companion_types import ButtonLocation
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
    HttpSender,
)
from aula_bridge.dispatcher import Transport
from aula_bridge.companion_dispatch_adapter import CompanionDispatchAdapter


class FakeHttpSender:
    """Fake HTTP sender for testing."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []
        self._response_map: dict[tuple[str, str], HttpResponse] = {}
        self._default_response: HttpResponse = HttpResponse(status_code=200, success=True)
        self._raise_on_call: Exception | None = None

    def set_response(self, method: str, url: str, response: HttpResponse) -> None:
        self._response_map[(method, url)] = response

    def set_default_response(self, response: HttpResponse) -> None:
        self._default_response = response

    def set_raise(self, exc: Exception) -> None:
        self._raise_on_call = exc

    def send(self, method: str, url: str, timeout: float) -> HttpResponse:
        self.calls.append((method, url, timeout))

        if self._raise_on_call:
            raise self._raise_on_call

        return self._response_map.get((method, url), self._default_response)

    def clear(self) -> None:
        self.calls.clear()
        self._response_map.clear()
        self._raise_on_call = None


class TestCompanionDispatchAdapter(unittest.TestCase):
    """Tests for CompanionDispatchAdapter."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(http_sender=self.sender)

        # Create button mapping for numpad keys
        self.button_mapping: Mapping[str, ButtonLocation] = {
            "numpad_1": ButtonLocation(page=1, row=0, column=0),
            "numpad_2": ButtonLocation(page=1, row=0, column=1),
            "numpad_3": ButtonLocation(page=1, row=0, column=2),
            "numpad_4": ButtonLocation(page=1, row=1, column=0),
            "numpad_5": ButtonLocation(page=1, row=1, column=1),
            "numpad_6": ButtonLocation(page=1, row=1, column=2),
            "numpad_7": ButtonLocation(page=1, row=2, column=0),
            "numpad_8": ButtonLocation(page=1, row=2, column=1),
            "numpad_9": ButtonLocation(page=1, row=2, column=2),
            "numpad_0": ButtonLocation(page=1, row=3, column=1),
            "numpad_enter": ButtonLocation(page=1, row=3, column=2),
            "numpad_plus": ButtonLocation(page=1, row=0, column=3),
            "numpad_minus": ButtonLocation(page=1, row=1, column=3),
            "numpad_multiply": ButtonLocation(page=1, row=2, column=3),
            "numpad_divide": ButtonLocation(page=1, row=3, column=3),
            "numpad_num": ButtonLocation(page=1, row=3, column=0),
            "numpad_decimal_delete": ButtonLocation(page=2, row=0, column=0),
        }

        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=self.button_mapping,
        )

    def _make_event(
        self,
        event_type: str = "short_press",
        key: str = "numpad_1",
        device: str = "0C45:800A",
        duration_ms: int = 100,
        seq: int = 1,
    ) -> ProviderEvent:
        return ProviderEvent(
            event=event_type,
            key=key,
            device=device,
            duration_ms=duration_ms,
            seq=seq,
        )

    # ==================== Event type filtering ====================

    def test_short_press_processed(self) -> None:
        """short_press events are processed and sent to HTTP transport."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="short_press", key="numpad_1", seq=1)

        self.adapter.send("test_cmd", "test_payload", event)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/location/1/0/0/press", url)

    def test_hold_ignored(self) -> None:
        """hold events are ignored (no HTTP request)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="hold", key="numpad_1", seq=1)

        self.adapter.send("test_cmd", "test_payload", event)

        self.assertEqual(len(self.sender.calls), 0)

    def test_secondary_hold_ignored(self) -> None:
        """secondary_hold events are ignored (no HTTP request)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="secondary_hold", key="numpad_1", seq=1)

        self.adapter.send("test_cmd", "test_payload", event)

        self.assertEqual(len(self.sender.calls), 0)

    def test_key_down_ignored(self) -> None:
        """key_down events are ignored (no HTTP request)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="key_down", key="numpad_1", seq=1)

        self.adapter.send("test_cmd", "test_payload", event)

        self.assertEqual(len(self.sender.calls), 0)

    def test_key_up_ignored(self) -> None:
        """key_up events are ignored (no HTTP request)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="key_up", key="numpad_1", seq=1)

        self.adapter.send("test_cmd", "test_payload", event)

        self.assertEqual(len(self.sender.calls), 0)

    def test_repeat_ignored_ignored(self) -> None:
        """repeat_ignored events are ignored (no HTTP request)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="repeat_ignored", key="numpad_1", seq=1)

        self.adapter.send("test_cmd", "test_payload", event)

        self.assertEqual(len(self.sender.calls), 0)

    # ==================== Mapping lookup ====================

    def test_mapped_short_press_sends_request(self) -> None:
        """Mapped short_press sends HTTP press request."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="short_press", key="numpad_5", seq=1)

        self.adapter.send("cmd", "payload", event)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/location/1/1/1/press", url)

    def test_unmapped_short_press_no_request(self) -> None:
        """Unmapped short_press produces no HTTP request."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(event_type="short_press", key="unknown_key", seq=1)

        self.adapter.send("cmd", "payload", event)

        self.assertEqual(len(self.sender.calls), 0)

    def test_no_default_mapping_invented(self) -> None:
        """Adapter never invents default mappings for unmapped keys."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        # Keys not in button_mapping should produce no request
        unmapped_keys = ["numpad_unknown", "key_a", "f1", "escape"]
        for key in unmapped_keys:
            with self.subTest(key=key):
                self.sender.clear()
                event = self._make_event(event_type="short_press", key=key, seq=1)
                self.adapter.send("cmd", "payload", event)
                self.assertEqual(len(self.sender.calls), 0)

    # ==================== Event field preservation ====================

    def test_device_identity_preserved(self) -> None:
        """Source device identity is preserved in logging (not sent to HTTP)."""
        # The adapter logs the device but doesn't send it in HTTP request
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(device="EEEF:268A", seq=1)

        self.adapter.send("cmd", "payload", event)

        # Request is made (so device didn't block it)
        self.assertEqual(len(self.sender.calls), 1)

    def test_event_sequence_preserved(self) -> None:
        """Event sequence number is preserved in logging."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(seq=42)

        self.adapter.send("cmd", "payload", event)

        self.assertEqual(len(self.sender.calls), 1)
        # seq is logged but not sent in HTTP - verify by checking adapter behavior
        # The adapter processes the event without dropping it
        self.assertEqual(event.seq, 42)  # Event not mutated

    def test_no_event_mutation(self) -> None:
        """ProviderEvent is not mutated during processing."""
        original_event = self._make_event(
            event_type="short_press",
            key="numpad_1",
            device="0C45:800A",
            duration_ms=150,
            seq=5,
        )
        original_dict = original_event.to_dict()

        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        self.adapter.send("cmd", "payload", original_event)

        self.assertEqual(original_event.to_dict(), original_dict)
        self.assertEqual(original_event.seq, 5)
        self.assertEqual(original_event.duration_ms, 150)

    # ==================== Dispatch ordering ====================

    def test_dispatch_ordering_preserved(self) -> None:
        """Multiple events processed in order preserve ordering."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
            self._make_event(key="numpad_3", seq=3),
        ]

        for event in events:
            self.adapter.send("cmd", "payload", event)

        self.assertEqual(len(self.sender.calls), 3)
        # Verify order by URL sequence
        urls = [call[1] for call in self.sender.calls]
        self.assertIn("/api/location/1/0/0/press", urls[0])  # numpad_1
        self.assertIn("/api/location/1/0/1/press", urls[1])  # numpad_2
        self.assertIn("/api/location/1/0/2/press", urls[2])  # numpad_3

    # ==================== HTTP response handling ====================

    def test_http_200_accepted(self) -> None:
        """HTTP 200 is logged as accepted."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        self.assertEqual(len(self.sender.calls), 1)
        log_output = "\n".join(cm.output)
        self.assertIn("status=200", log_output)
        self.assertIn("success=True", log_output)

    def test_http_204_no_control(self) -> None:
        """HTTP 204 returns NO_CONTROL error code."""
        self.sender.set_default_response(HttpResponse(status_code=204, success=False))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=204", log_output)
        self.assertIn("success=False", log_output)
        self.assertIn("NO_CONTROL", log_output)

    def test_http_400_invalid_location(self) -> None:
        """HTTP 400 returns INVALID_LOCATION error code."""
        self.sender.set_default_response(HttpResponse(status_code=400, success=False))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=400", log_output)
        self.assertIn("INVALID_LOCATION", log_output)

    def test_http_403_forbidden(self) -> None:
        """HTTP 403 returns FORBIDDEN error code."""
        self.sender.set_default_response(HttpResponse(status_code=403, success=False))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=403", log_output)
        self.assertIn("FORBIDDEN", log_output)

    def test_http_500_server_error(self) -> None:
        """HTTP 500 returns SERVER_ERROR error code."""
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=500", log_output)
        self.assertIn("SERVER_ERROR", log_output)

    def test_connection_refused(self) -> None:
        """Connection refused returns CONNECTION_REFUSED error code."""
        self.sender.set_raise(ConnectionRefusedError("Connection refused"))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("CONNECTION_REFUSED", log_output)

    def test_timeout(self) -> None:
        """Timeout returns TIMEOUT error code."""
        self.sender.set_raise(TimeoutError("Request timeout"))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("TIMEOUT", log_output)

    # ==================== Transport protocol compatibility ====================

    def test_transport_protocol_send_signature(self) -> None:
        """Adapter implements Transport.send(command, payload, event)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(seq=1)

        # Should not raise
        self.adapter.send("command", "payload", event)

    def test_transport_protocol_flush(self) -> None:
        """Adapter implements Transport.flush()."""
        # Should not raise
        self.adapter.flush()

    def test_transport_protocol_close(self) -> None:
        """Adapter implements Transport.close()."""
        # Should not raise
        self.adapter.close()

    # ==================== No retries, no buffering, no threads ====================

    def test_no_automatic_retries(self) -> None:
        """Failed requests are not retried automatically."""
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = self._make_event(key="numpad_1", seq=1)

        self.adapter.send("cmd", "payload", event)

        # Only one call made
        self.assertEqual(len(self.sender.calls), 1)

    def test_no_event_buffering(self) -> None:
        """Adapter doesn't buffer events - each send is independent."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
            self._make_event(key="numpad_3", seq=3),
        ]

        for event in events:
            self.adapter.send("cmd", "payload", event)

        # Each event made exactly one call (if mapped)
        self.assertEqual(len(self.sender.calls), 3)

    def test_no_background_threads(self) -> None:
        """Adapter uses no background threads (synchronous call)."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(key="numpad_1", seq=1)

        # Synchronous call - if it returned, no background thread is running
        self.adapter.send("cmd", "payload", event)
        self.assertEqual(len(self.sender.calls), 1)

    # ==================== Logging ====================

    def test_logging_includes_key_device_seq_event(self) -> None:
        """Log includes event.key, event.device, event.seq, event.event."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = self._make_event(
            event_type="short_press",
            key="numpad_7",
            device="EEEF:268A",
            seq=99,
        )

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("key=numpad_7", log_output)
        self.assertIn("device=EEEF:268A", log_output)
        self.assertIn("seq=99", log_output)
        self.assertIn("event=short_press", log_output)

    def test_logging_includes_http_status_error_code(self) -> None:
        """Log includes HTTP status and error code."""
        self.sender.set_default_response(HttpResponse(status_code=400, success=False, error_code="INVALID_LOCATION"))
        event = self._make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            self.adapter.send("cmd", "payload", event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=400", log_output)
        self.assertIn("error_code=INVALID_LOCATION", log_output)

    # ==================== Transport integration ====================

    def test_adapter_implements_transport_protocol(self) -> None:
        """Adapter can be used as Transport in ActionDispatcher."""
        from aula_bridge.dispatcher import ActionDispatcher, Transport

        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        dispatcher = ActionDispatcher(transport=self.adapter)
        event = self._make_event(event_type="short_press", key="numpad_1", seq=1)

        result = dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(len(self.sender.calls), 1)

    def test_ignored_events_not_sent_to_transport(self) -> None:
        """Ignored events (hold, key_down, etc.) don't reach HTTP transport."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        ignored_events = [
            self._make_event(event_type="hold", key="numpad_1", seq=1),
            self._make_event(event_type="key_down", key="numpad_1", seq=2),
            self._make_event(event_type="key_up", key="numpad_1", seq=3),
            self._make_event(event_type="repeat_ignored", key="numpad_1", seq=4),
            self._make_event(event_type="secondary_hold", key="numpad_1", seq=5),
        ]

        for event in ignored_events:
            self.adapter.send("cmd", "payload", event)

        self.assertEqual(len(self.sender.calls), 0)


if __name__ == "__main__":
    # Configure logging for test output
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(name)s - %(levelname)s - %(message)s",
    )
    unittest.main()