"""Integration tests for MockCompanionTransport with ActionDispatcher.

Tests the interaction between the dispatcher and the companion transport
for all specified scenarios.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.provider import ProviderEvent
from aula_bridge.dispatcher import ActionDispatcher
from aula_bridge.companion_transport import MockCompanionTransport, CompanionResponse
from aula_bridge.action_mapping import ActionMap


class TestCompanionDispatcherIntegration(unittest.TestCase):
    """Integration tests for ActionDispatcher with MockCompanionTransport."""

    def setUp(self):
        self.transport = MockCompanionTransport(default_success=True)
        self.dispatcher = ActionDispatcher(transport=self.transport)

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

    def test_short_press_dispatch(self):
        """Short press dispatches correctly via companion transport."""
        event = self._make_event(event_type="short_press", key="numpad_1", seq=1)
        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_1_press")
        self.assertEqual(result.source_event, event)

        req = self.transport.sent_requests[0]
        self.assertEqual(req.action_id, "numpad_1_press")
        self.assertEqual(req.event.event, "short_press")
        self.assertEqual(req.event.key, "numpad_1")
        self.assertEqual(req.metadata["duration_ms"], 100)

    def test_hold_dispatch(self):
        """Hold dispatches correctly via companion transport."""
        event = self._make_event(event_type="hold", key="numpad_5", duration_ms=700, seq=2)
        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_5_hold")

        req = self.transport.sent_requests[0]
        self.assertEqual(req.action_id, "numpad_5_hold")
        self.assertEqual(req.event.event, "hold")
        self.assertEqual(req.metadata["duration_ms"], 700)

    def test_secondary_hold_dispatch(self):
        """Secondary hold dispatches correctly via companion transport."""
        event = self._make_event(event_type="secondary_hold", key="numpad_enter", duration_ms=2000, seq=3)
        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_enter_secondary_hold")

        req = self.transport.sent_requests[0]
        self.assertEqual(req.action_id, "numpad_enter_secondary_hold")
        self.assertEqual(req.event.event, "secondary_hold")
        self.assertEqual(req.metadata["duration_ms"], 2000)

    def test_correct_action_identifier(self):
        """Action identifier (command) matches expected mapping."""
        test_cases = [
            ("numpad_1", "short_press", "numpad_1_press"),
            ("numpad_2", "short_press", "numpad_2_press"),
            ("numpad_7", "hold", "numpad_7_hold"),
            ("numpad_0", "hold", "numpad_0_hold"),
            ("numpad_enter", "secondary_hold", "numpad_enter_secondary_hold"),
            ("numpad_plus", "secondary_hold", "numpad_plus_secondary_hold"),
        ]

        for key, event_type, expected_command in test_cases:
            with self.subTest(key=key, event_type=event_type):
                self.transport.clear()
                event = self._make_event(event_type=event_type, key=key, seq=1)
                self.dispatcher.dispatch(event)

                req = self.transport.sent_requests[0]
                self.assertEqual(req.action_id, expected_command)

    def test_correct_source_device_identity(self):
        """Source device identity is preserved through dispatch."""
        devices = ["0C45:800A", "EEEF:268A", "1234:5678", "ABCD:EF00"]

        for device in devices:
            with self.subTest(device=device):
                self.transport.clear()
                event = self._make_event(device=device, seq=1)
                self.dispatcher.dispatch(event)

                req = self.transport.sent_requests[0]
                self.assertEqual(req.event.device, device)
                self.assertEqual(req.metadata["device"], device)

    def test_correct_event_sequence(self):
        """Event sequence numbers are preserved and increment correctly."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
            self._make_event(key="numpad_3", seq=3),
            self._make_event(key="numpad_1", seq=4),
            self._make_event(key="numpad_2", seq=5),
        ]

        for event in events:
            self.dispatcher.dispatch(event)

        self.assertEqual(len(self.transport.sent_requests), 5)
        for i, req in enumerate(self.transport.sent_requests):
            self.assertEqual(req.event.seq, i + 1)
            self.assertEqual(req.metadata.get("seq"), i + 1)

    def test_multiple_actions_preserve_ordering(self):
        """Multiple actions preserve dispatch ordering in companion transport."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
            self._make_event(key="numpad_3", seq=3),
            self._make_event(key="numpad_4", seq=4),
            self._make_event(key="numpad_5", seq=5),
        ]

        for event in events:
            self.dispatcher.dispatch(event)

        action_ids = self.transport.sent_action_ids
        expected = [
            "numpad_1_press",
            "numpad_2_press",
            "numpad_3_press",
            "numpad_4_press",
            "numpad_5_press",
        ]
        self.assertEqual(action_ids, expected)

        # Verify verify_request_sequence works
        self.assertTrue(self.transport.verify_request_sequence(expected))
        self.assertFalse(self.transport.verify_request_sequence(expected[::-1]))

    def test_provider_event_remains_unchanged(self):
        """ProviderEvent is not mutated during dispatch through companion transport."""
        original = ProviderEvent(
            event="hold",
            key="numpad_3",
            device="0C45:800A",
            duration_ms=850,
            held=True,
            seq=42,
        )
        original_dict = original.to_dict()

        self.dispatcher.dispatch(original)

        # Event should be completely unchanged
        self.assertEqual(original.to_dict(), original_dict)
        self.assertEqual(original.seq, 42)
        self.assertEqual(original.duration_ms, 850)
        self.assertEqual(original.held, True)
        self.assertEqual(original.event, "hold")
        self.assertEqual(original.key, "numpad_3")
        self.assertEqual(original.device, "0C45:800A")

        # Verify the dispatched action also preserves the original
        req = self.transport.sent_requests[0]
        self.assertEqual(req.event, original)
        self.assertEqual(req.event.seq, 42)
        self.assertEqual(req.event.duration_ms, 850)

    def test_unmapped_events_produce_no_request(self):
        """Unmapped event types produce no companion request."""
        unmapped_events = [
            "key_down",
            "key_up",
            "repeat_ignored",
            "unknown_event",
        ]

        for event_type in unmapped_events:
            with self.subTest(event_type=event_type):
                self.transport.clear()
                event = self._make_event(event_type=event_type, key="numpad_1", seq=1)
                result = self.dispatcher.dispatch(event)

                self.assertIsNone(result)
                self.assertEqual(len(self.transport), 0)

        # Also test unknown key with valid event type
        self.transport.clear()
        event = self._make_event(event_type="short_press", key="unknown_key", seq=1)
        result = self.dispatcher.dispatch(event)

        self.assertIsNone(result)
        self.assertEqual(len(self.transport), 0)

    def test_failure_propagation(self):
        """Failure responses from transport are accessible."""
        self.transport.set_failure("numpad_1_press", "INVALID_ACTION", "Action not configured")

        event = self._make_event(key="numpad_1", seq=1)
        self.dispatcher.dispatch(event)

        resp = self.transport.get_response("numpad_1_press")
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_code, "INVALID_ACTION")
        self.assertEqual(resp.error_message, "Action not configured")
        self.assertEqual(resp.action_id, "numpad_1_press")

    def test_timeout_propagation(self):
        """Timeout responses from transport are accessible."""
        self.transport.set_timeout("numpad_5_hold", "Connection timed out")

        event = self._make_event(event_type="hold", key="numpad_5", duration_ms=700, seq=1)
        self.dispatcher.dispatch(event)

        resp = self.transport.get_response("numpad_5_hold")
        self.assertFalse(resp.success)
        self.assertEqual(resp.error_code, "TIMEOUT")
        self.assertIn("timed out", resp.error_message)
        self.assertEqual(resp.action_id, "numpad_5_hold")

    def test_mixed_success_failure_timeout(self):
        """Mixed success, failure, and timeout responses work correctly."""
        self.transport.set_failure("numpad_1_press", "FAIL")
        self.transport.set_timeout("numpad_2_press", "TIMEOUT")
        # numpad_3_press uses default success

        events = [
            self._make_event(key="numpad_1", seq=1),  # failure
            self._make_event(key="numpad_2", seq=2),  # timeout
            self._make_event(key="numpad_3", seq=3),  # success
        ]

        for event in events:
            self.dispatcher.dispatch(event)

        self.assertEqual(len(self.transport), 3)

        resp1 = self.transport.get_response("numpad_1_press")
        self.assertFalse(resp1.success)
        self.assertEqual(resp1.error_code, "FAIL")

        resp2 = self.transport.get_response("numpad_2_press")
        self.assertFalse(resp2.success)
        self.assertEqual(resp2.error_code, "TIMEOUT")

        resp3 = self.transport.get_response("numpad_3_press")
        self.assertTrue(resp3.success)
        self.assertIsNone(resp3.error_code)

    def test_batch_dispatch_with_companion_transport(self):
        """Batch dispatch works correctly with companion transport."""
        events = [
            self._make_event(event_type="short_press", key="numpad_1", seq=1),
            self._make_event(event_type="hold", key="numpad_2", seq=2),
            self._make_event(event_type="secondary_hold", key="numpad_3", seq=3),
            self._make_event(event_type="key_down", key="numpad_4", seq=4),  # no-op
            self._make_event(event_type="short_press", key="numpad_5", seq=5),
        ]

        results = self.dispatcher.dispatch_batch(events)

        self.assertEqual(len(results), 4)  # 4 mapped, 1 no-op
        self.assertEqual(len(self.transport.sent_requests), 4)

        self.assertEqual(results[0].command, "numpad_1_press")
        self.assertEqual(results[1].command, "numpad_2_hold")
        self.assertEqual(results[2].command, "numpad_3_secondary_hold")
        self.assertEqual(results[3].command, "numpad_5_press")

    def test_transport_metadata_contains_full_event_info(self):
        """Transport metadata includes all relevant event information."""
        event = self._make_event(
            event_type="hold",
            key="numpad_7",
            device="EEEF:268A",
            duration_ms=950,
            seq=99,
        )
        self.dispatcher.dispatch(event)

        req = self.transport.sent_requests[0]
        metadata = req.metadata

        self.assertEqual(metadata["payload"], "")
        self.assertEqual(metadata["event_type"], "hold")
        self.assertEqual(metadata["duration_ms"], 950)
        self.assertEqual(metadata["device"], "EEEF:268A")
        self.assertEqual(metadata["seq"], 99)

    def test_flush_and_close_no_op(self):
        """Flush and close are no-ops for mock transport."""
        event = self._make_event(key="numpad_1", seq=1)
        self.dispatcher.dispatch(event)

        self.dispatcher.flush()  # Should not raise
        self.dispatcher.close()  # Should not raise

        # Transport still has the request
        self.assertEqual(len(self.transport), 1)

    def test_default_failure_mode_transport(self):
        """Transport with default_success=False returns failures by default."""
        transport = MockCompanionTransport(default_success=False)
        dispatcher = ActionDispatcher(transport=transport)

        event = self._make_event(key="numpad_1", seq=1)
        dispatcher.dispatch(event)

        resp = transport.get_response("numpad_1_press")
        self.assertFalse(resp.success)
        # Default failure has no specific error code (just success=False)
        self.assertIsNone(resp.error_code)
        self.assertEqual(resp.action_id, "numpad_1_press")

    def test_clear_transport_resets_state(self):
        """Clearing transport resets all state."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
        ]
        for e in events:
            self.dispatcher.dispatch(e)

        self.assertEqual(len(self.transport), 2)

        self.transport.clear()

        self.assertEqual(len(self.transport), 0)
        self.assertEqual(self.transport.sent_requests, ())
        self.assertEqual(self.transport.sent_action_ids, [])

    def test_count_requests_for_key(self):
        """Count requests per logical key works through dispatcher."""
        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_1", seq=2),
            self._make_event(key="numpad_2", seq=3),
            self._make_event(key="numpad_1", seq=4),
        ]
        for e in events:
            self.dispatcher.dispatch(e)

        self.assertEqual(self.transport.count_requests_for_key("numpad_1"), 3)
        self.assertEqual(self.transport.count_requests_for_key("numpad_2"), 1)
        self.assertEqual(self.transport.count_requests_for_key("numpad_3"), 0)

    def test_get_requests_for_device(self):
        """Filter requests by device works through dispatcher."""
        events = [
            self._make_event(key="numpad_1", device="0C45:800A", seq=1),
            self._make_event(key="numpad_2", device="EEEF:268A", seq=2),
            self._make_event(key="numpad_3", device="0C45:800A", seq=3),
        ]
        for e in events:
            self.dispatcher.dispatch(e)

        keyboard_reqs = self.transport.get_requests_for_device("0C45:800A")
        self.assertEqual(len(keyboard_reqs), 2)
        self.assertEqual(keyboard_reqs[0].event.key, "numpad_1")
        self.assertEqual(keyboard_reqs[1].event.key, "numpad_3")

    def test_get_last_request(self):
        """Get last request works through dispatcher."""
        self.assertIsNone(self.transport.get_last_request())

        events = [
            self._make_event(key="numpad_1", seq=1),
            self._make_event(key="numpad_2", seq=2),
        ]
        for e in events:
            self.dispatcher.dispatch(e)

        last = self.transport.get_last_request()
        self.assertIsNotNone(last)
        self.assertEqual(last.action_id, "numpad_2_press")
        self.assertEqual(last.event.seq, 2)


if __name__ == "__main__":
    unittest.main()