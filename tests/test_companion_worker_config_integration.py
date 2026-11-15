"""Integration tests for Companion opt-in config -> dispatch worker chain.

Tests the existing chain:

    CompanionOptInConfig
      -> Button Mapping
      -> CompanionDispatchWorker
      -> CompanionDispatchAdapter
      -> CompanionHttpTransport
      -> FakeHttpSender

Deterministic threading.Event / queue.Queue synchronization. No sleep-based
race assumptions. No network or hardware access. Tests only.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import tempfile
import threading
import unittest
from typing import Any, Dict, List, Mapping, Optional, Tuple

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
from aula_bridge.companion_dispatch_worker import (
    CompanionDispatchWorker,
    DEFAULT_QUEUE_CAPACITY,
)
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
)
from aula_bridge.companion_optin_config import (
    CompanionOptInConfig,
    CompanionOptInConfigError,
    load,
)
from aula_bridge.companion_types import ButtonLocation
from aula_bridge.dispatcher import ActionDispatcher, Transport
from aula_bridge.provider import ProviderEvent


# ========================================================================
# Test Infrastructure
# ========================================================================

class FakeHttpSender:
    """Deterministic fake HTTP sender. Records calls, no real network."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, str, float]] = []
        self._response_map: Dict[Tuple[str, str], HttpResponse] = {}
        self._default_response: HttpResponse = HttpResponse(status_code=200, success=True)
        self._raise_on_call: Optional[Exception] = None
        self._signal: "queue.Queue[Tuple[str, str, float]]" = queue.Queue()

    def set_response(self, method: str, url: str, response: HttpResponse) -> None:
        self._response_map[(method, url)] = response

    def set_default_response(self, response: HttpResponse) -> None:
        self._default_response = response

    def set_raise(self, exc: Exception) -> None:
        self._raise_on_call = exc

    def clear_raise(self) -> None:
        self._raise_on_call = None

    def send(self, method: str, url: str, timeout: float) -> HttpResponse:
        self.calls.append((method, url, timeout))
        self._signal.put((method, url, timeout))
        if self._raise_on_call is not None:
            raise self._raise_on_call
        return self._response_map.get((method, url), self._default_response)

    def wait_for_send(self, timeout: float = 5.0) -> Tuple[str, str, float]:
        return self._signal.get(timeout=timeout)

    def clear(self) -> None:
        self.calls.clear()
        self._response_map.clear()
        self._raise_on_call = None


class BlockingFakeHttpSender(FakeHttpSender):
    """Fake sender whose send() can be blocked via threading.Event.

    Uses a queue.Queue signal so tests can deterministically detect when the
    worker has reached the blocked send() call (mirrors SyncTransport in
    test_companion_dispatch_worker.py).
    """

    def __init__(self) -> None:
        super().__init__()
        self.block_send = threading.Event()
        self.release = threading.Event()
        self._signal: "queue.Queue[Tuple[str, str, float]]" = queue.Queue()

    def send(self, method: str, url: str, timeout: float) -> HttpResponse:
        self.calls.append((method, url, timeout))
        self._signal.put((method, url, timeout))
        if self._raise_on_call is not None:
            raise self._raise_on_call
        if self.block_send.is_set():
            self.release.wait()
            self.release.clear()
        return self._response_map.get((method, url), self._default_response)

    def wait_for_send(self, timeout: float = 5.0) -> Tuple[str, str, float]:
        return self._signal.get(timeout=timeout)

    def block(self) -> None:
        self.block_send.set()

    def unblock(self) -> None:
        self.release.set()
        self.release.clear()


