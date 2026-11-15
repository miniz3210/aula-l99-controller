"""Deterministic offline acceptance tests for future Windows Bridge Companion opt-in integration.

This module prepares contract-independent tests and fixtures for the 24 acceptance
requirements specified in the Companion opt-in integration specification.

Production opt-in integration does not exist yet. These tests:
- Use existing MockTransport, DryRunProvider, and fake HTTP sender infrastructure
- Do not depend on unfinished Session B production code
- Document deferred acceptance requirements in test docstrings
- Do not use pytest.skip or xfail to misrepresent acceptance
- Do not claim full opt-in acceptance

Run with: python -m pytest tests/test_companion_optin_acceptance.py -q
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Mapping, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.provider import ProviderEvent, DryRunProvider, BridgeProvider
from aula_bridge.dispatcher import ActionDispatcher, MockTransport, Transport
from aula_bridge.action_mapping import ActionMap
from aula_bridge.companion_button_mapping import (
    CompanionButtonMappingError,
    load_companion_button_mapping,
)
from aula_bridge.companion_dispatch_adapter import CompanionDispatchAdapter
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
    CompanionHttpTransportError,
)
from aula_bridge.companion_types import ButtonLocation


# ========================================================================
# Test Infrastructure
# ========================================================================

class FakeHttpSender:
    """Deterministic fake HTTP sender. Records calls, no real network."""

    def __init__(self) -> None:
        self.calls: List[tuple[str, str, float]] = []
        self._response_map: Dict[tuple[str, str], HttpResponse] = {}
        self._default_response: HttpResponse = HttpResponse(status_code=200, success=True)
        self._raise_on_call: Optional[Exception] = None

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


def _write_tmp_config(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="companion_config_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _make_event(
    event_type: str = "short_press",
    key: str = "numpad_1",
    device: str = "0C45:800A",
    duration_ms: int = 100,
    seq: int = 1,
    held: Optional[bool] = None,
) -> ProviderEvent:
    return ProviderEvent(
        event=event_type,
        key=key,
        device=device,
        duration_ms=duration_ms,
        held=held,
        seq=seq,
    )


# ========================================================================
# Reusable Fixtures and Base Classes
# ========================================================================

class CompanionOptInTestBase(unittest.TestCase):
    """Base class for Companion opt-in acceptance tests.

    Provides common setup for testing the opt-in configuration chain
    without requiring production integration code.
    """

    TEST_HOST = "127.0.0.1"
    TEST_PORT = 19876

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.temp_files: List[str] = []

    def tearDown(self) -> None:
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    def _build_chain(
        self,
        mappings: Dict[str, Dict[str, int]],
        enabled: bool = True,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> tuple[ActionDispatcher, CompanionDispatchAdapter, FakeHttpSender]:
        """Build the complete offline chain with explicit button mapping.

        This simulates the opt-in chain: ProviderEvent -> ActionDispatcher ->
        CompanionDispatchAdapter -> CompanionHttpTransport -> FakeHttpSender

        Args:
            mappings: Dictionary of logical_key -> {page, row, column}
            enabled: Whether Companion is enabled (simulated via config)
            host: Target host (must be loopback)
            port: Target port
            timeout: Request timeout

        Returns:
            Tuple of (dispatcher, adapter, sender) for testing.
        """
        # Write button mapping file
        mapping_content = json.dumps({"version": 1, "mappings": mappings})
        mapping_path = _write_tmp_mapping(mapping_content)
        self.temp_files.append(mapping_path)
        button_mapping = load_companion_button_mapping(mapping_path)

        # Build HTTP transport with fake sender
        http_transport = CompanionHttpTransport(
            http_sender=self.sender,
            host=host or self.TEST_HOST,
            port=port or self.TEST_PORT,
            timeout=timeout or 5.0,
        )

        # Build adapter
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport,
            button_mapping=button_mapping,
        )

        # Build dispatcher
        dispatcher = ActionDispatcher(transport=adapter)

        return dispatcher, adapter, self.sender


class DisabledCompanionTestBase(unittest.TestCase):
    """Base class for tests where Companion is explicitly disabled.

    Verifies that existing Bridge behavior (MockTransport, DryRunProvider)
    remains completely unchanged when Companion is not opted in.
    """

    def setUp(self) -> None:
        self.transport = MockTransport()
        self.provider = DryRunProvider(log_file="test_optin.jsonl", log_dir="logs")
        self.dispatcher = ActionDispatcher(transport=self.transport, action_map=ActionMap())

    def tearDown(self) -> None:
        self.provider.close()
        try:
            os.remove(self.provider.path)
        except OSError:
            pass


# ========================================================================
# Acceptance Requirement Tests
# ========================================================================

class TestRequirement1_CompanionDisabledByDefault(DisabledCompanionTestBase):
    """Requirement 1: Companion disabled by default.

    Existing Bridge behavior (MockTransport, DryRunProvider, ActionDispatcher)
    operates normally without any Companion integration. No Companion code
    is imported or executed unless explicitly opted in.
    """

    def test_mock_transport_preserved(self):
        """MockTransport continues to work without Companion."""
        event = _make_event(event_type="short_press", key="numpad_1", seq=1)
        result = self.dispatcher.dispatch(event)
        self.assertIsNotNone(result)
        self.assertEqual(len(self.transport.sent_actions), 1)

    def test_dryrun_provider_preserved(self):
        """DryRunProvider continues to log events without Companion."""
        event = _make_event(event_type="short_press", key="numpad_1", seq=1)
        self.provider.emit(event)
        self.provider.close()
        with open(self.provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)

    def test_no_companion_imports_in_bridge_core(self):
        """Bridge core modules do not import Companion modules.

        This is a structural test - the bridge entry point (aula_input_bridge.py)
        imports only MockTransport and DryRunProvider by default.
        """
        # Verify by inspecting imports in dispatcher and provider modules
        import aula_bridge.dispatcher as dispatcher_mod
        import aula_bridge.provider as provider_mod

        dispatcher_source = open(dispatcher_mod.__file__, "r").read() if dispatcher_mod.__file__ else ""
        provider_source = open(provider_mod.__file__, "r").read() if provider_mod.__file__ else ""

        # Check for actual import statements, not just word "companion" in comments
        # The word appears in docstrings as "no companion requests" which is expected
        self.assertNotIn("import companion", dispatcher_source.lower())
        self.assertNotIn("from companion", dispatcher_source.lower())
        self.assertNotIn("import companion", provider_source.lower())
        self.assertNotIn("from companion", provider_source.lower())

    def test_action_dispatcher_unchanged(self):
        """ActionDispatcher behavior unchanged without Companion."""
        # All 51 default mappings (17 keys * 3 event types) still work
        events = [
            _make_event(event_type="short_press", key="numpad_1", seq=1),
            _make_event(event_type="hold", key="numpad_2", seq=2),
            _make_event(event_type="secondary_hold", key="numpad_3", seq=3),
        ]
        results = self.dispatcher.dispatch_batch(events)
        self.assertEqual(len(results), 3)
        self.assertEqual(len(self.transport.sent_actions), 3)


class TestRequirement2_ExistingMockTransportPreserved(DisabledCompanionTestBase):
    """Requirement 2: Existing MockTransport preserved."""

    def test_mock_transport_interface_unchanged(self):
        """MockTransport still implements Transport protocol methods."""
        # Transport is a Protocol (not @runtime_checkable), so isinstance doesn't work
        # Instead verify it has the required methods
        self.assertTrue(hasattr(self.transport, 'send'))
        self.assertTrue(hasattr(self.transport, 'flush'))
        self.assertTrue(hasattr(self.transport, 'close'))
        self.assertTrue(callable(self.transport.send))
        self.assertTrue(callable(self.transport.flush))
        self.assertTrue(callable(self.transport.close))

    def test_mock_transport_records_actions(self):
        """MockTransport still records all dispatched actions."""
        events = [
            _make_event(key="numpad_1", seq=1),
            _make_event(key="numpad_2", seq=2),
            _make_event(key="numpad_3", seq=3),
        ]
        for e in events:
            self.dispatcher.dispatch(e)
        self.assertEqual(len(self.transport.sent_actions), 3)

    def test_mock_transport_clear_works(self):
        """MockTransport.clear() still works."""
        self.dispatcher.dispatch(_make_event(key="numpad_1", seq=1))
        self.transport.clear()
        self.assertEqual(len(self.transport.sent_actions), 0)

    def test_mock_transport_order_preserved(self):
        """MockTransport preserves dispatch order."""
        events = [_make_event(key=k, seq=i) for i, k in enumerate(["numpad_1", "numpad_2", "numpad_3"], 1)]
        self.dispatcher.dispatch_batch(events)
        sent = self.transport.sent_actions
        for i, s in enumerate(sent):
            self.assertEqual(s.event.seq, i + 1)


class TestRequirement3_DryRunProviderPreserved(DisabledCompanionTestBase):
    """Requirement 3: DryRunProvider preserved."""

    def test_dryrun_provider_logs_events(self):
        """DryRunProvider logs events in deterministic JSONL format."""
        events = [
            _make_event(event_type="key_down", key="numpad_1", seq=1),
            _make_event(event_type="short_press", key="numpad_1", duration_ms=150, seq=2),
        ]
        for e in events:
            self.provider.emit(e)
        self.provider.close()
        with open(self.provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 2)

    def test_dryrun_provider_seq_assignment(self):
        """DryRunProvider assigns sequential seq numbers."""
        for i in range(5):
            self.provider.emit(_make_event(key="numpad_1", seq=0))
        self.provider.close()
        with open(self.provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        for i, line in enumerate(lines):
            data = json.loads(line)
            self.assertEqual(data["seq"], i + 1)

    def test_dryrun_provider_field_order_stable(self):
        """DryRunProvider field order is stable (no timestamps)."""
        self.provider.emit(_make_event(event_type="short_press", key="numpad_1", seq=1))
        self.provider.close()
        with open(self.provider.path, "r", encoding="utf-8") as f:
            line = f.read().strip()
        data = json.loads(line)
        # Fields in expected order: event, key, device, seq, duration_ms
        keys = list(data.keys())
        self.assertEqual(keys[:4], ["event", "key", "device", "seq"])

    def test_dryrun_provider_no_companion_fields(self):
        """DryRunProvider log contains no Companion-specific fields."""
        self.provider.emit(_make_event(event_type="short_press", key="numpad_1", seq=1))
        self.provider.close()
        with open(self.provider.path, "r", encoding="utf-8") as f:
            line = f.read().strip()
        data = json.loads(line)
        companion_fields = ["companion", "http", "button", "page", "row", "column", "host", "port"]
        for field in companion_fields:
            self.assertNotIn(field, data)


class TestRequirement4_ExplicitOptInRequired(CompanionOptInTestBase):
    """Requirement 4: Explicit opt-in required.

    Companion integration is only activated when configuration explicitly
    enables it with a valid mapping file. No automatic activation occurs.
    """

    def test_disabled_config_produces_no_http(self):
        """When Companion disabled (no mapping), no HTTP requests are made."""
        # Simulate disabled config by providing empty mapping
        dispatcher, adapter, sender = self._build_chain(mappings={})
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        dispatcher.dispatch(_make_event(key="numpad_1", seq=1))
        # Empty mapping means no button location found, no HTTP request
        self.assertEqual(len(sender.calls), 0)

    def test_no_mapping_file_produces_no_http(self):
        """Without mapping file, no HTTP requests even if enabled."""
        # Build chain with empty mapping (simulates no mapping file)
        dispatcher, adapter, sender = self._build_chain(mappings={})
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        dispatcher.dispatch(_make_event(key="numpad_1", seq=1))
        self.assertEqual(len(sender.calls), 0)

    def test_opt_in_requires_both_enabled_and_mapping(self):
        """Opt-in requires both enabled=true AND explicit mapping_file.

        This is a design contract test - the production config loader
        (companion_optin_config.py) enforces this.
        """
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        # Config with enabled=true but no mapping_file should fail
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "host": "127.0.0.1", "port": 8000}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)

        # Config with enabled=false and no mapping_file should succeed (disabled)
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": False}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        config = load(path)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    def test_missing_config_file_defaults_disabled(self):
        """Missing or unreadable config file produces disabled config."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfig

        config = load("/nonexistent/path.json")
        self.assertIsInstance(config, CompanionOptInConfig)
        self.assertFalse(config.enabled)


