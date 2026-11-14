"""Offline end-to-end tests for the Companion integration stack.

Builds the complete offline chain:

    ProviderEvent
      -> ActionDispatcher
      -> CompanionDispatchAdapter
      -> CompanionHttpTransport
      -> FakeHttpSender

Uses the actual JSON mapping loader (load_companion_button_mapping) with
temporary JSON configuration files and a deterministic FakeHttpSender.

No real network access, no Companion connection, no hardware/firmware access.
All tests inject an explicit test port (never assume 5000 or 8000).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.action_mapping import NUM_PAD_KEYS
from aula_bridge.companion_button_mapping import (
    CompanionButtonMappingError,
    load_companion_button_mapping,
)
from aula_bridge.companion_dispatch_adapter import CompanionDispatchAdapter
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
)
from aula_bridge.dispatcher import ActionDispatcher
from aula_bridge.provider import ProviderEvent

# Explicit test port: never assume 5000 or 8000.
TEST_PORT = 19876
TEST_HOST = "127.0.0.1"


class FakeHttpSender:
    """Deterministic fake HTTP sender. Records calls, no real network."""

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
        if self._raise_on_call is not None:
            raise self._raise_on_call
        return self._response_map.get((method, url), self._default_response)

    def clear(self) -> None:
        self.calls.clear()
        self._response_map.clear()
        self._raise_on_call = None


def _write_tmp_mapping(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="companion_mapping_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _make_event(
    event_type: str = "short_press",
    key: str = "numpad_1",
    device: str = "0C45:800A",
    duration_ms: int = 100,
    seq: int = 1,
    held: bool | None = None,
) -> ProviderEvent:
    return ProviderEvent(
        event=event_type,
        key=key,
        device=device,
        duration_ms=duration_ms,
        held=held,
        seq=seq,
    )


class TestCompanionOfflineE2E(unittest.TestCase):
    """End-to-end offline Companion integration tests."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(
            http_sender=self.sender,
            host=TEST_HOST,
            port=TEST_PORT,
        )
        self.temp_files: list[str] = []
        self._build_chain(mappings={})

    def _build_chain(self, mappings: dict) -> None:
        """Rebuild the full chain with the given button mappings."""
        mapping_content = json.dumps({"version": 1, "mappings": mappings})
        path = _write_tmp_mapping(mapping_content)
        self.temp_files.append(path)
        button_mapping = load_companion_button_mapping(path)
        adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=button_mapping,
        )
        self.dispatcher = ActionDispatcher(transport=adapter)
        self.adapter = adapter

    def _add_mapping(self, key: str, page: int, row: int, column: int) -> None:
        self.sender.clear()
        mapping_content = json.dumps(
            {"version": 1, "mappings": {key: {"page": page, "row": row, "column": column}}}
        )
        path = _write_tmp_mapping(mapping_content)
        self.temp_files.append(path)
        button_mapping = load_companion_button_mapping(path)
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=button_mapping,
        )
        self.dispatcher = ActionDispatcher(transport=self.adapter)

    def tearDown(self) -> None:
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    # ==================== Requirement 1: mapped short_press generates HTTP POST ====================

    def test_mapped_short_press_generates_http_post(self):
        """Mapped short_press produces an HTTP POST through the full chain."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", seq=1)

        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(method, "POST")

    # ==================== Requirement 2: correct Companion location endpoint ====================

    def test_correct_companion_location_endpoint(self):
        """Press targets the Companion location endpoint with explicit test port."""
        self._add_mapping("numpad_5", 2, 3, 4)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_5", seq=1)

        self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        expected_url = f"http://{TEST_HOST}:{TEST_PORT}/api/location/2/3/4/press"
        self.assertEqual(url, expected_url)
        self.assertNotIn(":5000", url)
        self.assertNotIn(":8000", url)

    # ==================== Requirement 3: no request body ====================

    def test_no_request_body(self):
        """No request body is sent; sender receives only method, url, timeout."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", seq=1)

        self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 1)
        call = self.sender.calls[0]
        self.assertEqual(len(call), 3)
        self.assertIsInstance(call[0], str)   # method
        self.assertIsInstance(call[1], str)   # url
        self.assertIsInstance(call[2], float)  # timeout

    # ==================== Requirement 4: unmapped key generates no request ====================

    def test_unmapped_key_generates_no_request(self):
        """Unmapped key produces no HTTP request."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_99", seq=1)

        result = self.dispatcher.dispatch(event)

        self.assertIsNone(result)
        self.assertEqual(len(self.sender.calls), 0)

    # ==================== Requirement 5: empty mapping generates no request ====================

    def test_empty_mapping_generates_no_request(self):
        """Empty mapping produces no HTTP request for any key."""
        self._build_chain({})
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        for key in NUM_PAD_KEYS:
            self.sender.clear()
            event = _make_event(event_type="short_press", key=key, seq=1)
            self.dispatcher.dispatch(event)
            self.assertEqual(len(self.sender.calls), 0)

    # ==================== Requirement 6: invalid mapping fails before dispatch ====================

    def test_invalid_mapping_fails_before_dispatch(self):
        """Invalid mapping file raises at load time, before any dispatch."""
        invalid_path = _write_tmp_mapping("{not valid json")
        self.temp_files.append(invalid_path)
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(invalid_path)

        # No dispatcher/adapter was built from the invalid mapping; no request can be sent.
        self.assertEqual(len(self.sender.calls), 0)

    def test_unknown_logical_key_mapping_fails(self):
        """Mapping with unknown logical key fails at load time, before dispatch."""
        bad_mapping_path = _write_tmp_mapping(
            json.dumps({"version": 1, "mappings": {"numpad_99": {"page": 1, "row": 0, "column": 0}}})
        )
        self.temp_files.append(bad_mapping_path)
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(bad_mapping_path)
        self.assertEqual(len(self.sender.calls), 0)

    # ==================== Requirement 7: hold generates no request ====================

    def test_hold_generates_no_request(self):
        """Hold events produce no HTTP request."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="hold", key="numpad_1", duration_ms=700, seq=1)

        self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 0)

    # ==================== Requirement 8: secondary hold generates no request ====================

    def test_secondary_hold_generates_no_request(self):
        """Secondary hold events produce no HTTP request."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(
            event_type="secondary_hold", key="numpad_1", duration_ms=2000, seq=1
        )

        self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 0)

    # ==================== Requirement 9: key_down/key_up generate no request ====================

    def test_key_down_key_up_generate_no_request(self):
        """key_down and key_up events produce no HTTP request."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        for event_type in ("key_down", "key_up"):
            self.sender.clear()
            event = _make_event(event_type=event_type, key="numpad_1", seq=1)
            result = self.dispatcher.dispatch(event)
            self.assertIsNone(result)
            self.assertEqual(len(self.sender.calls), 0)

    # ==================== Requirement 10: device identity preserved in logs ====================

    def test_device_identity_preserved_in_logs(self):
        """Source device identity is preserved in the adapter log output."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", device="EEEF:268A", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("device=EEEF:268A", log_output)
        self.assertIn("key=numpad_1", log_output)

    # ==================== Requirement 11: event sequence preserved ====================

    def test_event_sequence_preserved(self):
        """Event sequence number is preserved through the chain (event not mutated)."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", seq=42)
        original_dict = event.to_dict()

        self.dispatcher.dispatch(event)

        self.assertEqual(event.to_dict(), original_dict)
        self.assertEqual(event.seq, 42)

    # ==================== Requirement 12: multiple events preserve ordering ====================

    def test_multiple_events_preserve_ordering(self):
        """Multiple mapped events preserve dispatch ordering in the fake sender."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self._add_mapping("numpad_2", 1, 0, 1)
        self._add_mapping("numpad_3", 1, 0, 2)

        # Rebuild with all mappings at once using a fresh combined mapping file.
        mapping_content = json.dumps(
            {
                "version": 1,
                "mappings": {
                    "numpad_1": {"page": 1, "row": 0, "column": 0},
                    "numpad_2": {"page": 1, "row": 0, "column": 1},
                    "numpad_3": {"page": 1, "row": 0, "column": 2},
                },
            }
        )
        path = _write_tmp_mapping(mapping_content)
        self.temp_files.append(path)
        button_mapping = load_companion_button_mapping(path)
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=button_mapping,
        )
        self.dispatcher = ActionDispatcher(transport=self.adapter)

        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            _make_event(key="numpad_1", seq=1),
            _make_event(key="numpad_2", seq=2),
            _make_event(key="numpad_3", seq=3),
        ]
        for event in events:
            self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 3)
        urls = [call[1] for call in self.sender.calls]
        self.assertEqual(
            urls,
            [
                f"http://{TEST_HOST}:{TEST_PORT}/api/location/1/0/0/press",
                f"http://{TEST_HOST}:{TEST_PORT}/api/location/1/0/1/press",
                f"http://{TEST_HOST}:{TEST_PORT}/api/location/1/0/2/press",
            ],
        )

    # ==================== Requirement 13: HTTP 200 accepted ====================

    def test_http_200_accepted(self):
        """HTTP 200 is logged as accepted through the full chain."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=200", log_output)
        self.assertIn("success=True", log_output)

    # ==================== Requirement 14: HTTP 204 reported as NO_CONTROL ====================

    def test_http_204_reported_as_no_control(self):
        """HTTP 204 is logged as NO_CONTROL."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=204, success=False))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=204", log_output)
        self.assertIn("NO_CONTROL", log_output)

    # ==================== Requirement 15: HTTP 400 reported as INVALID_LOCATION ====================

    def test_http_400_reported_as_invalid_location(self):
        """HTTP 400 is logged as INVALID_LOCATION."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=400, success=False))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=400", log_output)
        self.assertIn("INVALID_LOCATION", log_output)

    # ==================== Requirement 16: HTTP 403 reported as FORBIDDEN ====================

    def test_http_403_reported_as_forbidden(self):
        """HTTP 403 is logged as FORBIDDEN."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=403, success=False))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=403", log_output)
        self.assertIn("FORBIDDEN", log_output)

    # ==================== Requirement 17: HTTP 500 reported as SERVER_ERROR ====================

    def test_http_500_reported_as_server_error(self):
        """HTTP 500 is logged as SERVER_ERROR."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=500", log_output)
        self.assertIn("SERVER_ERROR", log_output)

    # ==================== Requirement 18: connection refused handled ====================

    def test_connection_refused_handled(self):
        """Connection refused is handled and logged without crashing."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_raise(ConnectionRefusedError("Connection refused"))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("CONNECTION_REFUSED", log_output)
        self.assertEqual(len(self.sender.calls), 1)

    # ==================== Requirement 19: timeout handled ====================

    def test_timeout_handled(self):
        """Timeout is handled and logged without crashing."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_raise(TimeoutError("Request timeout"))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("TIMEOUT", log_output)
        self.assertEqual(len(self.sender.calls), 1)

    # ==================== Requirement 20: no automatic retries ====================

    def test_no_automatic_retries(self):
        """Failed requests are not retried automatically."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = _make_event(key="numpad_1", seq=1)

        self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 1)

    # ==================== Requirement 21: no event buffering ====================

    def test_no_event_buffering(self):
        """Each event is processed independently; no buffering between events."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self._add_mapping("numpad_2", 1, 0, 1)
        self._add_mapping("numpad_3", 1, 0, 2)

        mapping_content = json.dumps(
            {
                "version": 1,
                "mappings": {
                    "numpad_1": {"page": 1, "row": 0, "column": 0},
                    "numpad_2": {"page": 1, "row": 0, "column": 1},
                    "numpad_3": {"page": 1, "row": 0, "column": 2},
                },
            }
        )
        path = _write_tmp_mapping(mapping_content)
        self.temp_files.append(path)
        button_mapping = load_companion_button_mapping(path)
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=button_mapping,
        )
        self.dispatcher = ActionDispatcher(transport=self.adapter)

        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            _make_event(key="numpad_1", seq=1),
            _make_event(key="numpad_2", seq=2),
            _make_event(key="numpad_3", seq=3),
        ]
        for event in events:
            self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 3)

    # ==================== Requirement 22: ProviderEvent remains unchanged ====================

    def test_provider_event_remains_unchanged(self):
        """ProviderEvent is not mutated through the full chain."""
        self._add_mapping("numpad_3", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        original = ProviderEvent(
            event="short_press",
            key="numpad_3",
            device="0C45:800A",
            duration_ms=850,
            held=True,
            seq=42,
        )
        original_dict = original.to_dict()

        self.dispatcher.dispatch(original)

        self.assertEqual(original.to_dict(), original_dict)
        self.assertEqual(original.seq, 42)
        self.assertEqual(original.duration_ms, 850)
        self.assertEqual(original.held, True)
        self.assertEqual(original.event, "short_press")
        self.assertEqual(original.key, "numpad_3")
        self.assertEqual(original.device, "0C45:800A")

    # ==================== Requirement 23/24: no network / hardware access ====================

    def test_no_real_network_access(self):
        """All responses come from the fake sender; no real network is used."""
        self._add_mapping("numpad_1", 1, 0, 0)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(key="numpad_1", seq=1)

        self.dispatcher.dispatch(event)

        self.assertEqual(len(self.sender.calls), 1)
        # The only sender involved is our in-process fake sender.
        self.assertIs(self.sender, self.http_transport._http_sender)


if __name__ == "__main__":
    unittest.main()