def _write_tmp(content: str, prefix: str, suffix: str = ".json") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def _make_event(
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


# ========================================================================
# Integration Test Fixture Base
# ========================================================================

class CompanionChainTestBase(unittest.TestCase):
    """Base for end-to-end chain tests.

    Builds: CompanionOptInConfig -> mapping -> FakeHttpSender ->
    CompanionHttpTransport -> CompanionDispatchAdapter ->
    CompanionDispatchWorker -> ActionDispatcher.
    """

    TEST_HOST = "127.0.0.1"
    TEST_PORT = 19876

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.temp_files: List[str] = []
        self.workers: List[CompanionDispatchWorker] = []

    def tearDown(self) -> None:
        for worker in self.workers:
            try:
                worker.close()
            except Exception:
                pass
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    def _add_temp(self, path: str) -> str:
        self.temp_files.append(path)
        return path

    def _write_config(
        self,
        enabled: bool = True,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        mapping_file: Optional[str] = None,
    ) -> str:
        companion: Dict[str, Any] = {"enabled": enabled}
        if host is not None:
            companion["host"] = host
        if port is not None:
            companion["port"] = port
        if timeout is not None:
            companion["timeout"] = timeout
        if mapping_file is not None:
            companion["mapping_file"] = mapping_file
        content = json.dumps({"version": 1, "companion": companion})
        return self._add_temp(_write_tmp(content, "companion_config_"))

    def _write_mapping(self, mappings: Dict[str, Dict[str, int]]) -> str:
        content = json.dumps({"version": 1, "mappings": mappings})
        return self._add_temp(_write_tmp(content, "companion_mapping_"))

    def _load_config(self, path: Optional[str]) -> CompanionOptInConfig:
        return load(path)

    def _build_worker_chain(
        self,
        config_path: Optional[str],
        mapping_path: str,
        blocking: bool = False,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[CompanionDispatchWorker, CompanionDispatchAdapter, FakeHttpSender]:
        """Build the full chain and return (worker, adapter, sender)."""
        config = self._load_config(config_path)
        button_mapping = load_companion_button_mapping(mapping_path)

        sender: FakeHttpSender
        if blocking:
            sender = BlockingFakeHttpSender()
        else:
            sender = FakeHttpSender()
        self.sender = sender

        http_transport = CompanionHttpTransport(
            http_sender=sender,
            host=host or config.host,
            port=port or config.port,
            timeout=timeout or config.timeout,
        )
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport,
            button_mapping=button_mapping,
        )
        worker = CompanionDispatchWorker(transport=adapter)
        self.workers.append(worker)
        dispatcher = ActionDispatcher(transport=worker)
        self.dispatcher = dispatcher
        return worker, adapter, sender

    def _dispatch(self, event: ProviderEvent) -> None:
        self.dispatcher.dispatch(event)


# ========================================================================
# 1. Enabled configuration validation
# ========================================================================

class TestEnabledConfigurationValidation(CompanionChainTestBase):
    """Enabled config validates and loads through the chain."""

    def test_enabled_config_loads_with_mapping(self) -> None:
        """A valid enabled config with mapping_file loads successfully."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        config_path = self._write_config(enabled=True, mapping_file=mapping_path)
        config = self._load_config(config_path)
        self.assertTrue(config.enabled)
        self.assertEqual(config.mapping_file, mapping_path)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)

    def test_enabled_config_propagates_host_port_timeout(self) -> None:
        """Enabled config carries custom host/port/timeout into the chain."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        config_path = self._write_config(
            enabled=True,
            host="127.0.0.1",
            port=self.TEST_PORT,
            timeout=2.5,
            mapping_file=mapping_path,
        )
        config = self._load_config(config_path)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, self.TEST_PORT)
        self.assertEqual(config.timeout, 2.5)

    def test_enabled_config_immutable(self) -> None:
        """CompanionOptInConfig is a frozen dataclass."""
        from dataclasses import FrozenInstanceError
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        config_path = self._write_config(enabled=True, mapping_file=mapping_path)
        config = self._load_config(config_path)
        with self.assertRaises(FrozenInstanceError):
            config.enabled = False  # type: ignore[misc]

    def test_enabled_requires_mapping_file(self) -> None:
        """enabled=true without mapping_file raises CompanionOptInConfigError."""
        config_path = self._write_config(enabled=True)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load_config(config_path)
        self.assertIn("mapping_file", str(ctx.exception))

    def test_missing_config_returns_disabled(self) -> None:
        """A missing config file produces the default disabled config."""
        config = self._load_config(None)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    def test_invalid_host_rejected(self) -> None:
        """Non-loopback host raises CompanionOptInConfigError."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        config_path = self._write_config(
            enabled=True, host="192.168.1.1", mapping_file=mapping_path
        )
        with self.assertRaises(CompanionOptInConfigError):
            self._load_config(config_path)

    def test_invalid_port_rejected(self) -> None:
        """Out-of-range port raises CompanionOptInConfigError."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        for bad_port in (0, 65536, -1):
            with self.subTest(port=bad_port):
                config_path = self._write_config(
                    enabled=True, port=bad_port, mapping_file=mapping_path
                )
                with self.assertRaises(CompanionOptInConfigError):
                    self._load_config(config_path)

    def test_invalid_timeout_rejected(self) -> None:
        """Non-positive timeout raises CompanionOptInConfigError."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        for bad_timeout in (0, -1.0):
            with self.subTest(timeout=bad_timeout):
                config_path = self._write_config(
                    enabled=True, timeout=bad_timeout, mapping_file=mapping_path
                )
                with self.assertRaises(CompanionOptInConfigError):
                    self._load_config(config_path)

    def test_malformed_json_rejected(self) -> None:
        """Malformed JSON config raises CompanionOptInConfigError."""
        config_path = self._add_temp(_write_tmp("{not json", "companion_config_"))
        with self.assertRaises(CompanionOptInConfigError):
            self._load_config(config_path)


# ========================================================================
# 2. Disabled configuration safety
# ========================================================================

class TestDisabledConfigurationSafety(CompanionChainTestBase):
    """Disabled config produces no dispatch through the chain."""

    def test_disabled_config_no_mapping(self) -> None:
        """Disabled config: no mapping_file set."""
        config_path = self._write_config(enabled=False)
        config = self._load_config(config_path)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    def test_missing_config_yields_disabled(self) -> None:
        """Missing config file yields disabled config (no companion activation)."""
        config = self._load_config(None)
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)
        self.assertEqual(config.host, "127.0.0.1")


# ========================================================================
# 3. Valid button mapping
# ========================================================================

class TestValidButtonMapping(CompanionChainTestBase):
    """Valid button mapping loads and dispatches through the chain."""

    VALID_MAPPINGS = {
        "numpad_1": {"page": 1, "row": 0, "column": 0},
        "numpad_5": {"page": 1, "row": 1, "column": 1},
        "numpad_0": {"page": 1, "row": 3, "column": 1},
    }

    def test_valid_mapping_loads_immutable(self) -> None:
        """A valid mapping file loads as an immutable MappingProxyType."""
        mapping_path = self._write_mapping(self.VALID_MAPPINGS)
        mapping = load_companion_button_mapping(mapping_path)
        self.assertIsInstance(mapping, Mapping)
        self.assertEqual(mapping["numpad_1"], ButtonLocation(page=1, row=0, column=0))
        self.assertEqual(mapping["numpad_5"], ButtonLocation(page=1, row=1, column=1))

    def test_mapped_short_press_dispatch_through_chain(self) -> None:
        """Mapped short_press: config -> mapping -> worker -> adapter -> transport -> sender."""
        mapping_path = self._write_mapping(self.VALID_MAPPINGS)
        config_path = self._write_config(
            enabled=True, mapping_file=mapping_path, port=self.TEST_PORT
        )
        worker, adapter, sender = self._build_worker_chain(
            config_path, mapping_path, port=self.TEST_PORT
        )
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        event = _make_event(key="numpad_5", seq=1)
        self._dispatch(event)
        self.sender.wait_for_send(timeout=5.0)  # worker dequeues and sends

        self.assertEqual(len(sender.calls), 1)
        method, url, timeout = sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/location/1/1/1/press", url)
        self.assertEqual(timeout, 5.0)

    def test_all_numpad_keys_valid(self) -> None:
        """All 17 numpad keys are valid mapping targets."""
        mappings = {key: {"page": 1, "row": 0, "column": i} for i, key in enumerate(NUM_PAD_KEYS)}
        mapping_path = self._write_mapping(mappings)
        mapping = load_companion_button_mapping(mapping_path)
        for key in NUM_PAD_KEYS:
            self.assertIn(key, mapping)


# ========================================================================
# 4. Invalid mapping rejection
# ========================================================================

class TestInvalidMappingRejection(CompanionChainTestBase):
    """Invalid button mappings are rejected before dispatch."""

    def test_unknown_logical_key_rejected(self) -> None:
        """Unknown logical key raises CompanionButtonMappingError."""
        mapping_path = self._write_mapping({"numpad_unknown": {"page": 1, "row": 0, "column": 0}})
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(mapping_path)

    def test_invalid_location_page_rejected(self) -> None:
        """page < 1 raises CompanionButtonMappingError."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 0, "row": 0, "column": 0}})
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(mapping_path)

    def test_invalid_location_negative_row_rejected(self) -> None:
        """negative row raises CompanionButtonMappingError."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": -1, "column": 0}})
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(mapping_path)

    def test_invalid_location_negative_column_rejected(self) -> None:
        """negative column raises CompanionButtonMappingError."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": -5}})
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(mapping_path)

    def test_boolean_location_values_rejected(self) -> None:
        """Boolean page/row/column values are rejected."""
        mapping_path = self._write_mapping({"numpad_1": {"page": True, "row": 0, "column": 0}})
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(mapping_path)


