"""Observability and drop accounting tests for Companion Runtime.

Focused offline tests verifying Companion Worker observability and
event-drop accounting. Uses FakeHttpSender and deterministic
threading.Event synchronization. No sleep-based race assumptions.
"""

from __future__ import annotations

import logging
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


class TestQueueOverflowObservability(unittest.TestCase):
    """Test 1: Queue overflow increments overflow_count and logs a WARNING."""

    def setUp(self) -> None:
        self.transport = SyncTransport()
        self.worker = CompanionDispatchWorker(
            transport=self.transport, queue_capacity=DEFAULT_QUEUE_CAPACITY
        )

    def tearDown(self) -> None:
        self.worker.close()

    def _fill_queue_while_worker_blocked(self) -> None:
        """Block the worker in transport.send, then fill the queue to capacity."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))

    def _drain_queued_sends(self, count: int) -> None:
        self.transport.unblock()
        for _ in range(count):
            try:
                self.transport.wait_for_send(timeout=5.0)
            except queue.Empty:
                break

    def test_overflow_increments_counter_and_logs_warning(self) -> None:
        """Queue overflow increments overflow_count and logs WARNING."""
        self._fill_queue_while_worker_blocked()

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_worker", level="WARNING"
        ) as cm:
            self.worker.send("cmd", "payload", make_event(seq=999))

        self.assertEqual(self.worker.overflow_count, 1)

        log_output = "\n".join(cm.output)
        self.assertIn("queue overflow", log_output)
        self.assertIn("overflow_count", log_output)
        self.assertIn("WARNING", log_output)

        self._drain_queued_sends(DEFAULT_QUEUE_CAPACITY + 1)

    def test_overflow_counter_accumulates_independently(self) -> None:
        """Overflow counter accumulates across multiple overflow events."""
        self._fill_queue_while_worker_blocked()

        for i in range(5):
            self.worker.send("cmd", "payload", make_event(seq=200 + i))

        self.assertEqual(self.worker.overflow_count, 5)

        self._drain_queued_sends(DEFAULT_QUEUE_CAPACITY + 1)


class TestShutdownDropAccounting(unittest.TestCase):
    """Test 2: Shutdown drops increment shutdown_drops independently of overflow_count."""

    def setUp(self) -> None:
        self.transport = SyncTransport()
        self.worker = CompanionDispatchWorker(
            transport=self.transport, queue_capacity=DEFAULT_QUEUE_CAPACITY
        )

    def tearDown(self) -> None:
        self.worker.close()

    def _block_worker_in_send(self) -> None:
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)

    def _release_worker(self) -> None:
        self.transport.unblock()

    def test_shutdown_drops_queued_events_independently_of_overflow(self) -> None:
        """Shutdown drops account for drained queue items, separate from overflow."""
        self._block_worker_in_send()
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))

        self.worker.close()
        self._release_worker()

        self.assertEqual(self.worker.shutdown_drops, DEFAULT_QUEUE_CAPACITY)
        self.assertEqual(self.worker.overflow_count, 0)

    def test_overflow_and_shutdown_drops_independent(self) -> None:
        """Overflow and shutdown drops are tracked independently."""
        self._block_worker_in_send()
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))
        self.worker.send("cmd", "payload", make_event(seq=999))
        self.assertEqual(self.worker.overflow_count, 1)

        self.worker.close()
        self._release_worker()

        self.assertEqual(self.worker.shutdown_drops, DEFAULT_QUEUE_CAPACITY)
        self.assertEqual(self.worker.overflow_count, 1)

    def test_late_send_after_close_increments_shutdown_drops(self) -> None:
        """Late send after close increments shutdown_drops and logs WARNING."""
        self.worker.close()

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_worker", level="WARNING"
        ) as cm:
            self.worker.send("cmd", "payload", make_event(seq=1))

        self.assertEqual(self.worker.shutdown_drops, 1)

        log_output = "\n".join(cm.output)
        self.assertIn("late send rejected after shutdown", log_output)
        self.assertIn("shutdown_drops", log_output)
        self.assertIn("WARNING", log_output)

        self.assertEqual(self.transport.sent_count(), 0)


class TestLateSendRejection(unittest.TestCase):
    """Test 3: Late send after close is rejected, counted and logged."""

    def setUp(self) -> None:
        self.transport = SyncTransport()
        self.worker = CompanionDispatchWorker(
            transport=self.transport, queue_capacity=DEFAULT_QUEUE_CAPACITY
        )

    def tearDown(self) -> None:
        self.worker.close()

    def test_late_send_rejected_counted_and_logged(self) -> None:
        """send() after close() is rejected, increments shutdown_drops, logs WARNING."""
        self.worker.close()

        before_drops = self.worker.shutdown_drops

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_worker", level="WARNING"
        ) as cm:
            self.worker.send("cmd", "payload", make_event(seq=42, device="AAAA:BBBB"))

        self.assertEqual(self.worker.shutdown_drops, before_drops + 1)

        log_output = "\n".join(cm.output)
        self.assertIn("late send rejected after shutdown", log_output)
        self.assertIn("command=cmd", log_output)
        self.assertIn("device=AAAA:BBBB", log_output)
        self.assertIn("seq=42", log_output)
        self.assertIn("shutdown_drops=1", log_output)
        self.assertIn("WARNING", log_output)

        self.assertEqual(self.transport.sent_count(), 0)

    def test_multiple_late_sends_each_counted(self) -> None:
        """Multiple late sends each increment shutdown_drops."""
        self.worker.close()

        for i in range(3):
            self.worker.send("cmd", "payload", make_event(seq=100 + i))

        self.assertEqual(self.worker.shutdown_drops, 3)
        self.assertEqual(self.transport.sent_count(), 0)


class TestHttp204Observability(unittest.TestCase):
    """Test 4: HTTP 204 produces NO_CONTROL logging without claiming success."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(http_sender=self.sender)

        self.button_mapping = {
            "numpad_1": make_location(page=1, row=0, column=0),
        }
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=self.button_mapping,
        )

    def test_http_204_logs_no_control_without_success(self) -> None:
        """HTTP 204 returns NO_CONTROL error, logs without claiming success."""
        self.sender.set_default_response(HttpResponse(status_code=204, success=False))
        event = make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.adapter.send("press", "", event)

        self.assertEqual(len(self.sender.calls), 1)

        log_output = "\n".join(cm.output)
        self.assertIn("status=204", log_output)
        self.assertIn("success=False", log_output)
        self.assertIn("error_code=NO_CONTROL", log_output)
        self.assertNotIn("success=True", log_output)

    def test_transport_returns_no_control_for_204(self) -> None:
        """CompanionHttpTransport returns NO_CONTROL for 204."""
        self.sender.set_default_response(HttpResponse(status_code=204, success=False))
        location = make_location()

        response = self.http_transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.error_code, "NO_CONTROL")
        self.assertEqual(response.error_message, "No control at location")


