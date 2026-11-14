"""Unit tests for the AULA L99 offline action dispatcher.

Tests deterministic mapping, no-op behavior, event field preservation,
and mock transport verification.
"""

import os
import sys
import unittest
from typing import List

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.provider import ProviderEvent, DryRunProvider
from aula_bridge.action_mapping import ActionMap, ActionMapEntry
from aula_bridge.dispatcher import (
    ActionDispatcher,
    Transport,
    MockTransport,
    DispatchedAction,
)


class TestActionMap(unittest.TestCase):
    """Tests for the immutable ActionMap."""

    def setUp(self):
        self.action_map = ActionMap()

    def test_short_press_mapped(self):
        """All 17 keys have short_press mappings."""
        for key in ActionMap.DEFAULT_ACTION_MAP.keys():
            if key[1] == "short_press":
                entry = self.action_map.lookup(key[0], "short_press")
                self.assertIsNotNone(entry)
                self.assertEqual(entry.logical_key, key[0])
                self.assertEqual(entry.event_type, "short_press")
                self.assertTrue(entry.command.endswith("_press"))
                self.assertEqual(entry.payload, "")

    def test_hold_mapped(self):
        """All 17 keys have hold mappings."""
        for key in ActionMap.DEFAULT_ACTION_MAP.keys():
            if key[1] == "hold":
                entry = self.action_map.lookup(key[0], "hold")
                self.assertIsNotNone(entry)
                self.assertEqual(entry.logical_key, key[0])
                self.assertEqual(entry.event_type, "hold")
                self.assertTrue(entry.command.endswith("_hold"))
                self.assertEqual(entry.payload, "")

    def test_secondary_hold_mapped(self):
        """All 17 keys have secondary_hold mappings."""
        for key in ActionMap.DEFAULT_ACTION_MAP.keys():
            if key[1] == "secondary_hold":
                entry = self.action_map.lookup(key[0], "secondary_hold")
                self.assertIsNotNone(entry)
                self.assertEqual(entry.logical_key, key[0])
                self.assertEqual(entry.event_type, "secondary_hold")
                self.assertTrue(entry.command.endswith("_secondary_hold"))
                self.assertEqual(entry.payload, "")

    def test_unsupported_event_type_no_op(self):
        """Unsupported event types return None."""
        entry = self.action_map.lookup("numpad_1", "key_down")
        self.assertIsNone(entry)
        entry = self.action_map.lookup("numpad_1", "key_up")
        self.assertIsNone(entry)
        entry = self.action_map.lookup("numpad_1", "repeat_ignored")
        self.assertIsNone(entry)

    def test_unknown_key_no_op(self):
        """Unknown logical keys return None."""
        entry = self.action_map.lookup("unknown_key", "short_press")
        self.assertIsNone(entry)
        entry = self.action_map.lookup("unknown_key", "hold")
        self.assertIsNone(entry)
        entry = self.action_map.lookup("unknown_key", "secondary_hold")
        self.assertIsNone(entry)

    def test_has_mapping(self):
        """has_mapping returns correct boolean."""
        self.assertTrue(self.action_map.has_mapping("numpad_1", "short_press"))
        self.assertTrue(self.action_map.has_mapping("numpad_1", "hold"))
        self.assertTrue(self.action_map.has_mapping("numpad_1", "secondary_hold"))
        self.assertFalse(self.action_map.has_mapping("numpad_1", "key_down"))
        self.assertFalse(self.action_map.has_mapping("unknown", "short_press"))

    def test_all_mappings_deterministic_order(self):
        """all_mappings returns entries in deterministic sorted order."""
        mappings = self.action_map.all_mappings()
        self.assertEqual(len(mappings), 51)  # 17 keys * 3 event types

        # Verify sorted by (key, event_type)
        for i in range(len(mappings) - 1):
            a = (mappings[i].logical_key, mappings[i].event_type)
            b = (mappings[i + 1].logical_key, mappings[i + 1].event_type)
            self.assertLessEqual(a, b)

    def test_custom_mapping(self):
        """Custom mapping overrides defaults."""
        custom = {("numpad_1", "short_press"): ("custom_cmd", "custom_payload")}
        action_map = ActionMap(mapping=custom)
        entry = action_map.lookup("numpad_1", "short_press")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.command, "custom_cmd")
        self.assertEqual(entry.payload, "custom_payload")

        # Other keys still use defaults
        entry2 = action_map.lookup("numpad_2", "short_press")
        self.assertIsNotNone(entry2)
        self.assertEqual(entry2.command, "numpad_2_press")