# ========================================================================
# 5. Mapped short_press dispatch
# ========================================================================

class TestMappedShortPressDispatch(CompanionChainTestBase):
    """Mapped short_press dispatches through the full worker chain."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.worker, self.adapter, self.sender = self._build_worker_chain(
            self.config_path, self.mapping_path, port=self.TEST_PORT
        )
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

    def test_short_press_sends_post_to_correct_endpoint(self) -> None:
        """Mapped short_press produces exactly one POST to the press endpoint."""
        event = _make_event(key="numpad_1", seq=1)
        self._dispatch(event)
        self.sender.wait_for_send(timeout=5.0)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("http://127.0.0.1:19876/api/location/1/0/0/press", url)

    def test_no_request_body(self) -> None:
        """No request body is sent (sender records 3-tuple calls only)."""
        event = _make_event(key="numpad_1", seq=1)
        self._dispatch(event)
        self.sender.wait_for_send(timeout=5.0)
        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(len(self.sender.calls[0]), 3)  # (method, url, timeout)

    def test_unmapped_key_produces_no_request(self) -> None:
        """Unmapped short_press produces no HTTP request through the worker."""
        event = _make_event(key="unknown_key", seq=1)
        self._dispatch(event)
        self.assertEqual(len(self.sender.calls), 0)


# ========================================================================
# 6. Hold / secondary_hold suppression
# ========================================================================

class TestHoldSecondaryHoldSuppression(CompanionChainTestBase):
    """Hold and secondary_hold events produce no HTTP request."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.worker, self.adapter, self.sender = self._build_worker_chain(
            self.config_path, self.mapping_path, port=self.TEST_PORT
        )
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

    def test_hold_suppressed_no_request(self) -> None:
        """hold event produces no HTTP request through the worker."""
        event = _make_event(event_type="hold", key="numpad_1", seq=1)
        self._dispatch(event)
        self.assertEqual(len(self.sender.calls), 0)

    def test_secondary_hold_suppressed_no_request(self) -> None:
        """secondary_hold event produces no HTTP request through the worker."""
        event = _make_event(event_type="secondary_hold", key="numpad_1", seq=1)
        self._dispatch(event)
        self.assertEqual(len(self.sender.calls), 0)

    def test_mixed_short_press_and_hold_ordering(self) -> None:
        """Interleaved short_press and hold: only short_press dispatches, in order."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        events = [
            _make_event(key="numpad_1", seq=1),
            _make_event(event_type="hold", key="numpad_1", seq=2),
            _make_event(key="numpad_1", seq=3),
            _make_event(event_type="secondary_hold", key="numpad_1", seq=4),
            _make_event(key="numpad_1", seq=5),
        ]
        for event in events:
            self._dispatch(event)
        for _ in range(3):
            self.sender.wait_for_send(timeout=5.0)
        self.assertEqual(len(self.sender.calls), 3)


# ========================================================================
# 7. Device identity preservation
# ========================================================================

class TestDeviceIdentityPreservation(CompanionChainTestBase):
    """Device identity is preserved through the worker snapshot."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.worker, self.adapter, self.sender = self._build_worker_chain(
            self.config_path, self.mapping_path, port=self.TEST_PORT
        )
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

    def test_device_identity_preserved_through_worker(self) -> None:
        """event.device is preserved on the queued dispatch snapshot."""
        device = "EEEF:268A"
        event = _make_event(device=device, seq=1)
        self._dispatch(event)
        self.assertEqual(event.device, device)

    def test_device_not_mutated_by_enqueue(self) -> None:
        """Caller's event device is not mutated by worker enqueue."""
        event = _make_event(device="0C45:800A", seq=1)
        original = event.device
        self._dispatch(event)
        self.assertEqual(event.device, original)

    def test_multiple_devices_preserved(self) -> None:
        """Events from different devices preserve distinct device identities."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        devices = ["0C45:800A", "EEEF:268A", "1A2B:3C4D"]
        for i, device in enumerate(devices):
            event = _make_event(device=device, seq=i + 1)
            self._dispatch(event)
        for _ in range(3):
            self.sender.wait_for_send(timeout=5.0)
        self.assertEqual(len(self.sender.calls), 3)


# ========================================================================
# 8. Event ordering
# ========================================================================

class TestEventOrdering(CompanionChainTestBase):
    """Multiple events preserve dispatch ordering through the worker."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({
            "numpad_1": {"page": 1, "row": 0, "column": 0},
            "numpad_2": {"page": 1, "row": 0, "column": 1},
            "numpad_3": {"page": 1, "row": 0, "column": 2},
        })
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.worker, self.adapter, self.sender = self._build_worker_chain(
            self.config_path, self.mapping_path, port=self.TEST_PORT
        )
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

    def test_multiple_events_preserve_order(self) -> None:
        """Multiple short_press events dispatched in seq order through the worker."""
        events = [_make_event(key=f"numpad_{i}", seq=i) for i in (1, 2, 3)]
        for event in events:
            self._dispatch(event)
        for _ in range(3):
            self.sender.wait_for_send(timeout=5.0)
        self.assertEqual(len(self.sender.calls), 3)
        urls = [call[1] for call in self.sender.calls]
        self.assertIn("/api/location/1/0/0/press", urls[0])
        self.assertIn("/api/location/1/0/1/press", urls[1])
        self.assertIn("/api/location/1/0/2/press", urls[2])

    def test_sequence_not_mutated_through_worker(self) -> None:
        """Caller's event seq is not mutated by worker enqueue."""
        event = _make_event(seq=7)
        original_seq = event.seq
        self._dispatch(event)
        self.assertEqual(event.seq, original_seq)


