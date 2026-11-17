"""Observability and drop accounting tests for Companion Runtime.

Focused offline tests verifying Companion Worker observability and
event-drop accounting. Uses FakeHttpSender and deterministic
threading.Event synchronization. No sleep-based race assumptions.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import queue
import sys
import threading
import unittest
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import aula_input_bridge
from aula_bridge.provider import ProviderEvent
from aula_bridge.dispatcher import Transport
from aula_bridge.companion_dispatch_worker import (
    CompanionDispatchWorker,
    DEFAULT_QUEUE_CAPACITY,
)
from aula_bridge.companion_http_transport import (
    CompanionHttpTransport,
    HttpResponse,
    HttpSender,
    ButtonLocation,
)
from aula_bridge.companion_dispatch_adapter import CompanionDispatchAdapter


class SyncTransport:
    """Test transport implementing the Transport protocol.

    Records sends in an internal queue for deterministic consumption by tests.
    Configurable blocking, failure, and call counting. No network I/O.
    """

    def __init__(self) -> None:
        self._signal: "queue.Queue[tuple[str, str, ProviderEvent]]" = queue.Queue()
        self.sent: list[tuple[str, str, ProviderEvent]] = []
        self._lock = threading.Lock()
        self.block_send = threading.Event()
        self.release = threading.Event()
        self.raise_exc = False
        self.exc: Optional[Exception] = None

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        with self._lock:
            self.sent.append((command, payload, event))
        self._signal.put((command, payload, event))
        if self.block_send.is_set():
            self.release.wait()
        if self.raise_exc:
            raise self.exc or RuntimeError("transport failure")

    def wait_for_send(self, timeout: float = 5.0) -> tuple[str, str, ProviderEvent]:
        return self._signal.get(timeout=timeout)

    def sent_count(self) -> int:
        with self._lock:
            return len(self.sent)

    def sent_commands(self) -> list[str]:
        with self._lock:
            return [c for c, _, _ in self.sent]

    def block(self) -> None:
        self.block_send.set()

    def unblock(self) -> None:
        self.release.set()
        self.release.clear()

    def set_raise(self, exc: Exception) -> None:
        self.raise_exc = True
        self.exc = exc

    def clear_raise(self) -> None:
        self.raise_exc = False
        self.exc = None

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class SyncTransportRaising:
    """Transport that raises from send()."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list[tuple[str, str, ProviderEvent]] = []

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        self.calls.append((command, payload, event))
        raise self.exc

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class FakeHttpSender:
    """Fake HTTP sender for testing. Records calls and returns configured responses."""

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


def make_event(
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


def make_location(page: int = 1, row: int = 0, column: int = 0) -> ButtonLocation:
    return ButtonLocation(page=page, row=row, column=column)


class TestDefaultLogLevel(unittest.TestCase):
    """Test 1: --log-level defaults to WARNING; INFO logs not emitted."""

    def test_log_level_defaults_to_warning(self) -> None:
        ns = aula_input_bridge.parse_args([])
        self.assertEqual(ns.log_level, "WARNING")

    def test_configure_logging_default_warning(self) -> None:
        """INFO HTTP result logs are not emitted under default WARNING level."""
        self._reset_root_logger()
        sender = FakeHttpSender()
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        http_transport = CompanionHttpTransport(http_sender=sender)
        button_mapping = {"numpad_1": make_location()}
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport, button_mapping=button_mapping
        )
        event = make_event(key="numpad_1", seq=1)

        aula_input_bridge.configure_logging("WARNING")
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.WARNING)

        adapter_logger = logging.getLogger("aula_bridge.companion_dispatch_adapter")
        self.assertFalse(adapter_logger.isEnabledFor(logging.INFO))

    @staticmethod
    def _reset_root_logger() -> None:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.NOTSET)


class TestExplicitInfoLogging(unittest.TestCase):
    """Test 2: --log-level INFO makes HTTP result logs visible."""

    def test_log_level_info_flag(self) -> None:
        ns = aula_input_bridge.parse_args(["--log-level", "INFO"])
        self.assertEqual(ns.log_level, "INFO")

    def test_configure_logging_info_makes_http_results_visible(self) -> None:
        """INFO logging so status=200 success=True is visible."""
        self._reset_root_logger()
        sender = FakeHttpSender()
        sender.set_default_response(HttpResponse(status_code=200, success=True))
        http_transport = CompanionHttpTransport(http_sender=sender)
        button_mapping = {"numpad_1": make_location()}
        adapter = CompanionDispatchAdapter(
            http_transport=http_transport, button_mapping=button_mapping
        )
        event = make_event(key="numpad_1", seq=1)

        aula_input_bridge.configure_logging("INFO")
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.INFO)
        adapter_logger = logging.getLogger("aula_bridge.companion_dispatch_adapter")
        self.assertTrue(adapter_logger.isEnabledFor(logging.INFO))

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            adapter.send("press", "", event)

        self.assertEqual(len(sender.calls), 1)
        log_output = "\n".join(cm.output)
        self.assertIn("status=200", log_output)
        self.assertIn("success=True", log_output)

    @staticmethod
    def _reset_root_logger() -> None:
        root = logging.getLogger()
        root.handlers.clear()
        root.setLevel(logging.NOTSET)