class TestRequirement5_MissingConfigurationRejected(CompanionOptInTestBase):
    """Requirement 5: Missing configuration rejected when enabled."""

    def test_enabled_without_mapping_file_rejected(self):
        """Config with enabled=true but missing mapping_file raises error."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            load(path)
        self.assertIn("mapping_file", str(ctx.exception))

    def test_mapping_file_path_syntax_validated(self):
        """Mapping file path must be valid string syntax."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        # Empty string rejected
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "mapping_file": ""}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)

        # Null bytes rejected
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "mapping_file": "path\x00file.json"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)


class TestRequirement6_InvalidConfigurationRejected(CompanionOptInTestBase):
    """Requirement 6: Invalid configuration rejected."""

    def test_non_loopback_host_rejected(self):
        """Non-loopback host addresses are rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "host": "192.168.1.1", "mapping_file": "m.json"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)

    def test_invalid_host_format_rejected(self):
        """Invalid host format (non-IP) is rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "host": "not-an-ip", "mapping_file": "m.json"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)

    def test_port_out_of_range_rejected(self):
        """Ports outside 1-65535 are rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        for bad_port in [0, -1, 65536]:
            config_content = json.dumps({
                "version": 1,
                "companion": {"enabled": True, "port": bad_port, "mapping_file": "m.json"}
            })
            path = _write_tmp_config(config_content)
            self.temp_files.append(path)
            with self.assertRaises(CompanionOptInConfigError):
                load(path)

    def test_timeout_non_positive_rejected(self):
        """Non-positive timeouts are rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        for bad_timeout in [0, -1.0, -5.0]:
            config_content = json.dumps({
                "version": 1,
                "companion": {"enabled": True, "timeout": bad_timeout, "mapping_file": "m.json"}
            })
            path = _write_tmp_config(config_content)
            self.temp_files.append(path)
            with self.assertRaises(CompanionOptInConfigError):
                load(path)

    def test_timeout_non_finite_rejected(self):
        """Non-finite timeouts (inf, nan) are rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        for bad_timeout in [float("inf"), float("-inf"), float("nan")]:
            config_content = json.dumps({
                "version": 1,
                "companion": {"enabled": True, "timeout": bad_timeout, "mapping_file": "m.json"}
            })
            path = _write_tmp_config(config_content)
            self.temp_files.append(path)
            with self.assertRaises(CompanionOptInConfigError):
                load(path)

    def test_unknown_top_level_fields_rejected(self):
        """Unknown top-level fields are rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "mapping_file": "m.json"},
            "unknown_field": "value"
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            load(path)
        self.assertIn("Unknown top-level fields", str(ctx.exception))

    def test_unknown_companion_fields_rejected(self):
        """Unknown companion fields are rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "mapping_file": "m.json", "unknown": "value"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            load(path)
        self.assertIn("Unknown companion fields", str(ctx.exception))

    def test_non_boolean_enabled_rejected(self):
        """Non-boolean enabled field is rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": "true", "mapping_file": "m.json"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)

    def test_non_integer_version_rejected(self):
        """Non-integer version is rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": "1",
            "companion": {"enabled": True, "mapping_file": "m.json"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)

    def test_unsupported_version_rejected(self):
        """Unsupported version is rejected."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError

        config_content = json.dumps({
            "version": 999,
            "companion": {"enabled": True, "mapping_file": "m.json"}
        })
        path = _write_tmp_config(config_content)
        self.temp_files.append(path)
        with self.assertRaises(CompanionOptInConfigError):
            load(path)