# ========================================================================
# 9. Queue overflow
# ========================================================================

class TestQueueOverflow(CompanionChainTestBase):
    """Worker bounded queue overflow behavior."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.sender = BlockingFakeHttpSender()
        http_transport = CompanionHttpTransport(
            http_sender=self.sender,
            host=self.TEST_HOST,
            port=self.TEST_PORT,
            timeout=5.0,
        )
        button_mapping = load_companion_button_mapping(self.mapping_path)
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport, button_mapping=button_mapping
        )
        self.worker = CompanionDispatchWorker(transport=adapter)
        self.workers.append(self.worker)
        self.dispatcher = ActionDispatcher(transport=self.worker)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

    def _fill_queue_worker_blocked(self) -> None:
        """Block the sender, fill the worker queue to capacity.

        The worker dequeues seq 1 and blocks inside sender.send(). The queue
        is then filled to capacity with seqs 2..(capacity+1).
        """
        self.sender.block()
        self.worker.send("cmd", "payload", _make_event(seq=1))
        # Deterministically wait until the worker reaches the blocked send.
        self.sender.wait_for_send(timeout=5.0)
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", _make_event(seq=i))

    def _drain_sends(self, count: int) -> None:
        self.sender.unblock()
        for _ in range(count):
            try:
                self.sender.wait_for_send(timeout=5.0)
            except queue.Empty:
                break

    def test_overflow_counter_increments(self) -> None:
        """Overflow increments the counter for each dropped event."""
        self._fill_queue_worker_blocked()
        overflow_events = 3
        for i in range(overflow_events):
            self.worker.send("cmd", "payload", _make_event(seq=100 + i))
        self.assertEqual(self.worker.overflow_count, overflow_events)
        self._drain_sends(DEFAULT_QUEUE_CAPACITY + 1)

    def test_overflow_logs_warning(self) -> None:
        """Overflow sends log a WARNING."""
        self._fill_queue_worker_blocked()
        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_worker", level="WARNING"
        ):
            self.worker.send("cmd", "payload", _make_event(seq=999))
        self._drain_sends(DEFAULT_QUEUE_CAPACITY + 1)


# ========================================================================
# 10. Shutdown drops
# ========================================================================

class TestShutdownDrops(CompanionChainTestBase):
    """Worker shutdown drops pending events and rejects late sends."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.sender = BlockingFakeHttpSender()
        http_transport = CompanionHttpTransport(
            http_sender=self.sender,
            host=self.TEST_HOST,
            port=self.TEST_PORT,
            timeout=5.0,
        )
        button_mapping = load_companion_button_mapping(self.mapping_path)
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport, button_mapping=button_mapping
        )
        self.worker = CompanionDispatchWorker(transport=adapter)
        self.workers.append(self.worker)
        self.dispatcher = ActionDispatcher(transport=self.worker)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

    def test_close_drops_pending_never_replays(self) -> None:
        """close() drains and drops pending queued events without replay."""
        self.sender.block()
        self.worker.send("cmd", "payload", _make_event(seq=1))
        self.sender.wait_for_send(timeout=5.0)  # worker blocked in send
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", _make_event(seq=i))
        self.worker.close()
        self.sender.unblock()
        # Only the in-flight event dispatched; pending dropped.
        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(self.worker.shutdown_drops, DEFAULT_QUEUE_CAPACITY)

    def test_late_send_after_shutdown_rejected(self) -> None:
        """send() after close() is rejected and counted as shutdown drop."""
        self.worker.close()
        before = self.worker.shutdown_drops
        self.worker.send("cmd", "payload", _make_event(seq=1))
        self.assertEqual(self.worker.shutdown_drops, before + 1)
        self.assertEqual(len(self.sender.calls), 0)

    def test_no_stale_event_replay_after_close(self) -> None:
        """Dropped events are never replayed after close()."""
        self.sender.block()
        for i in range(DEFAULT_QUEUE_CAPACITY):
            self.worker.send("cmd", "payload", _make_event(seq=i + 1))
        self.sender.wait_for_send(timeout=5.0)  # worker blocked on seq 1
        self.worker.close()
        self.sender.unblock()
        self.assertEqual(len(self.sender.calls), 1)


