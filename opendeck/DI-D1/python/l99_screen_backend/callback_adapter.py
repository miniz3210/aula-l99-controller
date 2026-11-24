"""Bounded local IPC adapter between Rust OD1-R3 plugin and OD2-B Python backend.

Provides a local-only integration path (named pipe or in-process) that receives
genuine OpenDeck setImage callbacks from the running Rust device plugin and
forwards them to OD2-B for processing.

Does NOT expose public TCP listeners.
Does NOT start a second device registration.
Does NOT add a second device registration.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from .callback_handler import CallbackHandler, CallbackResult
from .backend import ScreenBackend

logger = logging.getLogger(__name__)


@dataclass
class CallbackMessage:
    """A callback message received from the Rust plugin side."""
    device_id: str
    position: Optional[int]
    image: Optional[str]
    source: str = "rust_plugin"


class CallbackAdapter:
    """Bounded local IPC adapter connecting Rust callback output to OD2-B.

    The adapter accepts callback messages either from an in-process queue
    (used for unit tests) or from a local named pipe listener (used for live
    integration with OD1-R3's existing named pipe mechanism).

    Max pending messages is bounded to prevent unbounded queue growth.
    """

    MAX_PENDING = 16

    def __init__(
        self,
        backend: Optional[ScreenBackend] = None,
        profile_id: Optional[str] = None,
        max_pending: int = MAX_PENDING,
    ) -> None:
        self._backend = backend or ScreenBackend()
        self._handler = CallbackHandler(self._backend, profile_id=profile_id)
        self._max_pending = max_pending
        self._queue: queue.Queue[CallbackMessage] = queue.Queue(maxsize=max_pending)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._on_result: Optional[Callable[[CallbackResult], None]] = None

    @property
    def handler(self) -> CallbackHandler:
        return self._handler

    @property
    def backend(self) -> ScreenBackend:
        return self._backend

    @property
    def profile_id(self) -> str:
        return self._handler.profile_id

    def set_profile_id(self, profile_id: str) -> None:
        self._handler.set_profile_id(profile_id)

    def set_result_callback(self, callback: Callable[[CallbackResult], None]) -> None:
        """Register a callback invoked when a message is processed."""
        self._on_result = callback

    def submit(self, device_id: str, position: Optional[int], image: Optional[str]) -> bool:
        """Submit a callback message from the Rust side.

        Returns True if accepted into the bounded queue, False if full.
        """
        msg = CallbackMessage(device_id=device_id, position=position, image=image)
        try:
            self._queue.put_nowait(msg)
            return True
        except queue.Full:
            logger.warning("Callback queue full, dropping message: device=%s pos=%s", device_id, position)
            return False

    def _process_message(self, msg: CallbackMessage) -> CallbackResult:
        result = self._handler.handle_callback(msg.device_id, msg.position, msg.image)
        if self._on_result:
            try:
                self._on_result(result)
            except Exception:
                logger.exception("Result callback raised")
        return result

    def process_one(self, block: bool = True, timeout: Optional[float] = None) -> Optional[CallbackResult]:
        """Process a single pending callback message.

        Returns the result, or None if no message is available (non-blocking).
        """
        try:
            msg = self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
        try:
            return self._process_message(msg)
        finally:
            self._queue.task_done()

    def start(self) -> None:
        """Start the background processing thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background processing thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while self._running:
            result = self.process_one(block=True, timeout=0.5)
            # result processed internally via on_result callback

    def submit_json(self, payload: str) -> bool:
        """Submit a JSON-serialized callback message (e.g. from named pipe).

        Expected JSON shape:
          {"device_id": "al-l99-0001", "position": 0, "image": "data:image/png;base64,..."}
          or {"device_id": "al-l99-0001", "position": 0, "image": null}   (clear one)
          or {"device_id": "al-l99-0001", "position": null, "image": null} (clear all)
        """
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON callback: %s", e)
            return False
        return self.submit(
            device_id=data.get("device_id", ""),
            position=data.get("position"),
            image=data.get("image"),
        )