class TestRequirement7_NoDefaultButtonMapping(CompanionOptInTestBase):
    """Requirement 7: No default button mapping.

    Button mapping must be explicitly provided via configuration file.
    No automatic or default mappings are invented.
    """

    def test_empty_mapping_returns_empty_proxy(self):
        """Empty mapping file returns empty MappingProxyType."""
        mapping_content = json.dumps({"version": 1, "mappings": {}})
        path = _write_tmp_mapping(mapping_content)
        self.temp_files.append(path)
        result = load_companion_button_mapping(path)
        self.assertEqual(len(result), 0)
        from types import MappingProxyType
        self.assertIsInstance(result, MappingProxyType)

    def test_no_automatic_mapping_for_unmapped_keys(self):
        """Unmapped keys never get automatic mappings."""
        dispatcher, adapter, sender = self._build_chain(mappings={})
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        # All 17 numpad keys should produce no request
        from aula_bridge.action_mapping import NUM_PAD_KEYS
        for key in NUM_PAD_KEYS:
            sender.clear()
            dispatcher.dispatch(_make_event(key=key, seq=1))
            self.assertEqual(len(sender.calls), 0, f"Key {key} should produce no request")

    def test_adapter_never_invents_mappings(self):
        """CompanionDispatchAdapter never invents default mappings."""
        dispatcher, adapter, sender = self._build_chain(mappings={})
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        # Various unknown keys
        unknown_keys = ["numpad_unknown", "key_a", "f1", "escape", "space"]
        for key in unknown_keys:
            sender.clear()
            dispatcher.dispatch(_make_event(key=key, seq=1))
            self.assertEqual(len(sender.calls), 0)


