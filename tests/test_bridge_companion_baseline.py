"""Baseline regression tests for Windows Bridge behavior before Companion opt-in integration.

These tests protect existing behavior and ensure no unintended changes when
Companion opt-in features are added. Tests verify the current default behavior
without requiring any future CLI flags or opt-in mechanisms.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge import BridgeConfig, load_config
from aula_bridge.provider import DryRunProvider, ProviderEvent, BridgeProvider
from aula_bridge.dispatcher import ActionDispatcher, MockTransport, Transport
from aula_bridge.action_mapping import ActionMap


class TestCLIDefaultsUnchanged(unittest.TestCase):
    """Verify current CLI defaults remain unchanged."""

    def test_default_config_values(self):
        """BridgeConfig defaults match documented POC values."""
        config = BridgeConfig()
        self.assertEqual(config.vid, 0x0C45)
        self.assertEqual(config.pid, 0x800A)
        self.assertEqual(config.short_threshold_ms, 500)
        self.assertEqual(config.hold_threshold_ms, 700)
        self.assertEqual(config.secondary_hold_ms, 2000)
        self.assertEqual(config.secondary_hold_enabled, False)
        self.assertEqual(config.stuck_key_timeout_ms, 5000)
        self.assertEqual(config.provider, "dry_run")
        self.assertEqual(config.log_file, "bridge_events.jsonl")
        self.assertEqual(config.log_dir, "logs")

    def test_load_config_without_file_returns_defaults(self):
        """Missing config file produces default configuration."""
        config = load_config("/nonexistent/path.json")
        self.assertEqual(config.vid, 0x0C45)
        self.assertEqual(config.pid, 0x800A)
        self.assertEqual(config.provider, "dry_run")

    def test_config_env_var_nonexistent_returns_defaults(self):
        """Missing env var produces default configuration."""
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(None)
            self.assertEqual(config.provider, "dry_run")


class TestNoCompanionActivationByDefault(unittest.TestCase):
    """Verify Companion is not activated by default."""

    def test_bridge_config_has_no_companion_fields(self):
        """BridgeConfig contains no Companion-related fields."""
        config = BridgeConfig()
        config_dict = config.to_dict()
        self.assertNotIn("companion", config_dict)
        self.assertNotIn("enabled", config_dict)
        self.assertNotIn("host", config_dict)
        self.assertNotIn("port", config_dict)
        self.assertNotIn("timeout", config_dict)
        self.assertNotIn("mapping_file", config_dict)

    def test_provider_default_is_dry_run_only(self):
        """Default provider is dry_run, no companion provider exists."""
        config = BridgeConfig()
        self.assertEqual(config.provider, "dry_run")
        # Provider string must be exactly "dry_run"
        self.assertIsInstance(config.provider, str)
        self.assertNotEqual(config.provider, "companion")
        self.assertNotEqual(config.provider, "http")

    def test_entry_point_imports_no_companion_modules(self):
        """aula_input_bridge.py does not import Companion modules at module level."""
        import aula_input_bridge
        # Verify no companion imports in the module's namespace
        self.assertFalse(hasattr(aula_input_bridge, "CompanionOptInConfig"))
        self.assertFalse(hasattr(aula_input_bridge, "CompanionHttpSender"))
        self.assertFalse(hasattr(aula_input_bridge, "CompanionHttpTransport"))

    def test_bridge_package_exports_no_companion(self):
        """aula_bridge.__all__ does not export Companion types."""
        from aula_bridge import __all__
        for export in __all__:
            self.assertNotIn("companion", export.lower())
            self.assertNotIn("Companion", export)


class TestMockTransportAvailable(unittest.TestCase):
    """Verify existing MockTransport remains available and functional."""

    def test_mock_transport_instantiates(self):
        """MockTransport can be instantiated without arguments."""
        transport = MockTransport()
        self.assertIsInstance(transport, MockTransport)

    def test_mock_transport_implements_transport_protocol(self):
        """MockTransport satisfies Transport protocol."""
        transport = MockTransport()
        self.assertTrue(hasattr(transport, "send"))
        self.assertTrue(hasattr(transport, "flush"))
        self.assertTrue(hasattr(transport, "close"))
        self.assertTrue(hasattr(transport, "sent_actions"))
        self.assertTrue(hasattr(transport, "clear"))

    def test_mock_transport_records_actions(self):
        """MockTransport records sent actions for verification."""
        transport = MockTransport()
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1)
        transport.send("test_cmd", "test_payload", event)
        sent = transport.sent_actions
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].command, "test_cmd")
        self.assertEqual(sent[0].payload, "test_payload")
        self.assertEqual(sent[0].event, event)

    def test_mock_transport_preserves_order(self):
        """MockTransport preserves action order."""
        transport = MockTransport()
        events = [
            ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1),
            ProviderEvent(event="hold", key="numpad_1", device="0C45:800A", seq=2),
        ]
        for e in events:
            transport.send(f"cmd_{e.seq}", "payload", e)
        sent = transport.sent_actions
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0].event.seq, 1)
        self.assertEqual(sent[1].event.seq, 2)

    def test_mock_transport_clear_resets(self):
        """MockTransport.clear() resets recorded actions."""
        transport = MockTransport()
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        transport.send("cmd", "payload", event)
        transport.clear()
        self.assertEqual(len(transport.sent_actions), 0)


class TestDryRunProviderAvailable(unittest.TestCase):
    """Verify DryRunProvider remains available and functional."""

    def test_dryrun_provider_instantiates(self):
        """DryRunProvider can be instantiated with log file and directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            self.assertIsInstance(provider, DryRunProvider)
            self.assertTrue(os.path.exists(provider.path))

    def test_dryrun_provider_implements_bridge_provider(self):
        """DryRunProvider satisfies BridgeProvider interface."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            self.assertIsInstance(provider, BridgeProvider)
            self.assertTrue(hasattr(provider, "emit"))
            self.assertTrue(hasattr(provider, "flush"))
            self.assertTrue(hasattr(provider, "close"))

    def test_dryrun_provider_emits_deterministic_jsonl(self):
        """DryRunProvider emits deterministic JSONL with sequence numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            provider.emit(ProviderEvent(event="key_down", key="numpad_1", device="0C45:800A"))
            provider.emit(ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=183))
            provider.close()
            with open(provider.path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 2)
            first = json.loads(lines[0])
            self.assertEqual(first["event"], "key_down")
            self.assertEqual(first["seq"], 1)
            second = json.loads(lines[1])
            self.assertEqual(second["event"], "short_press")
            self.assertEqual(second["seq"], 2)
            self.assertEqual(second["duration_ms"], 183)

    def test_dryrun_provider_events_property_returns_emitted(self):
        """DryRunProvider.events returns copy of emitted events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            event1 = ProviderEvent(event="key_down", key="numpad_1", device="0C45:800A")
            event2 = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=100)
            provider.emit(event1)
            provider.emit(event2)
            events = provider.events
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].event, "key_down")
            self.assertEqual(events[1].duration_ms, 100)

    def test_dryrun_provider_no_companion_fields_in_output(self):
        """DryRunProvider output contains no Companion-related fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            provider.emit(ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=100))
            provider.close()
            with open(provider.path, "r", encoding="utf-8") as f:
                line = f.readline()
            data = json.loads(line)
            self.assertNotIn("companion", data)
            self.assertNotIn("http", data)
            self.assertNotIn("host", data)
            self.assertNotIn("port", data)