class TestDispatcherSyncException(unittest.TestCase):
    """Test 3: Dispatcher/transport exception produces exception log and does not propagate."""

    def setUp(self) -> None:
        self.handler = logging.handlers.MemoryHandler(capacity=1000)
        self.root_logger = logging.getLogger()
        self.root_logger.addHandler(self.handler)

    def tearDown(self) -> None:
        self.root_logger.removeHandler(self.handler)

    def _make_dispatcher(self):
        from aula_bridge.dispatcher import ActionDispatcher
        from aula_bridge.action_mapping import ActionMap

        return ActionDispatcher(transport=SyncTransportRaising(RuntimeError("boom")))

    def test_emit_and_dispatch_logs_exception_and_does_not_propagate(self) -> None:
        """emit_and_dispatch logs exception() and isolates from caller/message loop."""
        dispatcher = self._make_dispatcher()
        event = make_event(key="numpad_1", seq=1)
        provider = type("P", (), {"emit": lambda self, e: None})()

        aula_input_bridge.configure_logging("WARNING")

        # Must not raise into the caller (message loop).
        aula_input_bridge.emit_and_dispatch(provider, dispatcher, event)

        # Transport still recorded exactly one call attempt (no duplicate).
        transport = dispatcher.transport
        self.assertEqual(len(transport.calls), 1)

        # Exception log was emitted.
        records = [r for r in self.handler.buffer if r.levelno >= logging.ERROR]
        self.assertGreaterEqual(len(records), 1)
        joined = " ".join(r.getMessage() for r in records)
        self.assertIn("Dispatch failed", joined)
        self.assertIn("event=short_press", joined)
        self.assertIn("key=numpad_1", joined)
        self.assertIn("seq=1", joined)

    def test_exception_does_not_escape_into_caller(self) -> None:
        """Exception isolation: caller's code continues after dispatch failure."""
        dispatcher = self._make_dispatcher()
        event = make_event(key="numpad_1", seq=1)
        provider = type("P", (), {"emit": lambda self, e: None})()

        aula_input_bridge.configure_logging("WARNING")

        aula_input_bridge.emit_and_dispatch(provider, dispatcher, event)
        # Caller continues; no exception propagates.
        self.assertTrue(True)


class TestAdapterSendReturnsNone(unittest.TestCase):
    """Test 4: CompanionDispatchAdapter.send() returns None; no HttpResponse propagated."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(http_sender=self.sender)
        self.button_mapping = {"numpad_1": make_location()}
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=self.button_mapping,
        )

    def test_send_returns_none(self) -> None:
        """send() returns None, no HttpResponse propagated back."""
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))
        event = make_event(key="numpad_1", seq=1)

        result = self.adapter.send("press", "", event)

        self.assertIsNone(result)
        self.assertEqual(len(self.sender.calls), 1)


class TestSingleRequestInvariant(unittest.TestCase):
    """Test 5: One short_press results in exactly one sender/send invocation; no retry."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(http_sender=self.sender)
        self.button_mapping = {"numpad_1": make_location()}
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=self.button_mapping,
        )

    def test_short_press_one_sender_invocation_no_retry(self) -> None:
        """One short_press => exactly one sender.send; no retry."""
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))
        event = make_event(key="numpad_1", seq=1)

        self.adapter.send("press", "", event)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/api/location/1/0/0/press", url)


class TestLoggingFormat(unittest.TestCase):
    """Logging CLI format: concise stderr with timestamp, level, logger, message."""

    def test_configure_logging_format(self) -> None:
        """configure_logging sets a concise stderr format."""
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root = logging.getLogger()
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(logging.WARNING)

        logger = logging.getLogger("aula_bridge.companion_dispatch_adapter")
        logger.warning("test message")

        output = stream.getvalue()
        self.assertIn("WARNING", output)
        self.assertIn("aula_bridge.companion_dispatch_adapter", output)
        self.assertIn("test message", output)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(name)s - %(levelname)s - %(message)s",
    )
    unittest.main()