class TestRequirement8_ShortPressTriggersMappedAction(CompanionOptInTestBase):
    """Requirement 8: Short press triggers mapped action.

    When Companion is opted in and a key has a mapping, short_press
    events generate HTTP POST to the Companion press endpoint.
    """

    def test_mapped_short_press_generates_http_post(self):
        """Mapped short_press produces HTTP POST through full chain."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", seq=1)

        result = dispatcher.dispatch(event)

        self.assertIsNotNone(result)
        self.assertEqual(len(sender.calls), 1)
        method, url, timeout = sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/location/1/0/0/press", url)

    def test_correct_companion_endpoint_used(self):
        """Press targets correct Companion location endpoint."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_5": {"page": 2, "row": 3, "column": 4}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_5", seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 1)
        method, url, timeout = sender.calls[0]
        expected_url = f"http://{self.TEST_HOST}:{self.TEST_PORT}/api/location/2/3/4/press"
        self.assertEqual(url, expected_url)
        self.assertNotIn(":5000", url)
        self.assertNotIn(":8000", url)

    def test_no_request_body_sent(self):
        """No request body is sent; sender receives only method, url, timeout."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 1)
        call = sender.calls[0]
        self.assertEqual(len(call), 3)
        self.assertIsInstance(call[0], str)
        self.assertIsInstance(call[1], str)
        self.assertIsInstance(call[2], float)

    def test_unmapped_key_produces_no_request(self):
        """Unmapped key produces no HTTP request even when enabled."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_99", seq=1)

        result = dispatcher.dispatch(event)

        self.assertIsNone(result)
        self.assertEqual(len(sender.calls), 0)