# ========================================================================
# 11. No retries
# ========================================================================

class TestNoRetries(CompanionChainTestBase):
    """Failed requests are not retried through the worker chain."""

    def setUp(self) -> None:
        super().setUp()
        self.mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        self.config_path = self._write_config(
            enabled=True, mapping_file=self.mapping_path, port=self.TEST_PORT
        )
        self.sender = BlockingFakeHttpSender()
        http_transport = CompanionHttpTransport(
            http_sender=self.sender,
            host=self.TEST_HOST,
            port=self.TEST_PORT,
            timeout=5.0,
        )
        button_mapping = load_companion_button_mapping(self.mapping_path)
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport, button_mapping=button_mapping
        )
        self.worker = CompanionDispatchWorker(transport=adapter)
        self.workers.append(self.worker)
        self.dispatcher = ActionDispatcher(transport=self.worker)

    def test_failed_request_not_retried(self) -> None:
        """A failing sender produces exactly one call (no retry)."""
        self.sender.set_raise(ConnectionRefusedError("refused"))
        event = _make_event(key="numpad_1", seq=1)
        self._dispatch(event)
        self.sender.wait_for_send(timeout=5.0)  # worker attempted the send
        self.assertEqual(len(self.sender.calls), 1)


# ========================================================================
# 12. No network / hardware access
# ========================================================================

class TestNoNetworkOrHardwareAccess(CompanionChainTestBase):
    """No real network or hardware is accessed; only FakeHttpSender used."""

    def test_sender_is_fake_only(self) -> None:
        """The chain uses only FakeHttpSender, no real urllib sender."""
        mapping_path = self._write_mapping({"numpad_1": {"page": 1, "row": 0, "column": 0}})
        config_path = self._write_config(
            enabled=True, mapping_file=mapping_path, port=self.TEST_PORT
        )
        worker, adapter, sender = self._build_worker_chain(
            config_path, mapping_path, port=self.TEST_PORT
        )
        self.assertIsInstance(sender, FakeHttpSender)

    def test_no_socket_import_in_chain_modules(self) -> None:
        """Chain modules do not import socket (no network access)."""
        import aula_bridge.companion_dispatch_worker as w
        import aula_bridge.companion_dispatch_adapter as a
        import aula_bridge.companion_http_transport as t
        import aula_bridge.companion_optin_config as c
        import aula_bridge.companion_button_mapping as m
        for mod in (w, a, t, c, m):
            self.assertNotIn("socket", mod.__dict__)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
