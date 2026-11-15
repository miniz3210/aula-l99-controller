"""Deterministic offline contract tests for the CLI + JSON dual-gate Companion activation contract.

Tests existing executable behavior only. No future production APIs are invented.
No network access, no hardware access, no firmware changes.
"""

from __future__ import annotations

import json
import math
import os
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# Import existing production modules under test.
from aula_bridge.companion_optin_config import (
    CompanionOptInConfig,
    CompanionOptInConfigError,
    load,
)
from aula_bridge.companion_button_mapping import (
    CompanionButtonMappingError,
    load_companion_button_mapping,
)
from aula_bridge.dispatcher import ActionDispatcher, MockTransport
from aula_bridge.provider import DryRunProvider, ProviderEvent
from aula_bridge.action_mapping import ActionMap

import aula_input_bridge


def _write_tmp(content: str) -> str:
    """Write content to a temporary JSON file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="activation_contract_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TestActivationContract(unittest.TestCase):
    """Contract tests for the dual-gate (CLI + JSON) Companion activation."""

    # ----- 1. Config loader defaults to disabled -----

    def test_config_loader_defaults_to_disabled(self):
        """Default (no-arg) load returns a disabled Companion config."""
        config = load()
        self.assertIsInstance(config, CompanionOptInConfig)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)

    # ----- 2. Missing config returns disabled defaults -----

    def test_missing_config_returns_disabled_defaults(self):
        """load(None) returns disabled defaults."""
        config = load(None)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    def test_nonexistent_config_returns_disabled_defaults(self):
        """Nonexistent file path returns disabled defaults."""
        config = load(os.path.join(tempfile.gettempdir(), "nonexistent_activation.json"))
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    # ----- 3. JSON enabled=true requires mapping file -----

    def test_enabled_requires_mapping_file(self):
        """companion.enabled=true without mapping_file raises CompanionOptInConfigError."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {"enabled": True, "host": "127.0.0.1"},
                    }
                )
            )
        self.assertIn("mapping_file", str(ctx.exception))

    def test_enabled_with_mapping_file_accepted(self):
        """companion.enabled=true with a mapping_file is accepted."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config = self._load(
            json.dumps(
                {
                    "version": 1,
                    "companion": {
                        "enabled": True,
                        "mapping_file": mapping_path,
                    },
                }
            )
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.mapping_file, mapping_path)

    # ----- 4. Invalid JSON fails validation -----

    def test_invalid_json_fails_validation(self):
        """Malformed JSON raises CompanionOptInConfigError."""
        path = _write_tmp("{not valid json")
        self.addCleanup(os.remove, path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            load(path)
        self.assertIn("Malformed JSON", str(ctx.exception))

    # ----- 5. Unknown config fields rejected -----

    def test_unknown_top_level_field_rejected(self):
        """Unknown top-level field raises CompanionOptInConfigError."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "bogus_field": "value",
                    }
                )
            )
        self.assertIn("Unknown top-level fields", str(ctx.exception))

    def test_unknown_companion_field_rejected(self):
        """Unknown companion field raises CompanionOptInConfigError."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "mapping_file": "mapping.json",
                            "bogus_field": "value",
                        },
                    }
                )
            )
        self.assertIn("Unknown companion fields", str(ctx.exception))

    # ----- 6. Invalid host rejected -----

    def test_invalid_host_rejected(self):
        """Non-numeric host raises CompanionOptInConfigError."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "host": "not-an-ip",
                            "mapping_file": mapping_path,
                        },
                    }
                )
            )
        self.assertIn("Invalid host address", str(ctx.exception))

    def test_non_loopback_host_rejected(self):
        """Non-loopback host raises CompanionOptInConfigError."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "host": "192.168.1.1",
                            "mapping_file": mapping_path,
                        },
                    }
                )
            )
        self.assertIn("Non-loopback host rejected", str(ctx.exception))

    # ----- 7. Invalid port rejected -----

    def test_invalid_port_rejected(self):
        """Out-of-range port raises CompanionOptInConfigError."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        for bad_port in (0, -1, 65536):
            with self.subTest(port=bad_port):
                with self.assertRaises(CompanionOptInConfigError):
                    self._load(
                        json.dumps(
                            {
                                "version": 1,
                                "companion": {
                                    "enabled": True,
                                    "port": bad_port,
                                    "mapping_file": mapping_path,
                                },
                            }
                        )
                    )

    # ----- 8. Invalid timeout rejected -----

    def test_invalid_timeout_rejected(self):
        """Non-positive or non-finite timeout raises CompanionOptInConfigError."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        for bad_timeout in (0, -1.0, math.inf, float("nan"), True):
            with self.subTest(timeout=bad_timeout):
                with self.assertRaises(CompanionOptInConfigError):
                    self._load(
                        json.dumps(
                            {
                                "version": 1,
                                "companion": {
                                    "enabled": True,
                                    "timeout": bad_timeout,
                                    "mapping_file": mapping_path,
                                },
                            }
                        )
                    )

    # ----- 9. No default button mappings -----

    def test_no_default_button_mappings(self):
        """Empty mapping file returns an empty immutable mapping (no defaults)."""
        mapping_path = _write_tmp(json.dumps({"version": 1, "mappings": {}}))
        self.addCleanup(os.remove, mapping_path)
        result = load_companion_button_mapping(mapping_path)
        from types import MappingProxyType

        self.assertEqual(len(result), 0)
        self.assertIsInstance(result, MappingProxyType)

    # ----- 10. Config loading performs no network I/O -----

    def test_config_loading_performs_no_network_io(self):
        """Loading config performs no network I/O (pure local file read only)."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config_path = _write_tmp(
            json.dumps(
                {
                    "version": 1,
                    "companion": {
                        "enabled": True,
                        "host": "127.0.0.1",
                        "port": 8000,
                        "timeout": 5.0,
                        "mapping_file": mapping_path,
                    },
                }
            )
        )
        self.addCleanup(os.remove, config_path)

        # If any socket is created during load, raise immediately.
        real_socket = socket.socket

        def _fail_socket(*args, **kwargs):
            raise AssertionError("socket.socket must not be instantiated during config load")

        with patch("socket.socket", side_effect=_fail_socket):
            config = load(config_path)

        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)

    # ----- 11. Existing Bridge CLI remains unchanged -----

    def test_bridge_cli_original_flags_still_work(self):
        """Original three flags parse successfully."""
        ns = aula_input_bridge.parse_args(["--config", "c.json"])
        self.assertEqual(ns.config, "c.json")
        ns = aula_input_bridge.parse_args(["--list-devices"])
        self.assertTrue(ns.list_devices)
        ns = aula_input_bridge.parse_args(["--capture-raw"])
        self.assertTrue(ns.capture_raw)
        ns = aula_input_bridge.parse_args([])
        self.assertIsNone(ns.config)
        self.assertFalse(ns.list_devices)
        self.assertFalse(ns.capture_raw)

    def test_bridge_cli_new_companion_flags(self):
        """New Companion flags are recognized."""
        ns = aula_input_bridge.parse_args(["--enable-companion"])
        self.assertTrue(ns.enable_companion)
        self.assertIsNone(ns.companion_config)
        ns = aula_input_bridge.parse_args(["--enable-companion", "--companion-config", "path.json"])
        self.assertTrue(ns.enable_companion)
        self.assertEqual(ns.companion_config, "path.json")
        ns = aula_input_bridge.parse_args(["--companion-config", "path.json"])
        self.assertFalse(ns.enable_companion)
        self.assertEqual(ns.companion_config, "path.json")

    def test_bridge_cli_help_contains_new_flags(self):
        """CLI help text references new Companion flags."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                aula_input_bridge.parse_args(["--help"])
            except SystemExit:
                pass
        text = buf.getvalue()
        self.assertIn("--config", text)
        self.assertIn("--list-devices", text)
        self.assertIn("--capture-raw", text)
        self.assertIn("--enable-companion", text)
        self.assertIn("--companion-config", text)

    # ----- 12. Existing MockTransport remains available -----

    def test_mock_transport_remains_available(self):
        """MockTransport is importable and records dispatched actions."""
        transport = MockTransport()
        dispatcher = ActionDispatcher(transport=transport, action_map=ActionMap())
        event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1)
        result = dispatcher.dispatch(event)
        self.assertIsNotNone(result)
        self.assertEqual(len(transport.sent_actions), 1)

    def test_mock_transport_clear_and_order(self):
        """MockTransport.clear() and ordering still work."""
        transport = MockTransport()
        dispatcher = ActionDispatcher(transport=transport, action_map=ActionMap())
        events = [
            ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=i)
            for i in range(1, 4)
        ]
        dispatcher.dispatch_batch(events)
        self.assertEqual(len(transport.sent_actions), 3)
        transport.clear()
        self.assertEqual(len(transport.sent_actions), 0)

    def test_mock_transport_flush_and_close_noop(self):
        """MockTransport.flush() and close() are no-ops."""
        transport = MockTransport()
        transport.flush()
        transport.close()

    # ----- 13. DryRunProvider remains unchanged -----

    def test_dryrun_provider_remains_available(self):
        """DryRunProvider is importable and logs events deterministically."""
        import tempfile as _tf

        log_dir = _tf.mkdtemp(prefix="dryrun_contract_")
        provider = DryRunProvider(log_file="contract.jsonl", log_dir=log_dir)
        try:
            event = ProviderEvent(
                event="short_press", key="numpad_1", device="0C45:800A", duration_ms=100, seq=0
            )
            provider.emit(event)
            provider.close()
            with open(provider.path, "r", encoding="utf-8") as fh:
                line = fh.read().strip()
            data = json.loads(line)
            self.assertEqual(data["event"], "short_press")
            self.assertEqual(data["key"], "numpad_1")
            self.assertEqual(data["seq"], 1)
        finally:
            provider.close()

    def test_dryrun_provider_no_companion_fields(self):
        """DryRunProvider log contains no Companion-specific fields."""
        import tempfile as _tf

        log_dir = _tf.mkdtemp(prefix="dryrun_contract_")
        provider = DryRunProvider(log_file="contract.jsonl", log_dir=log_dir)
        try:
            provider.emit(ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1))
            provider.close()
            with open(provider.path, "r", encoding="utf-8") as fh:
                data = json.loads(fh.read().strip())
            for field in ("companion", "http", "button", "page", "row", "column", "host", "port"):
                self.assertNotIn(field, data)
        finally:
            provider.close()

    # ----- Helpers -----

    def _load(self, content: str) -> CompanionOptInConfig:
        path = _write_tmp(content)
        self.addCleanup(os.remove, path)
        return load(path)


if __name__ == "__main__":
    unittest.main()