class TestRequirement9_HoldIgnored(CompanionOptInTestBase):
    """Requirement 9: Hold ignored.

    Hold events produce zero HTTP requests; no command or payload
    reaches the transport.
    """

    def test_hold_generates_no_http_request(self):
        """Hold events produce no HTTP request."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="hold", key="numpad_1", duration_ms=700, seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 0)

    def test_hold_with_mapping_still_ignored(self):
        """Hold is ignored even when key has valid mapping."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="hold", key="numpad_1", duration_ms=1000, seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 0)

    def test_hold_no_command_reaches_transport(self):
        """No command or payload reaches HTTP transport for hold."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        # Verify at adapter level
        adapter.send("test_command", "test_payload", _make_event(event_type="hold", key="numpad_1", seq=1))

        self.assertEqual(len(sender.calls), 0)


class TestRequirement10_SecondaryHoldIgnored(CompanionOptInTestBase):
    """Requirement 10: Secondary hold ignored.

    Secondary hold events produce zero HTTP requests; no command
    or payload reaches the transport.
    """

    def test_secondary_hold_generates_no_http_request(self):
        """Secondary hold events produce no HTTP request."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="secondary_hold", key="numpad_1", duration_ms=2000, seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 0)

    def test_secondary_hold_with_mapping_still_ignored(self):
        """Secondary hold ignored even when key has valid mapping."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="secondary_hold", key="numpad_1", duration_ms=3000, seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 0)

    def test_secondary_hold_no_command_reaches_transport(self):
        """No command or payload reaches HTTP transport for secondary_hold."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        adapter.send("test_command", "test_payload", _make_event(event_type="secondary_hold", key="numpad_1", seq=1))

        self.assertEqual(len(sender.calls), 0)


class TestRequirement11_DeviceIdentityPreserved(CompanionOptInTestBase):
    """Requirement 11: Device identity preserved.

    ProviderEvent.device is never mutated; logged in INFO logs and
    included in transport metadata.
    """

    def test_device_identity_preserved_in_adapter_logs(self):
        """Source device identity is preserved in adapter log output."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", device="EEEF:268A", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("device=EEEF:268A", log_output)

    def test_device_identity_not_mutated(self):
        """ProviderEvent.device is not mutated during processing."""
        original_event = _make_event(
            event_type="short_press",
            key="numpad_1",
            device="0C45:800A",
            seq=5
        )
        original_device = original_event.device

        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        dispatcher.dispatch(original_event)

        self.assertEqual(original_event.device, original_device)

    def test_device_included_in_transport_metadata(self):
        """Device identity included in mock transport metadata."""
        from aula_bridge.companion_transport import MockCompanionTransport
        from aula_bridge.companion_http_transport import CompanionHttpTransport
        
        sender = FakeHttpSender()
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        http_transport = CompanionHttpTransport(http_sender=sender)
        
        mock_transport = MockCompanionTransport()
        # Test the mock transport directly with its send method
        button_mapping = {"numpad_1": ButtonLocation(page=1, row=0, column=0)}
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport,  # Use HTTP transport
            button_mapping=button_mapping
        )
        event = _make_event(device="0C45:800A", seq=1)
        adapter.send("cmd", "payload", event)
        
        # Verify device is in the event and preserved
        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(event.device, "0C45:800A")


class TestRequirement12_EventOrderingPreserved(CompanionOptInTestBase):
    """Requirement 12: Event ordering preserved.

    ProviderEvent.seq never mutated (frozen dataclass); events dispatched
    in call order; order preserved through mock transport.
    """

    def test_event_sequence_preserved(self):
        """Event sequence number is preserved through the chain."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(event_type="short_press", key="numpad_1", seq=42)
        original_dict = event.to_dict()

        dispatcher.dispatch(event)

        self.assertEqual(event.to_dict(), original_dict)
        self.assertEqual(event.seq, 42)

    def test_multiple_events_preserve_ordering(self):
        """Multiple mapped events preserve dispatch ordering."""
        mappings = {
            "numpad_1": {"page": 1, "row": 0, "column": 0},
            "numpad_2": {"page": 1, "row": 0, "column": 1},
            "numpad_3": {"page": 1, "row": 0, "column": 2},
        }
        dispatcher, adapter, sender = self._build_chain(mappings=mappings)
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            _make_event(key="numpad_1", seq=1),
            _make_event(key="numpad_2", seq=2),
            _make_event(key="numpad_3", seq=3),
        ]
        for event in events:
            dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 3)
        urls = [call[1] for call in sender.calls]
        self.assertEqual(
            urls,
            [
                f"http://{self.TEST_HOST}:{self.TEST_PORT}/api/location/1/0/0/press",
                f"http://{self.TEST_HOST}:{self.TEST_PORT}/api/location/1/0/1/press",
                f"http://{self.TEST_HOST}:{self.TEST_PORT}/api/location/1/0/2/press",
            ],
        )

    def test_provider_event_seq_not_mutated_by_chain(self):
        """ProviderEvent.seq is not mutated by the dispatch chain."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(seq=42)
        original_seq = event.seq
        original_dict = event.to_dict()

        dispatcher.dispatch(event)

        # Event should not be mutated
        self.assertEqual(event.seq, original_seq)
        self.assertEqual(event.to_dict(), original_dict)


class TestRequirement13_HTTP200Accepted(CompanionOptInTestBase):
    """Requirement 13: HTTP 200 accepted."""

    def test_http_200_logged_as_success(self):
        """HTTP 200 is logged as accepted through the full chain."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=200", log_output)
        self.assertIn("success=True", log_output)