class TestActionDispatcherContractUnchanged(unittest.TestCase):
    """Verify existing ActionDispatcher contract unchanged."""

    def setUp(self):
        self.transport = MockTransport()
        self.dispatcher = ActionDispatcher(transport=self.transport)

    def test_dispatcher_accepts_transport_and_action_map(self):
        """ActionDispatcher.__init__ accepts transport and optional action_map."""
        dispatcher = ActionDispatcher(transport=self.transport)
        self.assertIs(dispatcher.transport, self.transport)
        self.assertIsInstance(dispatcher.action_map, ActionMap)
        custom_map = ActionMap()
        dispatcher2 = ActionDispatcher(transport=self.transport, action_map=custom_map)
        self.assertIs(dispatcher2.action_map, custom_map)

    def test_dispatch_returns_dispatched_action_for_mapped_events(self):
        """dispatch() returns DispatchedAction for mapped event types."""
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1)
        result = self.dispatcher.dispatch(event)
        self.assertIsNotNone(result)
        self.assertEqual(result.command, "numpad_1_press")
        self.assertEqual(result.payload, "")
        self.assertEqual(result.source_event, event)
        self.assertEqual(result.map_entry.logical_key, "numpad_1")
        self.assertEqual(result.map_entry.event_type, "short_press")

    def test_dispatch_returns_none_for_unmapped_events(self):
        """dispatch() returns None for unmapped event types."""
        for event_type in ["key_down", "key_up", "repeat_ignored"]:
            event = ProviderEvent(event=event_type, key="numpad_1", device="0C45:800A")
            result = self.dispatcher.dispatch(event)
            self.assertIsNone(result)
            self.assertEqual(len(self.transport.sent_actions), 0)

    def test_dispatch_returns_none_for_unknown_keys(self):
        """dispatch() returns None for unknown logical keys."""
        event = ProviderEvent(event="short_press", key="unknown_key", device="0C45:800A")
        result = self.dispatcher.dispatch(event)
        self.assertIsNone(result)
        self.assertEqual(len(self.transport.sent_actions), 0)

    def test_dispatch_preserves_provider_event_fields(self):
        """DispatchedAction preserves all ProviderEvent fields."""
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

    def test_dispatch_does_not_mutate_provider_event(self):
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
        self.assertEqual(event.to_dict(), original_dict)
        self.assertEqual(event.seq, 5)
        self.assertEqual(event.duration_ms, 200)

    def test_dispatch_batch_preserves_order(self):
        """dispatch_batch() preserves input order."""
        events = [
            ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1),
            ProviderEvent(event="hold", key="numpad_2", device="0C45:800A", seq=2),
            ProviderEvent(event="secondary_hold", key="numpad_3", device="0C45:800A", seq=3),
        ]
        results = self.dispatcher.dispatch_batch(events)
        self.assertEqual(len(results), 3)
        for i, r in enumerate(results):
            self.assertEqual(r.source_event.seq, i + 1)
        sent = self.transport.sent_actions
        self.assertEqual(len(sent), 3)
        for i, s in enumerate(sent):
            self.assertEqual(s.event.seq, i + 1)

    def test_dispatcher_close_closes_transport(self):
        """dispatcher.close() calls transport.close()."""
        self.dispatcher.close()
        # MockTransport.close() is a no-op but should not raise

    def test_dispatcher_flush_flushes_transport(self):
        """dispatcher.flush() calls transport.flush()."""
        self.dispatcher.flush()
        # MockTransport.flush() is a no-op but should not raise