class TestMockTransport(unittest.TestCase):
    """Tests for the MockTransport."""

    def test_send_records_action(self):
        transport = MockTransport()
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=100)
        transport.send("test_cmd", "test_payload", event)

        sent = transport.sent_actions
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].command, "test_cmd")
        self.assertEqual(sent[0].payload, "test_payload")
        self.assertEqual(sent[0].event, event)

    def test_clear_resets(self):
        transport = MockTransport()
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        transport.send("cmd", "payload", event)
        transport.clear()
        self.assertEqual(len(transport.sent_actions), 0)

    def test_multiple_sends_preserve_order(self):
        transport = MockTransport()
        events = [
            ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1),
            ProviderEvent(event="hold", key="numpad_1", device="0C45:800A", seq=2),
            ProviderEvent(event="secondary_hold", key="numpad_1", device="0C45:800A", seq=3),
        ]
        for e in events:
            transport.send(f"cmd_{e.seq}", "payload", e)

        sent = transport.sent_actions
        self.assertEqual(len(sent), 3)
        for i, s in enumerate(sent):
            self.assertEqual(s.command, f"cmd_{i + 1}")
            self.assertEqual(s.event.seq, i + 1)


class TestActionDispatcher(unittest.TestCase):
    """Tests for the ActionDispatcher."""

    def setUp(self):
        self.transport = MockTransport()
        self.dispatcher = ActionDispatcher(transport=self.transport)

    def test_mapped_short_press(self):
        """Mapped short_press dispatches correctly."""
        event = ProviderEvent(
            event="short_press",
            key="numpad_1",
            device="0C45:800A",
            duration_ms=183,
            seq=1,
        )
        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_1_press")
        self.assertEqual(result.payload, "")
        self.assertEqual(result.source_event, event)
        self.assertEqual(result.map_entry.logical_key, "numpad_1")
        self.assertEqual(result.map_entry.event_type, "short_press")

        # Verify transport received it
        sent = self.transport.sent_actions
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].command, "numpad_1_press")

    def test_mapped_hold(self):
        """Mapped hold dispatches correctly."""
        event = ProviderEvent(
            event="hold",
            key="numpad_5",
            device="0C45:800A",
            duration_ms=700,
            seq=2,
        )
        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_5_hold")
        self.assertEqual(result.source_event, event)

    def test_mapped_secondary_hold(self):
        """Mapped secondary_hold dispatches correctly."""
        event = ProviderEvent(
            event="secondary_hold",
            key="numpad_enter",
            device="0C45:800A",
            duration_ms=2000,
            seq=3,
        )
        result = self.dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_enter_secondary_hold")
        self.assertEqual(result.source_event, event)

    def test_unmapped_event_no_op(self):
        """Unmapped event types (key_down, key_up, repeat_ignored) are no-op."""
        for event_type in ["key_down", "key_up", "repeat_ignored"]:
            event = ProviderEvent(event=event_type, key="numpad_1", device="0C45:800A")
            result = self.dispatcher.dispatch(event)
            self.assertIsNone(result)
            self.assertEqual(len(self.transport.sent_actions), 0)

    def test_unknown_key_no_op(self):
        """Unknown logical keys are no-op."""
        event = ProviderEvent(event="short_press", key="unknown_key", device="0C45:800A")
        result = self.dispatcher.dispatch(event)
        self.assertIsNone(result)
        self.assertEqual(len(self.transport.sent_actions), 0)

    def test_repeat_ignored_no_op(self):
        """repeat_ignored events are no-op."""
        event = ProviderEvent(event="repeat_ignored", key="numpad_1", device="0C45:800A")
        result = self.dispatcher.dispatch(event)
        self.assertIsNone(result)
        self.assertEqual(len(self.transport.sent_actions), 0)

    def test_event_fields_preserved(self):
        """Source ProviderEvent fields are preserved in DispatchedAction."""
        original = ProviderEvent(
            event="hold",
            key="numpad_3",
            device="0C45:800A",
            duration_ms=850,
            held=True,
            seq=42,
        )
        result = self.dispatcher.dispatch(original)

        self.assertIsNotNone(result)
        self.assertEqual(result.source_event, original)
        self.assertEqual(result.source_event.event, "hold")
        self.assertEqual(result.source_event.key, "numpad_3")
        self.assertEqual(result.source_event.device, "0C45:800A")
        self.assertEqual(result.source_event.duration_ms, 850)
        self.assertEqual(result.source_event.held, True)
        self.assertEqual(result.source_event.seq, 42)

    def test_no_mutation_of_provider_event(self):
        """ProviderEvent is not mutated during dispatch."""
        event = ProviderEvent(
            event="short_press",
            key="numpad_2",
            device="0C45:800A",
            duration_ms=200,
            seq=5,
        )
        original_dict = event.to_dict()

        self.dispatcher.dispatch(event)

        # Event should be unchanged
        self.assertEqual(event.to_dict(), original_dict)
        self.assertEqual(event.seq, 5)
        self.assertEqual(event.duration_ms, 200)

    def test_deterministic_dispatch_order(self):
        """Batch dispatch preserves input order."""
        events = [
            ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1),
            ProviderEvent(event="hold", key="numpad_2", device="0C45:800A", seq=2),
            ProviderEvent(event="secondary_hold", key="numpad_3", device="0C45:800A", seq=3),
        ]
        results = self.dispatcher.dispatch_batch(events)

        self.assertEqual(len(results), 3)
        for i, r in enumerate(results):
            self.assertEqual(r.source_event.seq, i + 1)

        # Transport should receive in same order
        sent = self.transport.sent_actions
        self.assertEqual(len(sent), 3)
        for i, s in enumerate(sent):
            self.assertEqual(s.event.seq, i + 1)

    def test_mock_transport_receives_expected_actions(self):
        """Mock transport receives exactly the expected actions."""
        events = [
            ProviderEvent(event="short_press", key="numpad_7", device="0C45:800A", seq=1),
            ProviderEvent(event="key_down", key="numpad_7", device="0C45:800A", seq=2),  # no-op
            ProviderEvent(event="hold", key="numpad_7", device="0C45:800A", seq=3),
        ]
        self.dispatcher.dispatch_batch(events)

        sent = self.transport.sent_actions
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0].command, "numpad_7_press")
        self.assertEqual(sent[1].command, "numpad_7_hold")

    def test_dryrun_provider_behavior_unchanged(self):
        """DryRunProvider behavior is unaffected by dispatcher."""
        provider = DryRunProvider(log_file="test_dispatch.jsonl", log_dir="logs")
        dispatcher = ActionDispatcher(transport=self.transport, action_map=ActionMap())

        # Emit via provider directly (simulating bridge behavior)
        event1 = ProviderEvent(event="key_down", key="numpad_1", device="0C45:800A")
        provider.emit(event1)

        event2 = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=150)
        provider.emit(event2)

        # Dispatch the short_press through dispatcher
        dispatcher.dispatch(event2)

        provider.close()

        # Verify provider log has both events
        with open(provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()

        self.assertEqual(len(lines), 2)
        import json
        first = json.loads(lines[0])
        self.assertEqual(first["event"], "key_down")
        second = json.loads(lines[1])
        self.assertEqual(second["event"], "short_press")

        # Verify transport also received the dispatched action
        sent = self.transport.sent_actions
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].command, "numpad_1_press")


if __name__ == "__main__":
    unittest.main()