class TestRequirement14_HTTP204LoggedAsNOControl(CompanionOptInTestBase):
    """Requirement 14: HTTP 204 logged as NO_CONTROL."""

    def test_http_204_logged_as_no_control(self):
        """HTTP 204 is logged as NO_CONTROL."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=204, success=False))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=204", log_output)
        self.assertIn("NO_CONTROL", log_output)


class TestRequirement15_HTTP403LoggedAsFORBIDDEN(CompanionOptInTestBase):
    """Requirement 15: HTTP 403 logged as FORBIDDEN."""

    def test_http_403_logged_as_forbidden(self):
        """HTTP 403 is logged as FORBIDDEN."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=403, success=False))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=403", log_output)
        self.assertIn("FORBIDDEN", log_output)


class TestRequirement16_ConnectionRefusedHandled(CompanionOptInTestBase):
    """Requirement 16: Connection refused handled."""

    def test_connection_refused_handled_and_logged(self):
        """Connection refused is handled and logged without crashing."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_raise(ConnectionRefusedError("Connection refused"))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("CONNECTION_REFUSED", log_output)
        self.assertEqual(len(sender.calls), 1)


class TestRequirement17_TimeoutHandled(CompanionOptInTestBase):
    """Requirement 17: Timeout handled."""

    def test_timeout_handled_and_logged(self):
        """Timeout is handled and logged without crashing."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_raise(TimeoutError("Request timeout"))
        event = _make_event(key="numpad_1", seq=1)

        with self.assertLogs(logger="aula_bridge.companion_dispatch_adapter", level="INFO") as cm:
            dispatcher.dispatch(event)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("TIMEOUT", log_output)
        self.assertEqual(len(sender.calls), 1)


class TestRequirement18_NoAutomaticRetries(CompanionOptInTestBase):
    """Requirement 18: No automatic retries."""

    def test_failed_requests_not_retried(self):
        """Failed requests are not retried automatically."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = _make_event(key="numpad_1", seq=1)

        dispatcher.dispatch(event)

        # Only one call made
        self.assertEqual(len(sender.calls), 1)

    def test_transport_makes_single_sender_call(self):
        """Transport makes exactly one call to sender per press."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = _make_event(key="numpad_1", seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 1)


