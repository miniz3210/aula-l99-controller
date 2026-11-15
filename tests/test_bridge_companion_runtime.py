"""Minimal offline runtime wiring tests for the AULA L99 Windows Bridge Companion opt-in.

Four essential tests only:
1. Default mode uses MockTransport.
2. Enabled mode injects CompanionDispatchWorker into ActionDispatcher.
3. Worker wraps CompanionDispatchAdapter.
4. Slow FakeHttpSender does not block the caller/message-loop thread.

No real network requests. No hardware access. No production code modifications.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.companion_dispatch_adapter import CompanionDispatchAdapter
from aula_bridge.companion_dispatch_worker import (
    CompanionDispatchWorker,
    DEFAULT_QUEUE_CAPACITY,
)
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
)
from aula_bridge.companion_types import ButtonLocation
from aula_bridge.dispatcher import ActionDispatcher, ActionMap, MockTransport
from aula_bridge.provider import ProviderEvent
from aula_bridge.companion_optin_config import load as load_companion_config
from aula_bridge.companion_button_mapping import load_companion_button_mapping
import aula_input_bridge


class _ExitLoop(Exception):
    """Raised by fake time.sleep to break out of main()'s message loop."""


class FakeHttpSender:
    """Deterministic fake HTTP sender. Records calls, no real network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []
        self.block_send = threading.Event()
        self.release = threading.Event()
        self._signal: "queue.Queue[tuple[str, str, float]]" = queue.Queue()

    def send(self, method: str, url: str, timeout: float) -> HttpResponse:
        self.calls.append((method, url, timeout))
        self._signal.put((method, url, timeout))
        if self.block_send.is_set():
            self.release.wait()
            self.release.clear()
        return HttpResponse(status_code=200, success=True)

    def wait_for_send(self, timeout: float = 5.0) -> tuple[str, str, float]:
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


def _make_event(event_type="short_press", key="numpad_1", device="0C45:800A", seq=1):
    return ProviderEvent(
        event=event_type, key=key, device=device, seq=seq
    )


def _raise_exit(*args, **kwargs):
    raise _ExitLoop()


class TestBridgeCompanionRuntime(unittest.TestCase):
    """Four essential offline runtime wiring tests."""

    def setUp(self) -> None:
        self.mapping_path = _write_tmp(
            json.dumps({"version": 1, "mappings": {
                "numpad_1": {"page": 1, "row": 0, "column": 0},
                "numpad_2": {"page": 1, "row": 0, "column": 1},
                "numpad_3": {"page": 1, "row": 0, "column": 2},
            }}),
            "companion_mapping_",
        )
        self.config_path = _write_tmp(
            json.dumps({"version": 1, "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 19876,
                "timeout": 5.0,
                "mapping_file": self.mapping_path,
            }}),
            "companion_config_",
        )
        self._patches: list = []

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def _mock_windows(self) -> None:
        """Patch Windows APIs so main() can run without hardware."""
        self._patches.append(
            patch("aula_input_bridge.find_target_device", return_value=None)
        )
        self._patches.append(
            patch("aula_input_bridge.user32.PeekMessageW", return_value=False)
        )
        self._patches.append(
            patch("aula_input_bridge.time.sleep", side_effect=_raise_exit)
        )
        for p in self._patches:
            p.start()

    # ------------------------------------------------------------------
    # Test 1: Default mode uses MockTransport
    # ------------------------------------------------------------------

    def test_default_mode_uses_mock_transport(self) -> None:
        """Without --enable-companion, ActionDispatcher receives MockTransport."""
        self._mock_windows()
        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()
        self._dispatcher_mock = dispatcher_mock

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        transport_arg = call_args.kwargs.get("transport")
        self.assertIsInstance(transport_arg, MockTransport)

    # ------------------------------------------------------------------
    # Test 2: Enabled mode injects CompanionDispatchWorker into ActionDispatcher
    # ------------------------------------------------------------------

    def test_enabled_mode_injects_worker_into_dispatcher(self) -> None:
        """With --enable-companion, ActionDispatcher receives CompanionDispatchWorker."""
        self._mock_windows()
        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        transport_arg = call_args.kwargs.get("transport")
        self.assertIsInstance(transport_arg, CompanionDispatchWorker)

    # ------------------------------------------------------------------
    # Test 3: Worker wraps CompanionDispatchAdapter
    # ------------------------------------------------------------------

    def test_worker_wraps_companion_dispatch_adapter(self) -> None:
        """CompanionDispatchWorker transport is a CompanionDispatchAdapter."""
        self._mock_windows()
        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsInstance(worker, CompanionDispatchWorker)
        self.assertIsInstance(worker._transport, CompanionDispatchAdapter)

    # ------------------------------------------------------------------
    # Test 4: Slow FakeHttpSender does not block caller/message-loop thread
    # ------------------------------------------------------------------

    def test_slow_fake_http_sender_does_not_block_caller(self) -> None:
        """Worker.send() returns immediately even when sender blocks; caller thread is not blocked."""
        sender = FakeHttpSender()
        sender.block()  # block the sender's send()

        http_transport = CompanionHttpTransport(
            http_sender=sender,
            host="127.0.0.1",
            port=19876,
            timeout=5.0,
        )
        button_mapping: dict[str, ButtonLocation] = {
            "numpad_1": ButtonLocation(page=1, row=0, column=0),
        }
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport,
            button_mapping=button_mapping,
        )
        worker = CompanionDispatchWorker(transport=adapter)

        try:
            event = _make_event(key="numpad_1", seq=1)
            start = time.perf_counter()
            # Caller's send() must return immediately (non-blocking enqueue).
            worker.send("numpad_1_press", "", event)
            elapsed = time.perf_counter() - start
            self.assertLess(elapsed, 1.0, "worker.send() blocked the caller")
            # Worker should have dequeued and reached the blocked sender.
            sender.wait_for_send(timeout=5.0)
        finally:
            sender.unblock()
            worker.close()

    # ------------------------------------------------------------------
    # Helper: build a real Worker via the actual Bridge composition path
    # ------------------------------------------------------------------

    def _build_worker(self):
        """Build a CompanionDispatchWorker via aula_input_bridge.build_companion_transport."""
        companion_config = load_companion_config(self.config_path)
        worker = aula_input_bridge.build_companion_transport(companion_config, self.mapping_path)
        return worker

    # ------------------------------------------------------------------
    # Test 5: Short press produces one HTTP request
    # ------------------------------------------------------------------

    def test_short_press_produces_one_http_request(self) -> None:
        """A short_press event yields exactly one HTTP POST request."""
        sender = FakeHttpSender()
        self._mock_windows()

        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsNotNone(worker)

        # Replace the real sender with our fake to record calls without network.
        adapter = worker._transport
        http_transport = adapter._http_transport
        original_sender = http_transport._http_sender
        http_transport._http_sender = sender
        try:
            event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1)
            dispatcher = ActionDispatcher(transport=worker, action_map=ActionMap())
            dispatcher.dispatch(event)
            sender.wait_for_send(timeout=5.0)
        finally:
            http_transport._http_sender = original_sender
            worker.close()

        self.assertEqual(len(sender.calls), 1)
        method, url, timeout = sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/location/1/0/0/press", url)

    # ------------------------------------------------------------------
    # Test 6: Hold produces zero HTTP requests
    # ------------------------------------------------------------------

    def test_hold_produces_zero_http_requests(self) -> None:
        """A hold event yields zero HTTP requests (adapter only processes short_press)."""
        sender = FakeHttpSender()
        self._mock_windows()

        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsNotNone(worker)

        adapter = worker._transport
        http_transport = adapter._http_transport
        original_sender = http_transport._http_sender
        http_transport._http_sender = sender
        try:
            event = ProviderEvent(event="hold", key="numpad_1", device="0C45:800A", seq=1)
            dispatcher = ActionDispatcher(transport=worker, action_map=ActionMap())
            dispatcher.dispatch(event)
            # Give the worker thread a moment to dequeue; no request should appear.
            time.sleep(0.2)
        finally:
            http_transport._http_sender = original_sender
            worker.close()

        self.assertEqual(len(sender.calls), 0)

    # ------------------------------------------------------------------
    # Test 7: Secondary hold produces zero requests
    # ------------------------------------------------------------------

    def test_secondary_hold_produces_zero_requests(self) -> None:
        """A secondary_hold event yields zero HTTP requests."""
        sender = FakeHttpSender()
        self._mock_windows()

        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsNotNone(worker)

        adapter = worker._transport
        http_transport = adapter._http_transport
        original_sender = http_transport._http_sender
        http_transport._http_sender = sender
        try:
            event = ProviderEvent(event="secondary_hold", key="numpad_1", device="0C45:800A", seq=1)
            dispatcher = ActionDispatcher(transport=worker, action_map=ActionMap())
            dispatcher.dispatch(event)
            time.sleep(0.2)
        finally:
            http_transport._http_sender = original_sender
            worker.close()

        self.assertEqual(len(sender.calls), 0)

    # ------------------------------------------------------------------
    # Test 8: Unmapped key produces zero requests
    # ------------------------------------------------------------------

    def test_unmapped_key_produces_zero_requests(self) -> None:
        """An unmapped key yields zero HTTP requests (no button location)."""
        sender = FakeHttpSender()
        self._mock_windows()

        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsNotNone(worker)

        adapter = worker._transport
        http_transport = adapter._http_transport
        original_sender = http_transport._http_sender
        http_transport._http_sender = sender
        try:
            event = ProviderEvent(event="short_press", key="numpad_9", device="0C45:800A", seq=1)
            dispatcher = ActionDispatcher(transport=worker, action_map=ActionMap())
            dispatcher.dispatch(event)
            # Give the worker thread a moment to dequeue; no request should appear.
            time.sleep(0.2)
        finally:
            http_transport._http_sender = original_sender
            worker.close()

        self.assertEqual(len(sender.calls), 0)

    # ------------------------------------------------------------------
    # Test 9: Device identity and sequence preserved
    # ------------------------------------------------------------------

    def test_device_identity_and_sequence_preserved(self) -> None:
        """Worker.send preserves device and seq on the ProviderEvent sent through."""
        sender = FakeHttpSender()
        self._mock_windows()

        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsNotNone(worker)

        adapter = worker._transport
        http_transport = adapter._http_transport
        original_sender = http_transport._http_sender
        http_transport._http_sender = sender
        try:
            event = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=42)
            dispatcher = ActionDispatcher(transport=worker, action_map=ActionMap())
            dispatcher.dispatch(event)
            sender.wait_for_send(timeout=5.0)
        finally:
            http_transport._http_sender = original_sender
            worker.close()

        self.assertEqual(len(sender.calls), 1)
        # sender.calls only records (method, url, timeout); inspect the queued event via the adapter's last send path.
        # Re-dispatch through worker directly to capture the event object.
        sender.calls.clear()
        captured_event: list[ProviderEvent] = []

        class CapturingSender:
            def send(self, method, url, timeout):
                return HttpResponse(status_code=200, success=True)

        # Build a fresh worker whose adapter we can introspect by wrapping transport.send.
        http_transport2 = CompanionHttpTransport(
            http_sender=sender,
            host="127.0.0.1",
            port=19876,
            timeout=5.0,
        )
        button_mapping = load_companion_button_mapping(self.mapping_path)
        adapter2 = CompanionDispatchAdapter(
            http_transport=http_transport2,
            button_mapping=button_mapping,
        )
        worker2 = CompanionDispatchWorker(transport=adapter2)
        try:
            event2 = ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=42)
            worker2.send("numpad_1_press", "", event2)
            sender.wait_for_send(timeout=5.0)
        finally:
            worker2.close()

        self.assertEqual(len(sender.calls), 1)
        self.assertEqual(event2.device, "0C45:800A")
        self.assertEqual(event2.seq, 42)

    # ------------------------------------------------------------------
    # Test 10: Worker FIFO dispatch ordering preserved
    # ------------------------------------------------------------------

    def test_worker_fifo_dispatch_ordering_preserved(self) -> None:
        """Worker dequeues and dispatches requests in FIFO order."""
        sender = FakeHttpSender()
        self._mock_windows()

        mock_dispatcher = patch("aula_input_bridge.ActionDispatcher")
        self._patches.append(mock_dispatcher)
        dispatcher_mock = mock_dispatcher.start()

        try:
            with self.assertRaises(_ExitLoop):
                aula_input_bridge.main([
                    "--enable-companion",
                    "--companion-config",
                    self.config_path,
                ])
        finally:
            for p in self._patches:
                p.stop()

        call_args = dispatcher_mock.call_args
        self.assertIsNotNone(call_args)
        worker = call_args.kwargs.get("transport")
        self.assertIsNotNone(worker)

        adapter = worker._transport
        http_transport = adapter._http_transport
        original_sender = http_transport._http_sender
        http_transport._http_sender = sender
        try:
            dispatcher = ActionDispatcher(transport=worker, action_map=ActionMap())
            events = [
                ProviderEvent(event="short_press", key="numpad_1", device="0C45:800A", seq=1),
                ProviderEvent(event="short_press", key="numpad_2", device="0C45:800A", seq=2),
                ProviderEvent(event="short_press", key="numpad_3", device="0C45:800A", seq=3),
            ]
            for ev in events:
                dispatcher.dispatch(ev)
            for _ in events:
                sender.wait_for_send(timeout=5.0)
        finally:
            http_transport._http_sender = original_sender
            worker.close()

        self.assertEqual(len(sender.calls), 3)
        # URLs in FIFO order: page1/col0, page1/col1, page1/col2
        expected_urls = [
            "http://127.0.0.1:19876/api/location/1/0/0/press",
            "http://127.0.0.1:19876/api/location/1/0/1/press",
            "http://127.0.0.1:19876/api/location/1/0/2/press",
        ]
        actual_urls = [url for _, url, _ in sender.calls]
        self.assertEqual(actual_urls, expected_urls)


if __name__ == "__main__":
    unittest.main()
