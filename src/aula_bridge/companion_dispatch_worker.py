"""Bounded asynchronous Companion dispatch worker.

Standalone non-blocking dispatch wrapper around the existing Transport
interface. Runs exactly one worker thread with a bounded FIFO queue.

No Windows Bridge integration. No Dispatcher modifications. No State Machine
modifications. No Raw Input attribution changes. No Companion HTTP Core
modifications. No HTTP Sender modifications. No firmware changes. No dependency
upgrades.

Live Companion dispatch is explicitly opt-in; network I/O occurs only through
the configured live Companion sender/transport path. There are no automatic
retries or redirects.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass, replace
from typing import Optional, Protocol

from aula_bridge.dispatcher import Transport
from aula_bridge.provider import ProviderEvent

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_CAPACITY = 8
DEFAULT_JOIN_TIMEOUT = 5.0


@dataclass(frozen=True)
class _PendingRequest:
    """Frozen snapshot of a queued dispatch request.

    ProviderEvent is copied at enqueue time (via dataclasses.replace) so
    later mutation of the caller's ProviderEvent cannot affect the queued
    request data.
    """

    command: str
    payload: str
    event: ProviderEvent


class CompanionDispatchWorker:
    """Bounded asynchronous dispatch worker wrapping a Transport.

    Exactly one worker thread dequeues requests FIFO and calls
    transport.send(). Enqueue is non-blocking: a full queue drops the
    incoming event, increments an overflow counter, and logs a WARNING.

    Shutdown is signaled via threading.Event. close() rejects new events
    immediately, stops processing queued events, drops pending queued
    events (never replaying them), and attempts a bounded worker join.
    An already-running HTTP request cannot be forcibly cancelled; if the
    worker remains alive after the bounded join, that state is reported
    accurately via logging (a full shutdown is not falsely claimed).
    """

    def __init__(
        self,
        transport: Transport,
        *,
        queue_capacity: int = DEFAULT_QUEUE_CAPACITY,
        join_timeout: float = DEFAULT_JOIN_TIMEOUT,
    ) -> None:
        if queue_capacity < 1:
            raise ValueError(f"queue_capacity must be >= 1, got {queue_capacity}")
        if join_timeout <= 0:
            raise ValueError(f"join_timeout must be > 0, got {join_timeout}")

        self._transport = transport
        self._queue_capacity = queue_capacity
        self._join_timeout = join_timeout

        self._queue: queue.Queue[_PendingRequest] = queue.Queue(maxsize=queue_capacity)
        self._shutdown = threading.Event()
        self._closed = threading.Event()
        self._worker_finished = threading.Event()

        self._overflow_count = 0
        self._shutdown_drops = 0
        self._lock = threading.Lock()

        self._worker: Optional[threading.Thread] = None
        self._start_worker()

    def _start_worker(self) -> None:
        self._worker = threading.Thread(
            target=self._run,
            name="CompanionDispatchWorker",
            daemon=True,
        )
        self._worker.start()

    def _run(self) -> None:
        try:
            while not self._shutdown.is_set():
                try:
                    request = self._queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                try:
                    self._transport.send(request.command, request.payload, request.event)
                except Exception:
                    # Isolate worker exceptions: one failed event does not kill worker.
                    logger.exception(
                        "Worker exception while dispatching event command=%s device=%s seq=%d; continuing",
                        request.command,
                        request.event.device,
                        request.event.seq,
                    )
                finally:
                    self._queue.task_done()
        finally:
            self._worker_finished.set()

    def send(self, command: str, payload: str, event: ProviderEvent) -> None:
        """Enqueue a dispatch request. Returns immediately after enqueue or drop.

        Shutdown-state checking and queue admission are atomic relative to
        close(): both are performed under self._lock so a late send cannot
        enqueue after close() has drained the queue.
        """
        snapshot = _PendingRequest(
            command=command,
            payload=payload,
            event=replace(event),
        )
        with self._lock:
            if self._closed.is_set():
                # Reject new events immediately after shutdown.
                self._shutdown_drops += 1
                drops = self._shutdown_drops
                logger.warning(
                    "CompanionDispatchWorker late send rejected after shutdown (command=%s device=%s seq=%d; shutdown_drops=%d)",
                    command,
                    event.device,
                    event.seq,
                    drops,
                )
                return
            try:
                self._queue.put_nowait(snapshot)
            except queue.Full:
                # Overflow: drop incoming event, increment counter, log WARNING.
                self._overflow_count += 1
                count = self._overflow_count
                logger.warning(
                    "CompanionDispatchWorker queue overflow (capacity=%d); dropping event command=%s device=%s seq=%d (overflow_count=%d)",
                    self._queue_capacity,
                    command,
                    event.device,
                    event.seq,
                    count,
                )

    def flush(self) -> None:
        """Flush any buffered commands. No-op (no persistent buffering)."""

    def close(self) -> None:
        """Close the worker.

        Rejects new events immediately, stops processing queued events,
        drops pending queued events (never replayed), and attempts a
        bounded worker join. Idempotent.

        Shutdown-state setting and queue draining are performed under
        self._lock so a concurrent send() cannot enqueue after the queue
        has been drained.
        """
        with self._lock:
            if self._closed.is_set():
                return
            self._closed.set()
            self._shutdown.set()

            # Drop pending queued events - never replay them.
            drained = 0
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
                self._queue.task_done()
                drained += 1
            if drained:
                self._shutdown_drops += drained

        # Attempt bounded worker join; avoid blocking indefinitely.
        # Lock is NOT held during worker.join() (requirement 9).
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=self._join_timeout)
            if worker.is_alive():
                logger.warning(
                    "CompanionDispatchWorker worker did not terminate within join_timeout=%ds; "
                    "worker may still be alive (an in-flight HTTP request cannot be forcibly cancelled)",
                    self._join_timeout,
                )
        self._worker_finished.set()

    @property
    def overflow_count(self) -> int:
        with self._lock:
            return self._overflow_count

    @property
    def shutdown_drops(self) -> int:
        with self._lock:
            return self._shutdown_drops

    @property
    def is_alive(self) -> bool:
        worker = self._worker
        return worker is not None and worker.is_alive()

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def queue_capacity(self) -> int:
        return self._queue_capacity

    @property
    def shutdown_complete(self) -> bool:
        return self._worker_finished.is_set() and not self.is_alive