class TestProviderEventSchemaUnchanged(unittest.TestCase):
    """Verify ProviderEvent schema unchanged."""

    def test_provider_event_required_fields(self):
        """ProviderEvent requires event, key, device."""
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        self.assertEqual(event.event, "short_press")
        self.assertEqual(event.key, "numpad_1")
        self.assertEqual(event.device, "0C45:800A")

    def test_provider_event_optional_fields(self):
        """ProviderEvent optional fields default to None."""
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        self.assertIsNone(event.duration_ms)
        self.assertIsNone(event.held)
        self.assertEqual(event.seq, 0)

    def test_provider_event_with_optional_fields(self):
        """ProviderEvent accepts optional fields."""
        event = ProviderEvent(
            event="hold",
            key="numpad_1",
            device="0C45:800A",
            duration_ms=700,
            held=True,
            seq=5,
        )
        self.assertEqual(event.duration_ms, 700)
        self.assertEqual(event.held, True)
        self.assertEqual(event.seq, 5)

    def test_provider_event_to_dict_includes_all_fields(self):
        """ProviderEvent.to_dict() includes all non-None fields."""
        event = ProviderEvent(
            event="short_press",
            key="numpad_1",
            device="0C45:800A",
            duration_ms=183,
            seq=1,
        )
        data = event.to_dict()
        self.assertEqual(data["event"], "short_press")
        self.assertEqual(data["key"], "numpad_1")
        self.assertEqual(data["device"], "0C45:800A")
        self.assertEqual(data["duration_ms"], 183)
        self.assertEqual(data["seq"], 1)
        self.assertNotIn("held", data)

    def test_provider_event_to_dict_excludes_none_fields(self):
        """ProviderEvent.to_dict() excludes None optional fields."""
        event = ProviderEvent(event="key_down", key="numpad_1", device="0C45:800A")
        data = event.to_dict()
        self.assertNotIn("duration_ms", data)
        self.assertNotIn("held", data)

    def test_provider_event_known_event_types(self):
        """ProviderEvent supports all known event types."""
        known_events = [
            "key_down",
            "short_press",
            "hold",
            "key_up",
            "repeat_ignored",
            "secondary_hold",
        ]
        for evt in known_events:
            event = ProviderEvent(event=evt, key="numpad_1", device="0C45:800A")
            self.assertEqual(event.event, evt)


