"""Unit tests for MockCompanionTransport."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.provider import ProviderEvent
from aula_bridge.companion_transport import MockCompanionTransport, CompanionRequest, CompanionResponse


class TestMockCompanionTransport(unittest.TestCase):
    """Tests for the deterministic MockCompanionTransport."""

    def setUp(self):
        self.transport = MockCompanionTransport(default_success=True)

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

    def test_single_valid_action_dispatch(self):
        """Single valid action is recorded correctly."""
        event = self._make_event(key="numpad_1", seq=1)
        self.transport.send("numpad_1_press", "", event)

        self.assertEqual(len(self.transport), 1)
        req = self.transport.sent_requests[0]
        self.assertEqual(req.action_id, "numpad_1_press")
        self.assertEqual(req.event.key, "numpad_1")
        self.assertEqual(req.event.device, "0C45:800A")
        self.assertEqual(req.metadata["duration_ms"], 100)

    def test_multiple_actions_preserve_ordering(self):
        """Multiple actions preserve dispatch order."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
            self._make_event(key="numpad_3", seq=3),
        ]
        for e in events:
            self.transport.send(f"{e.key}_press", "", e)

        self.assertEqual(len(self.transport), 3)
        action_ids = self.transport.sent_action_ids
        self.assertEqual(action_ids, ["numpad_1_press", "numpad_2_press", "numpad_3_press"])

    def test_correct_action_identifier_propagation(self):
        """Action identifier (command) is preserved from dispatch."""
        event = self._make_event(key="numpad_5", seq=1)
        self.transport.send("numpad_5_hold", "hold_payload", event)

        req = self.transport.sent_requests[0]
        self.assertEqual(req.action_id, "numpad_5_hold")
        self.assertEqual(req.metadata["payload"], "hold_payload")

    def test_correct_device_identity_propagation(self):
        """Source device identity is preserved."""
        event = self._make_event(device="EEEF:268A", seq=1)
        self.transport.send("test_cmd", "", event)

        req = self.transport.sent_requests[0]
        self.assertEqual(req.event.device, "EEEF:268A")
        self.assertEqual(req.metadata["device"], "EEEF:268A")

    def test_success_response_handling(self):
        """Default success response is returned."""
        event = self._make_event(key="numpad_1", seq=1)
        self.transport.send("numpad_1_press", "", event)

        resp = self.transport.get_response("numpad_1_press")
        self.assertTrue(resp.success)
        self.assertEqual(resp.action_id, "numpad_1_press")
        self.assertIsNone(resp.error_code)

    def test_failure_response_handling(self):
        """Configured failure response is returned."""
        self.transport.set_failure("numpad_1_press", "INVALID_ACTION", "Action not configured")
        event = self._make_event(key="numpad_1", seq=1)
        self.transport.send("numpad_1_press", "", event)

        resp = self.transport.get_response("numpad_1_press")
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_code, "INVALID_ACTION")
        self.assertEqual(resp.error_message, "Action not configured")

    def test_timeout_handling(self):
        """Configured timeout response is returned."""
        self.transport.set_timeout("numpad_1_press", "Connection timed out")
        event = self._make_event(key="numpad_1", seq=1)
        self.transport.send("numpad_1_press", "", event)

        resp = self.transport.get_response("numpad_1_press")
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_code, "TIMEOUT")
        self.assertIn("timed out", resp.error_message)

    def test_invalid_action_rejection(self):
        """Invalid/unsupported action IDs are tracked but return default."""
        event = self._make_event(key="unknown_key", seq=1)
        self.transport.send("unknown_key_press", "", event)

        # Request is still recorded
        self.assertEqual(len(self.transport), 1)
        req = self.transport.sent_requests[0]
        self.assertEqual(req.action_id, "unknown_key_press")

        # Response uses default (success since not in fail set)
        resp = self.transport.get_response("unknown_key_press")
        self.assertTrue(resp.success)

    def test_dryrun_provider_unchanged(self):
        """DryRunProvider behavior is unaffected by companion transport."""
        from aula_bridge.provider import DryRunProvider

        provider = DryRunProvider(log_file="test_transport.jsonl", log_dir="logs")
        event = self._make_event(key="numpad_1", seq=1)
        provider.emit(event)

        # Also dispatch through transport
        self.transport.send("numpad_1_press", "", event)

        provider.close()

        # Verify provider log
        with open(provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        self.assertEqual(len(lines), 1)
        import json
        logged = json.loads(lines[0])
        self.assertEqual(logged["event"], "short_press")
        self.assertEqual(logged["key"], "numpad_1")

        # Verify transport recorded the dispatch
        self.assertEqual(len(self.transport), 1)

    def test_no_network_or_hardware_access(self):
        """Transport performs no network or hardware I/O."""
        # Just verify the transport works without any I/O
        # (by design it has no network/hardware dependencies)
        events = [self._make_event(key=f"numpad_{i}", seq=i) for i in range(10)]
        for e in events:
            self.transport.send(f"{e.key}_press", "", e)

        # All recorded in memory only
        self.assertEqual(len(self.transport), 10)

    def test_clear_resets_state(self):
        """Clear resets all recorded state."""
        event = self._make_event(key="numpad_1", seq=1)
        self.transport.send("numpad_1_press", "", event)
        self.transport.clear()

        self.assertEqual(len(self.transport), 0)
        self.assertEqual(self.transport.sent_requests, ())

    def test_verify_request_sequence(self):
        """Verify request sequence matching."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
            self._make_event(key="numpad_1", seq=3),  # same key again
        ]
        for e in events:
            self.transport.send(f"{e.key}_press", "", e)

        self.assertTrue(self.transport.verify_request_sequence(["numpad_1_press", "numpad_2_press", "numpad_1_press"]))
        self.assertFalse(self.transport.verify_request_sequence(["numpad_1_press", "numpad_1_press", "numpad_2_press"]))

    def test_count_requests_for_key(self):
        """Count requests per logical key."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_1", seq=2),
            self._make_event(key="numpad_2", seq=3),
        ]
        for e in events:
            self.transport.send(f"{e.key}_press", "", e)

        self.assertEqual(self.transport.count_requests_for_key("numpad_1"), 2)
        self.assertEqual(self.transport.count_requests_for_key("numpad_2"), 1)
        self.assertEqual(self.transport.count_requests_for_key("numpad_3"), 0)

    def test_get_requests_for_device(self):
        """Filter requests by device."""
        events = [
            self._make_event(key="numpad_1", device="0C45:800A", seq=1),
            self._make_event(key="numpad_2", device="EEEF:268A", seq=2),
            self._make_event(key="numpad_3", device="0C45:800A", seq=3),
        ]
        for e in events:
            self.transport.send(f"{e.key}_press", "", e)

        keyboard_reqs = self.transport.get_requests_for_device("0C45:800A")
        self.assertEqual(len(keyboard_reqs), 2)
        self.assertEqual(keyboard_reqs[0].event.key, "numpad_1")
        self.assertEqual(keyboard_reqs[1].event.key, "numpad_3")

    def test_get_last_request(self):
        """Get most recent request."""
        self.assertIsNone(self.transport.get_last_request())

        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
        ]
        for e in events:
            self.transport.send(f"{e.key}_press", "", e)

        last = self.transport.get_last_request()
        self.assertIsNotNone(last)
        self.assertEqual(last.action_id, "numpad_2_press")

    def test_default_failure_mode(self):
        """Transport can be configured with default failure."""
        transport = MockCompanionTransport(default_success=False)
        event = self._make_event(key="numpad_1", seq=1)
        transport.send("numpad_1_press", "", event)

        resp = transport.get_response("numpad_1_press")
        self.assertFalse(resp.success)


class TestCompanionRequestResponse(unittest.TestCase):
    """Tests for CompanionRequest and CompanionResponse dataclasses."""

    def test_companion_request_immutable(self):
        """CompanionRequest is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        req = CompanionRequest(action_id="test", event=event, metadata={"foo": "bar"})

        with self.assertRaises(FrozenInstanceError):
            req.action_id = "changed"

    def test_companion_response_immutable(self):
        """CompanionResponse is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError
        resp = CompanionResponse(success=True, action_id="test")

        with self.assertRaises(FrozenInstanceError):
            resp.success = False


if __name__ == "__main__":
    unittest.main()