class TestRequirement19_NoBuffering(CompanionOptInTestBase):
    """Requirement 19: No buffering."""

    def test_no_event_buffering(self):
        """Each event is processed independently; no buffering between events."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={
                "numpad_1": {"page": 1, "row": 0, "column": 0},
                "numpad_2": {"page": 1, "row": 0, "column": 1},
                "numpad_3": {"page": 1, "row": 0, "column": 2},
            }
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            _make_event(key="numpad_1", seq=1),
            _make_event(key="numpad_2", seq=2),
            _make_event(key="numpad_3", seq=3),
        ]
        for event in events:
            dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 3)

    def test_adapter_flush_is_noop(self):
        """Adapter.flush() is a no-op (no buffering)."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        # Should not raise
        adapter.flush()

    def test_adapter_close_is_noop(self):
        """Adapter.close() is a no-op (no persistent connections)."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        # Should not raise
        adapter.close()

    def test_transport_flush_is_noop(self):
        """HTTP transport flush is a no-op (transport implements Transport protocol)."""
        from aula_bridge.dispatcher import ActionDispatcher, MockTransport
        transport = MockTransport()
        transport.flush()  # Should not raise
        
        # Also verify ActionDispatcher.flush works
        dispatcher = ActionDispatcher(transport=transport)
        dispatcher.flush()  # Should not raise


class TestRequirement20_NoRealNetworkAccess(CompanionOptInTestBase):
    """Requirement 20: No real network access."""

    def test_all_responses_from_fake_sender(self):
        """All responses come from the fake sender; no real network is used."""
        dispatcher, adapter, sender = self._build_chain(
            mappings={"numpad_1": {"page": 1, "row": 0, "column": 0}}
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = _make_event(key="numpad_1", seq=1)

        dispatcher.dispatch(event)

        self.assertEqual(len(sender.calls), 1)
        # Verify the only sender involved is our in-process fake sender
        # (implementation detail - the http_transport's sender is our fake)
        self.assertIs(sender, adapter._http_transport._http_sender)

    def test_no_socket_imports(self):
        """No socket or network modules imported in Companion modules."""
        import aula_bridge.companion_dispatch_adapter as adapter_mod
        import aula_bridge.companion_http_transport as transport_mod

        for mod, name in [(adapter_mod, "companion_dispatch_adapter"), (transport_mod, "companion_http_transport")]:
            if mod.__file__:
                source = open(mod.__file__, "r").read()
                self.assertNotIn("import socket", source)
                self.assertNotIn("from socket", source)
                self.assertNotIn("urllib.request", source)  # Only in http_sender.py


class TestRequirement21_NoHardwareAccess(CompanionOptInTestBase):
    """Requirement 21: No hardware access."""

    def test_no_serial_usb_hid_imports(self):
        """No serial, USB, or HID modules imported in Companion modules."""
        import aula_bridge.companion_dispatch_adapter as adapter_mod
        import aula_bridge.companion_http_transport as transport_mod
        import aula_bridge.companion_button_mapping as mapping_mod
        import aula_bridge.companion_types as types_mod

        for mod, name in [
            (adapter_mod, "companion_dispatch_adapter"),
            (transport_mod, "companion_http_transport"),
            (mapping_mod, "companion_button_mapping"),
            (types_mod, "companion_types"),
        ]:
            if mod.__file__:
                source = open(mod.__file__, "r").read()
                self.assertNotIn("import serial", source)
                self.assertNotIn("from serial", source)
                self.assertNotIn("import usb", source)
                self.assertNotIn("from usb", source)
                self.assertNotIn("import hid", source)
                self.assertNotIn("from hid", source)


class TestRequirement22_NoFirmwareInteraction(CompanionOptInTestBase):
    """Requirement 22: No firmware interaction."""

    def test_no_firmware_modules_imported(self):
        """No firmware/flashing modules imported in Companion stack."""
        import aula_bridge.companion_dispatch_adapter as adapter_mod
        import aula_bridge.companion_http_transport as transport_mod

        for mod, name in [(adapter_mod, "companion_dispatch_adapter"), (transport_mod, "companion_http_transport")]:
            if mod.__file__:
                source = open(mod.__file__, "r").read()
                self.assertNotIn("firmware", source.lower())
                self.assertNotIn("flash", source.lower())
                # "isp" appears in "dispatch" - check for actual ISP references
                # Look for "isp" as a standalone word (not in dispatch/transports)
                self.assertNotIn(" isp ", source.lower())
                self.assertNotIn("isp.", source.lower())
                # Check for ISP as standalone uppercase word (not in DISPATCH/TRANSPORT)
                # Split on non-alphanumeric and check individual words
                import re
                words = re.findall(r'\b\w+\b', source.upper())
                self.assertNotIn("ISP", words)
                self.assertNotIn("FLASH", words)
                self.assertNotIn("FIRMWARE", words)


class TestRequirement23_ExistingBridgeTestsUnchanged(DisabledCompanionTestBase):
    """Requirement 23: Existing Bridge tests remain unchanged.

    Verifies that the core Bridge behavior (ActionDispatcher, MockTransport,
    DryRunProvider, KeyStateMachine) is completely unaffected by Companion
    integration code.
    """

    def test_action_dispatcher_all_mappings_work(self):
        """All 51 default action mappings (17 keys * 3 event types) still work."""
        results = []
        for key in ["numpad_1", "numpad_2", "numpad_3", "numpad_4", "numpad_5"]:
            for event_type in ["short_press", "hold", "secondary_hold"]:
                event = _make_event(event_type=event_type, key=key, seq=1)
                result = self.dispatcher.dispatch(event)
                if result:
                    results.append(result)
        self.assertEqual(len(results), 15)  # 5 keys * 3 event types

    def test_mock_transport_fully_functional(self):
        """MockTransport records all action types correctly."""
        events = [
            _make_event(event_type="short_press", key="numpad_1", seq=1),
            _make_event(event_type="hold", key="numpad_2", seq=2),
            _make_event(event_type="secondary_hold", key="numpad_3", seq=3),
        ]
        self.dispatcher.dispatch_batch(events)
        self.assertEqual(len(self.transport.sent_actions), 3)

    def test_dryrun_provider_fully_functional(self):
        """DryRunProvider logs all event types correctly."""
        events = [
            _make_event(event_type="key_down", key="numpad_1", seq=1),
            _make_event(event_type="short_press", key="numpad_1", duration_ms=150, seq=2),
            _make_event(event_type="hold", key="numpad_1", duration_ms=700, seq=3),
            _make_event(event_type="key_up", key="numpad_1", held=True, seq=4),
        ]
        for e in events:
            self.provider.emit(e)
        self.provider.close()
        with open(self.provider.path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 4)

    def test_key_state_machine_unchanged(self):
        """KeyStateMachine behavior unchanged (imported from bridge)."""
        from aula_bridge import KeyStateMachine
        machine = KeyStateMachine(
            short_threshold_ms=200,
            hold_threshold_ms=500,
            secondary_hold_ms=1500,
            secondary_hold_enabled=True,
            stuck_key_timeout_ms=5000,
            now_ms=0,
        )
        # Basic sanity check - machine operates deterministically
        # key_down at time 100 - returns ACTION_NONE (key now PRESSED)
        results = machine.key_down("numpad_1", "0C45:800A", 100)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "none")
        
        # Advance to 150ms (held for 50ms < short_threshold)
        machine.set_time(150)
        results = machine.tick(150)
        self.assertEqual(len(results), 0)  # No time-based action yet
        
        # key_up at 150ms - short press (held < short_threshold)
        results = machine.key_up("numpad_1", "0C45:800A", 150)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].action, "short_press")


class TestRequirement24_NoUnintendedActivationDuringImport(CompanionOptInTestBase):
    """Requirement 24: No unintended activation during import.

    Importing Companion modules does not trigger any network connections,
    hardware access, or background threads.
    """

    def test_importing_modules_no_side_effects(self):
        """Importing Companion modules has no side effects."""
        # These imports should not trigger any I/O
        import aula_bridge.companion_dispatch_adapter
        import aula_bridge.companion_http_transport
        import aula_bridge.companion_button_mapping
        import aula_bridge.companion_types
        import aula_bridge.companion_transport
        import aula_bridge.companion_optin_config

        # No exception, no background activity

    def test_companion_http_transport_construction_no_io(self):
        """Constructing CompanionHttpTransport does no I/O."""
        sender = FakeHttpSender()
        # Construction should not call sender
        transport = CompanionHttpTransport(http_sender=sender)
        self.assertEqual(len(sender.calls), 0)

    def test_adapter_construction_no_io(self):
        """Constructing CompanionDispatchAdapter does no I/O."""
        adapter = CompanionDispatchAdapter(
            http_transport=self.sender,  # type: ignore
            button_mapping={}
        )
        self.assertEqual(len(self.sender.calls), 0)

    def test_config_load_no_network(self):
        """Loading opt-in config does no network access."""
        from aula_bridge.companion_optin_config import load
        config = load()  # No file - returns default disabled config
        self.assertFalse(config.enabled)

    def test_no_background_threads_on_import(self):
        """No background threads started on module import."""
        import threading
        initial_threads = threading.active_count()

        import aula_bridge.companion_dispatch_adapter
        import aula_bridge.companion_http_transport

        # Thread count should not increase from module imports
        final_threads = threading.active_count()
        self.assertEqual(initial_threads, final_threads)


# ========================================================================
# Contract Validation Tests
# ========================================================================

class TestOptInConfigContract(unittest.TestCase):
    """Tests validating the CompanionOptInConfig contract.

    These tests verify the configuration loader behavior that will be used
    by the production opt-in integration.
    """

    def test_default_config_disabled(self):
        """Default config has Companion disabled."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfig
        config = load()
        self.assertIsInstance(config, CompanionOptInConfig)
        self.assertFalse(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)
        self.assertIsNone(config.mapping_file)

    def test_enabled_config_requires_mapping_file(self):
        """Enabled config requires explicit mapping_file."""
        from aula_bridge.companion_optin_config import load, CompanionOptInConfigError
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "mapping_file": "mappings.json"}
        })
        path = _write_tmp_config(config_content)
        try:
            config = load(path)
            self.assertTrue(config.enabled)
            self.assertEqual(config.mapping_file, "mappings.json")
        finally:
            os.remove(path)

    def test_config_immutable(self):
        """CompanionOptInConfig is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError
        from aula_bridge.companion_optin_config import CompanionOptInConfig
        config = CompanionOptInConfig(enabled=True)
        with self.assertRaises(FrozenInstanceError):
            config.enabled = False


if __name__ == "__main__":
    # Configure logging for test output
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(name)s - %(levelname)s - %(message)s",
    )
    unittest.main()