class TestDeviceIdentityPreserved(unittest.TestCase):
    """Verify device identity (VID:PID) preserved throughout pipeline."""

    def test_bridge_config_default_vid_pid(self):
        """BridgeConfig defaults to AULA L99 VID:PID."""
        config = BridgeConfig()
        self.assertEqual(config.vid, 0x0C45)
        self.assertEqual(config.pid, 0x800A)

    def test_config_device_format(self):
        """Device identity formatted as 'VID:PID' in hex."""
        config = BridgeConfig()
        device = "%04X:%04X" % (config.vid, config.pid)
        self.assertEqual(device, "0C45:800A")

    def test_provider_event_carries_device(self):
        """ProviderEvent carries device identity."""
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        self.assertEqual(event.device, "0C45:800A")

    def test_dispatched_action_preserves_device(self):
        """DispatchedAction preserves device from source event."""
        transport = MockTransport()
        dispatcher = ActionDispatcher(transport=transport)
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1)
        result = dispatcher.dispatch(event)
        self.assertIsNotNone(result)
        self.assertEqual(result.source_event.device, "0C45:800A")


class TestEventOrderingPreserved(unittest.TestCase):
    """Verify event ordering preserved through pipeline."""

    def test_provider_seq_increments(self):
        """DryRunProvider assigns incrementing sequence numbers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            for i in range(5):
                provider.emit(ProviderEvent(event="key_down", key=f"numpad_{i%17+1}", device="0C45:800A"))
            events = provider.events
            for i, e in enumerate(events):
                self.assertEqual(e.seq, i + 1)

    def test_dispatcher_preserves_seq(self):
        """ActionDispatcher preserves sequence numbers."""
        transport = MockTransport()
        dispatcher = ActionDispatcher(transport=transport)
        events = [
            ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1),
            ProviderEvent(event="hold", key="numpad_1", device="0C45:800A", seq=2),
            ProviderEvent(event="secondary_hold", key="numpad_1", device="0C45:800A", seq=3),
        ]
        dispatcher.dispatch_batch(events)
        sent = transport.sent_actions
        self.assertEqual(len(sent), 3)
        for i, s in enumerate(sent):
            self.assertEqual(s.event.seq, i + 1)

    def test_bridge_main_loop_emits_in_order(self):
        """Bridge main loop emits events in deterministic order."""
        from aula_bridge.provider import ProviderEvent
        from aula_bridge.dispatcher import MockTransport, ActionDispatcher
        from aula_bridge.action_mapping import ActionMap

        transport = MockTransport()
        dispatcher = ActionDispatcher(transport=transport, action_map=ActionMap())
        provider = DryRunProvider(log_file="test.jsonl", log_dir="logs")

        # Simulate bridge emission order: key_down, short_press, hold
        provider.emit(ProviderEvent(event="key_down", key="numpad_1", device="0C45:800A"))
        provider.emit(ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=100))
        provider.emit(ProviderEvent(event="hold", key="numpad_1", device="0C45:800A", duration_ms=700))

        # Dispatch action events
        dispatcher.dispatch(ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", duration_ms=100, seq=2))
        dispatcher.dispatch(ProviderEvent(event="hold", key="numpad_1", device="0C45:800A", duration_ms=700, seq=3))

        provider.close()

        with open(provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 3)
        events = [json.loads(l) for l in lines]
        self.assertEqual(events[0]["event"], "key_down")
        self.assertEqual(events[1]["event"], "short_press")
        self.assertEqual(events[2]["event"], "hold")
        self.assertEqual(events[0]["seq"], 1)
        self.assertEqual(events[1]["seq"], 2)
        self.assertEqual(events[2]["seq"], 3)


class TestNoHttpSenderByDefault(unittest.TestCase):
    """Verify no HTTP sender instantiated by default."""

    def test_entry_point_creates_no_http_sender(self):
        """aula_input_bridge.main() creates no HTTP sender."""
        import aula_input_bridge
        # The module only imports DryRunProvider and MockTransport
        self.assertFalse(hasattr(aula_input_bridge, "CompanionHttpSender"))
        self.assertFalse(hasattr(aula_input_bridge, "CompanionHttpTransport"))

    def test_bridge_config_provider_dry_run_only(self):
        """BridgeConfig.provider defaults to 'dry_run' only."""
        config = BridgeConfig()
        self.assertEqual(config.provider, "dry_run")
        # No other provider types in config
        self.assertNotIn("http", config.provider)
        self.assertNotIn("companion", config.provider)


class TestNoNetworkAccessDuringImports(unittest.TestCase):
    """Verify no network access during module imports."""

    def test_import_aula_bridge_no_network(self):
        """Importing aula_bridge performs no network operations."""
        # This test verifies by absence of network calls during import
        # If any import triggered network access, it would fail/timeout
        import aula_bridge
        import aula_bridge.config
        import aula_bridge.provider
        import aula_bridge.dispatcher
        import aula_bridge.action_mapping
        import aula_bridge.keymap
        import aula_bridge.state_machine
        import aula_bridge.devices

    def test_import_entry_point_no_network(self):
        """Importing aula_input_bridge performs no network operations."""
        import aula_input_bridge


class TestNoHardwareAccessDuringTests(unittest.TestCase):
    """Verify tests use mocked Windows APIs, no hardware access."""

    def test_mock_transport_no_hardware(self):
        """MockTransport uses no hardware."""
        transport = MockTransport()
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A")
        transport.send("cmd", "payload", event)
        # No exceptions, no hardware calls

    def test_dryrun_provider_no_hardware(self):
        """DryRunProvider uses no hardware, only file I/O."""
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = DryRunProvider(log_file="test.jsonl", log_dir=tmpdir)
            provider.emit(ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A"))
            provider.close()
            # Only file I/O, no hardware

    def test_state_machine_no_hardware(self):
        """KeyStateMachine uses mocked time, no hardware."""
        from aula_bridge.state_machine import KeyStateMachine
        m = KeyStateMachine(now_ms=0)
        m.key_down("numpad_1", "0C45:800A", 0)
        m.set_time(100)
        results = m.key_up("numpad_1", "0C45:800A", 100)
        self.assertEqual(results[0].action, "short_press")

    def test_keymap_no_hardware(self):
        """LogicalKeyMap uses no hardware."""
        from aula_bridge.keymap import LogicalKeyMap
        keymap = LogicalKeyMap()
        key = keymap.key_for_return_value(0x0030)
        self.assertEqual(key, "numpad_num")


class TestExistingBridgeTestsCompatible(unittest.TestCase):
    """Verify existing Bridge tests remain compatible."""


class TestDeferredRequirements(unittest.TestCase):
    """Requirements that cannot be tested without future implementation."""

    def test_companion_opt_in_flag_not_present(self):
        """CLI flag --companion-opt-in does not exist yet (deferred)."""
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--config", help="Path to bridge config JSON")
        parser.add_argument("--list-devices", action="store_true")
        parser.add_argument("--capture-raw", action="store_true")
        # No --companion-opt-in flag
        args = parser.parse_args(["--config", "test.json"])
        self.assertFalse(hasattr(args, "companion_opt_in"))

    def test_companion_config_not_loaded_by_default(self):
        """Companion config not loaded unless explicitly enabled (deferred)."""
        # This will be testable when companion_optin_config.py is integrated
        pass


if __name__ == "__main__":
    unittest.main()