class TestHttp403Observability(unittest.TestCase):
    """Test 5: HTTP 403 produces FORBIDDEN logging without claiming success."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(http_sender=self.sender)

        self.button_mapping = {
            "numpad_1": make_location(page=1, row=0, column=0),
        }
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=self.button_mapping,
        )

    def test_http_403_logs_forbidden_without_success(self) -> None:
        """HTTP 403 returns FORBIDDEN error, logs without claiming success."""
        self.sender.set_default_response(HttpResponse(status_code=403, success=False))
        event = make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.adapter.send("press", "", event)

        self.assertEqual(len(self.sender.calls), 1)

        log_output = "\n".join(cm.output)
        self.assertIn("status=403", log_output)
        self.assertIn("success=False", log_output)
        self.assertIn("error_code=FORBIDDEN", log_output)
        self.assertNotIn("success=True", log_output)

    def test_transport_returns_forbidden_for_403(self) -> None:
        """CompanionHttpTransport returns FORBIDDEN for 403."""
        self.sender.set_default_response(HttpResponse(status_code=403, success=False))
        location = make_location()

        response = self.http_transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.error_code, "FORBIDDEN")
        self.assertEqual(response.error_message, "HTTP API disabled or access forbidden")


class TestHttpTimeoutObservability(unittest.TestCase):
    """Test 6: HTTP timeout produces TIMEOUT logging without automatic retry."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.http_transport = CompanionHttpTransport(http_sender=self.sender)

        self.button_mapping = {
            "numpad_1": make_location(page=1, row=0, column=0),
        }
        self.adapter = CompanionDispatchAdapter(
            http_transport=self.http_transport,
            button_mapping=self.button_mapping,
        )

    def test_http_timeout_logs_timeout_without_retry(self) -> None:
        """HTTP timeout returns TIMEOUT error, logs without retry."""
        self.sender.set_raise(TimeoutError("Request timeout"))
        event = make_event(key="numpad_1", seq=1)

        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_adapter", level="INFO"
        ) as cm:
            self.adapter.send("press", "", event)

        self.assertEqual(len(self.sender.calls), 1)

        log_output = "\n".join(cm.output)
        self.assertIn("status=0", log_output)
        self.assertIn("success=False", log_output)
        self.assertIn("error_code=TIMEOUT", log_output)
        self.assertNotIn("success=True", log_output)

    def test_transport_returns_timeout_without_retry(self) -> None:
        """CompanionHttpTransport returns TIMEOUT for timeout, no retry."""
        self.sender.set_raise(TimeoutError("Request timeout"))
        location = make_location()

        response = self.http_transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "TIMEOUT")
        self.assertEqual(response.error_message, "Request timeout")

        self.assertEqual(len(self.sender.calls), 1)

    def test_no_automatic_retry_on_timeout(self) -> None:
        """Timeout does not trigger automatic retry."""
        self.sender.set_raise(TimeoutError("Request timeout"))
        location = make_location()

        self.http_transport.press(location)
        self.http_transport.press(location)

        self.assertEqual(len(self.sender.calls), 2)

    def test_no_automatic_retry_on_any_failure(self) -> None:
        """No automatic retries on any failure status."""
        for status in [400, 403, 500, 503]:
            with self.subTest(status=status):
                self.sender.clear()
                self.sender.set_default_response(
                    HttpResponse(status_code=status, success=False)
                )
                location = make_location()

                self.http_transport.press(location)

                self.assertEqual(len(self.sender.calls), 1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(name)s - %(levelname)s - %(message)s",
    )
    unittest.main()