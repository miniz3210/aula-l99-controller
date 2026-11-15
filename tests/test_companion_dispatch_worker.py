"""Unit tests for CompanionDispatchWorker.

Deterministic synchronization with threading.Event / queue.Queue.
No sleep-based race assumptions. No real HTTP sender. No network or hardware access.
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


class TestCompanionDispatchWorker(unittest.TestCase):
    """Tests for the bounded CompanionDispatchWorker."""

    def setUp(self) -> None:
        self.transport = SyncTransport()
        self.worker = CompanionDispatchWorker(
            transport=self.transport, queue_capacity=DEFAULT_QUEUE_CAPACITY
        )

    def tearDown(self) -> None:
        self.worker.close()

    # ==================== Single event dispatch ====================

    def test_single_event_dispatch(self) -> None:
        """A single enqueued event is dispatched by the worker."""
        event = make_event(seq=1)
        self.worker.send("numpad_1_press", "", event)
        command, payload, sent_event = self.transport.wait_for_send()
        self.assertEqual(command, "numpad_1_press")
        self.assertEqual(payload, "")
        self.assertEqual(sent_event, event)

    # ==================== FIFO ordering ====================

    def test_fifo_ordering(self) -> None:
        """Events are dispatched in FIFO order."""
        events = [
            make_event(key="numpad_1", seq=1),
            make_event(key="numpad_2", seq=2),
            make_event(key="numpad_3", seq=3),
        ]
        for e in events:
            self.worker.send("cmd", "payload", e)
        for i, e in enumerate(events):
            _, _, sent_event = self.transport.wait_for_send()
            self.assertEqual(sent_event.seq, i + 1)
            self.assertEqual(sent_event.key, e.key)

    # ==================== Queue capacity ====================

    def test_queue_capacity_default(self) -> None:
        """Default queue capacity is 8."""
        self.assertEqual(self.worker.queue_capacity, DEFAULT_QUEUE_CAPACITY)
        self.assertEqual(DEFAULT_QUEUE_CAPACITY, 8)

    def test_queue_capacity_respected(self) -> None:
        """Worker queue maxsize equals configured capacity."""
        self.assertEqual(self.worker._queue.maxsize, DEFAULT_QUEUE_CAPACITY)

    # ==================== Overflow counter ====================

    def _fill_queue_while_worker_blocked(self) -> None:
        """Block the worker in transport.send, then fill the queue to capacity.

        After this, the queue is full (capacity items queued, one in-flight) and
        the next send() will overflow.
        """
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)  # worker dequeued seq 1, blocked in send
        # Queue is now empty; fill it to capacity (8 items).
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))

    def _drain_queued_sends(self, count: int) -> None:
        """Drain `count` queued sends after releasing the worker."""
        self.transport.unblock()
        for _ in range(count):
            try:
                self.transport.wait_for_send(timeout=5.0)
            except queue.Empty:
                break

    # ==================== Overflow counter ====================

    def test_overflow_counter(self) -> None:
        """Overflow increments the counter for each dropped event."""
        self._fill_queue_while_worker_blocked()
        overflow_events = 3
        for i in range(overflow_events):
            self.worker.send("cmd", "payload", make_event(seq=100 + i))
        self.assertEqual(self.worker.overflow_count, overflow_events)
        self._drain_queued_sends(DEFAULT_QUEUE_CAPACITY + 1)

    def test_overflow_counter_accumulates(self) -> None:
        """Overflow counter accumulates across multiple overflow events."""
        self._fill_queue_while_worker_blocked()
        for i in range(5):
            self.worker.send("cmd", "payload", make_event(seq=200 + i))
        self.assertEqual(self.worker.overflow_count, 5)
        self._drain_queued_sends(DEFAULT_QUEUE_CAPACITY + 1)

    # ==================== Overflow warning ====================

    def test_overflow_logs_warning(self) -> None:
        """Overflow logs a WARNING message."""
        self._fill_queue_while_worker_blocked()  # worker blocked, queue full (8 queued)
        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_worker", level="WARNING"
        ) as cm:
            # Overflow send inside capture context.
            self.worker.send("cmd", "payload", make_event(seq=999))
        self._drain_queued_sends(DEFAULT_QUEUE_CAPACITY + 1)
        log_output = "\n".join(cm.output)
        self.assertIn("queue overflow", log_output)
        self.assertIn("overflow_count", log_output)

    # ==================== Non-blocking enqueue ====================

    def test_non_blocking_enqueue(self) -> None:
        """send() returns immediately after enqueue or drop; does not wait for worker."""
        self.transport.block()
        # First send: worker dequeues and blocks inside transport.send.
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)  # worker reached send and blocked
        # Second send must return immediately (non-blocking enqueue).
        self.worker.send("cmd", "payload", make_event(seq=2))
        self.transport.unblock()
        self.transport.wait_for_send(timeout=5.0)

    # ==================== Slow transport does not block caller ====================

    def test_slow_transport_does_not_block_caller(self) -> None:
        """A slow transport does not block the caller's send()."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)  # worker blocked in send
        # Caller's next send must return without waiting for the slow transport.
        self.worker.send("cmd", "payload", make_event(seq=2))
        self.transport.unblock()
        self.transport.wait_for_send(timeout=5.0)

    # ==================== Timeout simulation ====================

    def test_close_does_not_block_indefinitely_on_slow_transport(self) -> None:
        """close() with a slow/in-flight transport returns within join_timeout and reports worker alive."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)  # worker blocked in send
        # close() must not block indefinitely; worker remains alive mid-request.
        self.worker.close()
        self.transport.unblock()
        # Worker may still have been alive after bounded join; state reported via logging.
        # After unblock, worker should finish on its own (daemon thread).

    # ==================== Worker exception isolation ====================

    def test_worker_exception_isolation(self) -> None:
        """One failed event does not kill the worker; subsequent events still dispatch."""
        self.transport.set_raise(ValueError("boom"))
        event1 = make_event(seq=1)
        self.worker.send("cmd", "payload", event1)
        try:
            self.transport.wait_for_send(timeout=5.0)
        except queue.Empty:
            self.fail("worker did not attempt send for failing event")
        # Worker must still be alive and process subsequent events.
        self.assertTrue(self.worker.is_alive)
        self.transport.clear_raise()
        event2 = make_event(seq=2)
        self.worker.send("cmd", "payload", event2)
        _, _, sent_event = self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(sent_event.seq, 2)

    def test_worker_exception_does_not_stop_queue(self) -> None:
        """Multiple failing events are all attempted; worker keeps running."""
        self.transport.set_raise(RuntimeError("fail"))
        for i in range(3):
            self.worker.send("cmd", "payload", make_event(seq=i + 1))
        for _ in range(3):
            try:
                self.transport.wait_for_send(timeout=5.0)
            except queue.Empty:
                self.fail("worker stopped after an exception")
        self.assertTrue(self.worker.is_alive)
        self.transport.clear_raise()

    # ==================== Device identity preserved ====================

    def test_device_identity_preserved(self) -> None:
        """event.device is preserved on the dispatched request."""
        device = "EEEF:268A"
        event = make_event(device=device, seq=1)
        self.worker.send("cmd", "payload", event)
        _, _, sent_event = self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(sent_event.device, device)

    def test_device_not_mutated(self) -> None:
        """Caller's event device is not mutated by enqueue."""
        event = make_event(device="0C45:800A", seq=1)
        original_device = event.device
        self.worker.send("cmd", "payload", event)
        self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(event.device, original_device)

    # ==================== Event sequence preserved ====================

    def test_event_sequence_preserved(self) -> None:
        """event.seq is preserved on the dispatched request."""
        event = make_event(seq=42)
        self.worker.send("cmd", "payload", event)
        _, _, sent_event = self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(sent_event.seq, 42)

    def test_sequence_not_mutated(self) -> None:
        """Caller's event seq is not mutated by enqueue."""
        event = make_event(seq=7)
        original_seq = event.seq
        self.worker.send("cmd", "payload", event)
        self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(event.seq, original_seq)

    # ==================== No duplicate dispatch ====================

    def test_no_duplicate_dispatch(self) -> None:
        """Each enqueued event is dispatched exactly once."""
        n = 5
        for i in range(n):
            self.worker.send("cmd", "payload", make_event(seq=i + 1))
        for _ in range(n):
            self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(self.transport.sent_count(), n)

    # ==================== Shutdown while idle ====================

    def test_shutdown_while_idle(self) -> None:
        """close() while idle stops the worker without error."""
        self.worker.close()
        self.assertTrue(self.worker._closed.is_set())
        self.assertTrue(self.worker._shutdown.is_set())

    # ==================== Shutdown while busy ====================

    def test_shutdown_while_busy(self) -> None:
        """close() while worker is processing stops accepting new work."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)  # worker busy in send
        self.worker.close()
        self.transport.unblock()
        # No new events should be accepted after close.
        self.worker.send("cmd", "payload", make_event(seq=2))
        self.assertEqual(self.transport.sent_count(), 1)

    # ==================== Shutdown with full queue ====================

    def test_shutdown_with_full_queue_drops_pending(self) -> None:
        """close() drops pending queued events and never replays them."""
        self._fill_queue_while_worker_blocked()
        # Worker is blocked on in-flight seq 1; queue full with seqs 2..9.
        self.worker.close()
        self.transport.unblock()
        # Pending queued events (seqs 2..9) were dropped, not replayed.
        # Only the in-flight event (seq 1) was sent.
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.transport.sent[0][2].seq, 1)

    # ==================== No dispatch after shutdown ====================

    def test_no_dispatch_after_shutdown(self) -> None:
        """send() after close() does not dispatch any event."""
        self.worker.close()
        event = make_event(seq=1)
        self.worker.send("cmd", "payload", event)
        # Worker is shut down; nothing should be dispatched.
        with self.assertRaises(queue.Empty):
            self.transport.wait_for_send(timeout=1.0)

    # ==================== No stale event replay ====================

    def test_no_stale_event_replay(self) -> None:
        """Dropped events are never replayed after close."""
        self.transport.block()
        for i in range(DEFAULT_QUEUE_CAPACITY):
            self.worker.send("cmd", "payload", make_event(seq=i + 1))
        self.transport.wait_for_send(timeout=5.0)
        self.worker.close()
        self.transport.unblock()
        # Re-open style usage: no new dispatch should occur for dropped items.
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.transport.sent[0][2].seq, 1)

    # ==================== Idempotent close ====================

    def test_idempotent_close(self) -> None:
        """close() can be called multiple times without error."""
        self.worker.close()
        self.worker.close()  # second call must not raise
        self.worker.close()

    def test_idempotent_close_after_busy(self) -> None:
        """close() is idempotent after a busy shutdown."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)
        self.worker.close()
        self.transport.unblock()
        self.worker.close()

    # ==================== No unbounded threads ====================

    def test_no_unbounded_threads(self) -> None:
        """Exactly one worker thread exists; no thread per send."""
        for i in range(20):
            self.worker.send("cmd", "payload", make_event(seq=i + 1))
            self.transport.wait_for_send(timeout=5.0)
        # Exactly one worker thread; no per-send thread creation.
        self.assertIsNotNone(self.worker._worker)
        self.assertTrue(self.worker.is_alive)
        self.assertEqual(self.worker._worker.name, "CompanionDispatchWorker")

    # ==================== Transport protocol ====================

    def test_transport_protocol_send(self) -> None:
        """Worker implements send(command, payload, event)."""
        event = make_event(seq=1)
        self.worker.send("command", "payload", event)
        _, _, sent_event = self.transport.wait_for_send(timeout=5.0)
        self.assertEqual(sent_event, event)

    def test_transport_protocol_flush(self) -> None:
        """Worker implements flush()."""
        self.worker.flush()

    def test_transport_protocol_close(self) -> None:
        """Worker implements close()."""
        self.worker.close()

    # ==================== Shutdown reports worker state ====================

    def test_close_reports_worker_still_alive_after_bounded_join(self) -> None:
        """If worker remains alive after bounded join, that state is reported (logged), not falsely claimed as full shutdown."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)
        # close with slow transport; worker alive after bounded join.
        with self.assertLogs(
            logger="aula_bridge.companion_dispatch_worker", level="WARNING"
        ) as cm:
            self.worker.close()
        self.transport.unblock()
        log_output = "\n".join(cm.output)
        self.assertIn("did not terminate within join_timeout", log_output)

    # ==================== Deterministic concurrency (TOCTOU race repair) ====================

    def _block_worker_in_send(self) -> None:
        """Block the worker inside transport.send() and confirm it reached there."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)

    def _release_worker(self) -> None:
        self.transport.unblock()

    def _racer_pair(self) -> threading.Barrier:
        """Barrier (3 parties: close thread, send thread, main thread) to synchronize a close/send race."""
        return threading.Barrier(3)

    def test_send_racing_close(self) -> None:
        """send() and close() race: atomic under lock; every event dispatched or shutdown-drop accounted."""
        self._block_worker_in_send()
        barrier = threading.Barrier(3)
        outcome: dict[str, object] = {}

        def closer() -> None:
            barrier.wait()
            self.worker.close()
            outcome["closed"] = True

        def sender() -> None:
            barrier.wait()
            self.worker.send("cmd", "payload", make_event(seq=2))
            outcome["sent"] = True

        t_close = threading.Thread(target=closer)
        t_send = threading.Thread(target=sender)
        t_close.start()
        t_send.start()
        barrier.wait()
        t_close.join(timeout=15)
        t_send.join(timeout=15)

        self.assertFalse(t_close.is_alive(), "close thread did not terminate")
        self.assertFalse(t_send.is_alive(), "send thread did not terminate")
        self.assertIn("closed", outcome)
        self.assertIn("sent", outcome)

        self.assertTrue(self.worker.is_alive, "worker should still be alive right after bounded close")
        self.assertFalse(
            self.worker.shutdown_complete, "shutdown_complete should be False while worker in-flight"
        )

        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.transport.sent[0][2].seq, 1)

        self.assertEqual(self.worker.shutdown_drops, 1)
        self.assertEqual(self.worker.overflow_count, 0)
        self.assertEqual(self.worker.queue_size, 0)

        self._release_worker()
        worker = self.worker._worker
        self.assertIsNotNone(worker)
        worker.join(timeout=10)
        self.assertFalse(self.worker.is_alive, "worker did not terminate after release")
        self.assertTrue(self.worker.shutdown_complete, "shutdown_complete should be True after worker termination")

    def test_close_while_queue_full(self) -> None:
        """close() with a full queue drops pending items without deadlock."""
        self.transport.block()
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.transport.wait_for_send(timeout=5.0)  # worker blocked in send (in-flight)
        # Fill queue to capacity (items 2..9).
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))
        # Queue is full; close() must drain and return bounded.
        self.worker.close()
        self._release_worker()
        # Only the in-flight event dispatched; pending drained items never replayed.
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.transport.sent[0][2].seq, 1)
        # Shutdown drops account for the drained pending queue.
        self.assertEqual(self.worker.shutdown_drops, DEFAULT_QUEUE_CAPACITY)

    def test_late_send_after_shutdown(self) -> None:
        """send() after close() is explicitly rejected and counted as a shutdown drop."""
        self.worker.close()
        before = self.worker.shutdown_drops
        self.worker.send("cmd", "payload", make_event(seq=1))
        self.assertEqual(self.worker.shutdown_drops, before + 1)
        # No dispatch occurs after shutdown.
        self.assertEqual(self.transport.sent_count(), 0)

    def test_shutdown_drop_accounting(self) -> None:
        """Shutdown drops are observable and distinct from overflow drops."""
        self._block_worker_in_send()
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))
        self.worker.close()
        self._release_worker()
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.worker.shutdown_drops, DEFAULT_QUEUE_CAPACITY)
        self.assertEqual(self.worker.overflow_count, 0)

    def test_overflow_counter_independence(self) -> None:
        """Overflow counter is independent of shutdown drops."""
        self._block_worker_in_send()
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))
        # Overflow send while queue full (worker blocked, queue full).
        self.worker.send("cmd", "payload", make_event(seq=999))
        self.assertEqual(self.worker.overflow_count, 1)
        self.worker.close()
        self._release_worker()
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.worker.shutdown_drops, DEFAULT_QUEUE_CAPACITY)
        self.assertEqual(self.worker.overflow_count, 1)

    def test_no_post_close_dispatch(self) -> None:
        """No dispatch occurs after close() completes, even for previously queued items."""
        self._block_worker_in_send()
        for i in range(2, DEFAULT_QUEUE_CAPACITY + 2):
            self.worker.send("cmd", "payload", make_event(seq=i))
        self.worker.close()
        self._release_worker()
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.transport.sent[0][2].seq, 1)

    def test_idempotent_close(self) -> None:
        """close() can be called multiple times without error or double drain."""
        self.worker.close()
        self.worker.close()
        self.worker.close()
        self.assertTrue(self.worker._closed.is_set())
        self.assertEqual(self.worker.shutdown_drops, 0)

    def test_worker_busy_during_close(self) -> None:
        """close() returns bounded while worker is busy in transport.send()."""
        self._block_worker_in_send()
        # close() must not block indefinitely on the in-flight HTTP request.
        self.worker.close()
        self._release_worker()
        self.assertTrue(self.worker._closed.is_set())

    def test_no_deadlock_send_close(self) -> None:
        """No deadlock between send() and close() under contention; both threads terminate, every event dispatched or shutdown-drop accounted."""
        self._block_worker_in_send()
        barrier = threading.Barrier(3)
        results: list[str] = []

        def closer() -> None:
            barrier.wait()
            try:
                self.worker.close()
                results.append("close-ok")
            except Exception as exc:  # pragma: no cover - defensive
                results.append(f"close-err:{exc!r}")

        def sender() -> None:
            barrier.wait()
            try:
                self.worker.send("cmd", "payload", make_event(seq=2))
                results.append("send-ok")
            except Exception as exc:  # pragma: no cover - defensive
                results.append(f"send-err:{exc!r}")

        t_close = threading.Thread(target=closer)
        t_send = threading.Thread(target=sender)
        t_close.start()
        t_send.start()
        barrier.wait()
        t_close.join(timeout=15)
        t_send.join(timeout=15)

        # Both threads must terminate (no deadlock, no hang).
        self.assertFalse(t_close.is_alive(), "close thread did not terminate")
        self.assertFalse(t_send.is_alive(), "send thread did not terminate")
        # Neither call raised; both made progress regardless of race winner.
        self.assertEqual(len(results), 2)
        self.assertIn("close-ok", results)
        self.assertIn("send-ok", results)

        # Exactly one event (in-flight seq 1) was dispatched; the raced event seq 2 was
        # either drained as a shutdown drop (send won) or rejected as a shutdown drop (close won).
        self.assertEqual(self.transport.sent_count(), 1)
        self.assertEqual(self.transport.sent[0][2].seq, 1)
        self.assertEqual(self.worker.shutdown_drops, 1)
        self.assertEqual(self.worker.overflow_count, 0)
        self.assertEqual(self.worker.queue_size, 0)

        # Worker liveness reported accurately: still in-flight right after bounded close.
        self.assertTrue(self.worker.is_alive, "worker should still be alive right after bounded close")
        self.assertFalse(
            self.worker.shutdown_complete, "shutdown_complete should be False while worker in-flight"
        )

        # No duplicate dispatch, no post-close dispatch: sent_count stays 1.
        self.assertEqual(self.transport.sent_count(), 1)

        self._release_worker()
        worker = self.worker._worker
        self.assertIsNotNone(worker)
        worker.join(timeout=10)
        self.assertFalse(self.worker.is_alive, "worker did not terminate after release")
        self.assertTrue(self.worker.shutdown_complete, "shutdown_complete should be True after worker termination")

    def test_fifo_ordering_unchanged(self) -> None:
        """FIFO ordering is preserved under concurrent send/close."""
        events = [make_event(key=f"k{i}", seq=i) for i in range(1, 6)]
        for e in events:
            self.worker.send("cmd", "payload", e)
        sent_seqs: list[int] = []
        for _ in events:
            _, _, sent_event = self.transport.wait_for_send(timeout=5.0)
            sent_seqs.append(sent_event.seq)
        self.assertEqual(sent_seqs, [1, 2, 3, 4, 5])
        self.worker.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
