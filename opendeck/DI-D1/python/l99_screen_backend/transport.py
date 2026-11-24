"""Transport interface and MockTransport implementation for DI-D1.

Abstraction over screen region delivery. MockTransport is the only concrete
implementation. No physical USB commands, no public TCP listener, no L99
framebuffer command invention.
"""

from __future__ import annotations

import time
import json
import hashlib
import logging
import struct
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Protocol, Callable
from enum import Enum

from .layout import LayoutModel
from .state_manager import StateManager, PhysicalConfirmStatus
from .l99_mailbox import L99Mailbox, L99Error


class TransportStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CLEARED = "cleared"
    RECONNECTED = "reconnected"


@dataclass
class TransportRecord:
    timestamp: float
    device_id: str
    profile_id: str
    position: int
    image_sha256: str
    payload_length: int
    operation: str  # connect, disconnect, send_region, clear_region, reconnect
    status: TransportStatus
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class ScreenTransport(Protocol):
    """Transport abstraction protocol.

    Required operations:
      - connect(device_id, profile_id) -> bool
      - disconnect() -> bool
      - reconnect(device_id, profile_id) -> bool
      - send_region(position, rgb565_payload, sha256) -> bool
      - clear_region(position) -> bool
      - is_connected() -> bool
      - get_diagnostics() -> dict
    """

    def connect(self, device_id: str, profile_id: str) -> bool: ...
    def disconnect(self) -> bool: ...
    def reconnect(self, device_id: str, profile_id: str) -> bool: ...
    def send_region(self, position: int, rgb565_payload: bytes, sha256: str) -> bool: ...
    def clear_region(self, position: int) -> bool: ...
    def is_connected(self) -> bool: ...
    def get_diagnostics(self) -> dict: ...


class MockScreenTransport(ScreenTransport):
    """Mock screen transport: records operations, issues no hardware commands.

    Does NOT implement physical USB/serial/HID commands. Does NOT mark physical
    display as CONFIRMED - physical status remains SENT_UNCONFIRMED.
    """

    def __init__(self, layout: LayoutModel, state_manager: StateManager) -> None:
        self._layout = layout
        self._state_manager = state_manager
        self._connected = False
        self._device_id: Optional[str] = None
        self._profile_id: Optional[str] = None
        self._records: List[TransportRecord] = []
        self._max_records = 1000
        self._reconnect_count = 0
        self._send_failures = 0

    def connect(self, device_id: str, profile_id: str) -> bool:
        if self._connected:
            return False
        self._connected = True
        self._device_id = device_id
        self._profile_id = profile_id
        self._record(TransportRecord(
            timestamp=time.time(), device_id=device_id, profile_id=profile_id,
            position=-1, image_sha256="", payload_length=0,
            operation="connect", status=TransportStatus.CONNECTED,
        ))
        return True

    def disconnect(self) -> bool:
        if not self._connected:
            return False
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "", profile_id=self._profile_id or "",
            position=-1, image_sha256="", payload_length=0,
            operation="disconnect", status=TransportStatus.DISCONNECTED,
        ))
        self._connected = False
        self._device_id = None
        self._profile_id = None
        return True

    def reconnect(self, device_id: str, profile_id: str) -> bool:
        """Reconnect after a disconnect. Preserves desired state in caller."""
        was_connected = self._connected
        if self._connected:
            self.disconnect()
        ok = self.connect(device_id, profile_id)
        if ok:
            self._reconnect_count += 1
            self._record(TransportRecord(
                timestamp=time.time(), device_id=device_id, profile_id=profile_id,
                position=-1, image_sha256="", payload_length=0,
                operation="reconnect", status=TransportStatus.RECONNECTED,
            ))
        return ok

    def is_connected(self) -> bool:
        return self._connected

    def send_region(self, position: int, rgb565_payload: bytes, sha256: str) -> bool:
        if not self._connected:
            self._send_failures += 1
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "", profile_id=self._profile_id or "",
                position=position, image_sha256=sha256,
                payload_length=len(rgb565_payload),
                operation="send_region", status=TransportStatus.FAILED,
                error_message="Transport not connected",
            ))
            return False

        if not self._layout.validate_position(position):
            self._send_failures += 1
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "", profile_id=self._profile_id or "",
                position=position, image_sha256=sha256,
                payload_length=len(rgb565_payload),
                operation="send_region", status=TransportStatus.FAILED,
                error_message=f"Invalid position {position}",
            ))
            return False

        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "", profile_id=self._profile_id or "",
            position=position, image_sha256=sha256,
            payload_length=len(rgb565_payload),
            operation="send_region", status=TransportStatus.SENT,
        ))

        if self._device_id and self._profile_id:
            self._state_manager.mark_sent_unconfirmed(
                self._device_id, self._profile_id, position
            )
        return True

    def clear_region(self, position: int) -> bool:
        if not self._connected:
            self._send_failures += 1
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "", profile_id=self._profile_id or "",
                position=position, image_sha256="", payload_length=0,
                operation="clear_region", status=TransportStatus.FAILED,
                error_message="Transport not connected",
            ))
            return False

        if not self._layout.validate_position(position):
            self._send_failures += 1
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "", profile_id=self._profile_id or "",
                position=position, image_sha256="", payload_length=0,
                operation="clear_region", status=TransportStatus.FAILED,
                error_message=f"Invalid position {position}",
            ))
            return False

        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "", profile_id=self._profile_id or "",
            position=position, image_sha256="", payload_length=0,
            operation="clear_region", status=TransportStatus.CLEARED,
        ))

        if self._device_id and self._profile_id:
            self._state_manager.set_physical_status(
                self._device_id, self._profile_id, position,
                PhysicalConfirmStatus.SENT_UNCONFIRMED,
            )
        return True

    def get_records(self) -> List[TransportRecord]:
        return list(self._records)

    def get_records_for_profile(self, device_id: str, profile_id: str) -> List[TransportRecord]:
        return [r for r in self._records
                if r.device_id == device_id and r.profile_id == profile_id]

    def export_trace(self, path: str) -> None:
        data = {
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "connected": self._connected,
            "reconnect_count": self._reconnect_count,
            "send_failures": self._send_failures,
            "record_count": len(self._records),
            "records": [r.to_dict() for r in self._records],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def get_diagnostics(self) -> dict:
        ops: dict[str, dict[str, int]] = {}
        for record in self._records:
            op = record.operation
            if op not in ops:
                ops[op] = {"sent": 0, "failed": 0, "cleared": 0, "connected": 0,
                           "disconnected": 0, "reconnected": 0}
            status_val = record.status.value
            ops[op][status_val] = ops[op].get(status_val, 0) + 1
        return {
            "connected": self._connected,
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "reconnect_count": self._reconnect_count,
            "send_failures": self._send_failures,
            "total_records": len(self._records),
            "operations": ops,
        }

    def clear_records(self) -> None:
        self._records.clear()

    # ------------------------------------------------------------------
    # Safety: no physical hardware operations exposed
    # ------------------------------------------------------------------
    def _record(self, record: TransportRecord) -> None:
        """Add record to history with size limit."""
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)

    @property
    def has_usb_write(self) -> bool:
        return False

    @property
    def has_serial_write(self) -> bool:
        return False

    @property
    def has_firmware_flash(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Slot configuration
# ---------------------------------------------------------------------------
def load_slot_config(path: str) -> dict:
    """Load and validate the L99 icon slot configuration.

    Validation:
      - every slot inside the screen
      - w*h <= 6144 (pixel buffer limit)
      - no overlapping slots
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    screen_w, screen_h = cfg["screen"]
    icon_w, icon_h = cfg["icon_size"]
    slots = cfg["slots"]

    rects: Dict[int, tuple[int, int, int, int]] = {}
    used: List[tuple[int, int, int, int]] = []

    for key, pos in slots.items():
        if key == "...":
            continue
        position = int(key)
        x, y = int(pos[0]), int(pos[1])
        w, h = int(icon_w), int(icon_h)

        if not (0 <= x and x + w <= screen_w and 0 <= y and y + h <= screen_h):
            raise ValueError(f"slot {position} rect ({x},{y},{w}x{h}) outside screen {screen_w}x{screen_h}")
        if w * h > 6144:
            raise ValueError(f"slot {position} {w}*{h}={w*h} exceeds pixel buffer 6144")

        rect = (x, y, w, h)
        for ux, uy, uw, uh in used:
            if x < ux + uw and ux < x + w and y < uy + uh and uy < y + h:
                raise ValueError(f"slot {position} overlaps slot at ({ux},{uy},{uw}x{uh})")
        used.append(rect)
        rects[position] = rect

    return {"screen": [screen_w, screen_h], "icon_size": [icon_w, icon_h], "rects": rects}


def slot_rect(cfg: dict, position: int) -> Optional[tuple[int, int, int, int]]:
    """Return (x, y, w, h) for a position, or None if not configured."""
    return cfg["rects"].get(position)


# ---------------------------------------------------------------------------
# MailboxTransport
# ---------------------------------------------------------------------------
class MailboxTransport(ScreenTransport):
    """L99 icon mailbox transport implementing the ScreenTransport protocol.

    Delivers icons to the L99 mailbox (VP 0x1F00) via L99Mailbox.upload.
    Reuses scheduler/dirty-region coalescing logic from the DI-D1 backend;
    this transport only owns the per-position pending buffer and uploads the
    newest image per position on flush.

    No serial/COM/HID/USB writes. Transports: in-memory fake (tests) or TCP
    to the CEmu bridge via an SSH tunnel.
    """

    def __init__(
        self,
        layout: LayoutModel,
        state_manager: StateManager,
        slot_config_path: Optional[str] = None,
        device_id: str = "al-l99-0001",
        profile_id: str = "default",
        page_poll_s: float = 1.0,
        mailbox: Optional[L99Mailbox] = None,
    ) -> None:
        from PIL import Image  # PIL is a package dependency (image_processor)

        self._Image = Image
        self._layout = layout
        self._state_manager = state_manager
        self._device_id = device_id
        self._profile_id = profile_id
        self._connected = False
        self._records: List[TransportRecord] = []
        self._max_records = 1000
        self._reconnect_count = 0
        self._send_failures = 0
        self._page_poll_s = float(page_poll_s)
        self._mailbox = mailbox
        self._cfg = load_slot_config(slot_config_path) if slot_config_path else None
        self._pending: Dict[int, tuple[list[int], str]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._page_thread: Optional[threading.Thread] = None
        self._last_page: Optional[int] = None
        self._backoff_s = 0.5
        self._max_backoff_s = 5.0
        self._logger = logging.getLogger(__name__)

    # -- slot helpers -------------------------------------------------------
    def rect_for_position(self, position: int) -> Optional[tuple[int, int, int, int]]:
        if self._cfg is None:
            return None
        return slot_rect(self._cfg, position)

    # -- image conversion ---------------------------------------------------
    def _image_to_rgb565_ints(self, image: Any, w: int, h: int) -> list[int]:
        """Letterbox-resize ``image`` to w x h (keep aspect, black background)
        and return RGB565 ints row-major. Accepts a PIL Image, a path/bytes to
        an image, or an already-converted list of RGB565 ints."""
        if isinstance(image, (list, tuple)):
            px = [int(p) & 0xFFFF for p in image]
            if len(px) != w * h:
                raise ValueError(f"pixel count {len(px)} != {w * h}")
            return px
        img = self._Image.open(image) if isinstance(image, (str, bytes, bytearray)) else image
        if img.mode != "RGB":
            img = img.convert("RGB")
        iw, ih = img.size
        scale = min(w / iw, h / ih)
        nw, nh = max(1, round(iw * scale)), max(1, round(ih * scale))
        img = img.resize((nw, nh), self._Image.Resampling.LANCZOS)
        canvas = self._Image.new("RGB", (w, h), (0, 0, 0))
        ox, oy = (w - nw) // 2, (h - nh) // 2
        canvas.paste(img, (ox, oy))
        px = canvas.load()
        out: list[int] = []
        for yy in range(h):
            for xx in range(w):
                r, g, b = px[xx, yy]
                out.append(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
        return out

    def _bytes_to_rgb565_ints(self, data: bytes, count: int) -> list[int]:
        return list(struct.unpack("<%dH" % count, data[: count * 2]))

    # -- transport protocol -------------------------------------------------
    def connect(self, device_id: str, profile_id: str) -> bool:
        if self._connected:
            return False
        self._device_id = device_id
        self._profile_id = profile_id
        if self._mailbox is None:
            # TCP mode not configured for MailboxTransport directly; require a
            # mailbox instance to be injected.
            raise L99Error("MailboxTransport requires an injected L99Mailbox")
        self._connected = True
        self._last_page = None
        self._record(TransportRecord(
            timestamp=time.time(), device_id=device_id, profile_id=profile_id,
            position=-1, image_sha256="", payload_length=0,
            operation="connect", status=TransportStatus.CONNECTED,
        ))
        self._start_page_watch()
        return True

    def disconnect(self) -> bool:
        if not self._connected:
            return False
        self._stop_page_watch()
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "", profile_id=self._profile_id or "",
            position=-1, image_sha256="", payload_length=0,
            operation="disconnect", status=TransportStatus.DISCONNECTED,
        ))
        self._connected = False
        self._device_id = None
        self._profile_id = None
        return True

    def reconnect(self, device_id: str, profile_id: str) -> bool:
        was_connected = self._connected
        if self._connected:
            self.disconnect()
        ok = self.connect(device_id, profile_id)
        if ok:
            self._reconnect_count += 1
            self._record(TransportRecord(
                timestamp=time.time(), device_id=device_id, profile_id=profile_id,
                position=-1, image_sha256="", payload_length=0,
                operation="reconnect", status=TransportStatus.RECONNECTED,
            ))
            self.resend_page()
        return ok

    def is_connected(self) -> bool:
        return self._connected

    def send_region(self, position: int, rgb565_payload: bytes, sha256: str) -> bool:
        """Protocol send: upload slot-size RGB565 LE payload to the position rect."""
        if not self._connected:
            self._send_failures += 1
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "", profile_id=self._profile_id or "",
                position=position, image_sha256=sha256,
                payload_length=len(rgb565_payload), operation="send_region",
                status=TransportStatus.FAILED, error_message="Transport not connected",
            ))
            return False
        rect = self.rect_for_position(position)
        if rect is None:
            self._send_failures += 1
            self._record(TransportRecord(
                timestamp=time.time(),
                device_id=self._device_id or "", profile_id=self._profile_id or "",
                position=position, image_sha256=sha256,
                payload_length=len(rgb565_payload), operation="send_region",
                status=TransportStatus.FAILED, error_message=f"Invalid position {position}",
            ))
            return False
        x, y, w, h = rect
        try:
            pixels = self._bytes_to_rgb565_ints(rgb565_payload, w * h)
            res = self._upload(x, y, w, h, pixels, position, sha256)
        except L99Error as e:
            return self._on_upload_error(position, sha256, len(rgb565_payload), str(e))
        return res

    def clear_region(self, position: int) -> bool:
        """Protocol clear: upload an all-black icon of the slot size."""
        return self.CLEAR_POSITION(position)

    # -- consumer API -------------------------------------------------------
    def SET_IMAGE(self, position: int, image: Any) -> bool:
        """Queue an icon for ``position`` (coalesces: latest per position wins).

        Resizes ``image`` to the slot size (letterbox black), converts to
        RGB565 ints row-major, and stores as the pending update for the
        position. Call flush() to upload pending icons.
        """
        if not self._connected:
            self._send_failures += 1
            return False
        rect = self.rect_for_position(position)
        if rect is None:
            self._send_failures += 1
            return False
        x, y, w, h = rect
        try:
            pixels = self._image_to_rgb565_ints(image, w, h)
        except Exception:
            self._send_failures += 1
            return False
        sha = hashlib.sha256(struct.pack("<%dH" % len(pixels), *pixels)).hexdigest()
        with self._lock:
            self._pending[position] = (pixels, sha)
        return True

    def CLEAR_POSITION(self, position: int) -> bool:
        """Upload an all-black (0x0000) icon of the slot size."""
        rect = self.rect_for_position(position)
        if rect is None:
            self._send_failures += 1
            return False
        x, y, w, h = rect
        pixels = [0] * (w * h)
        sha = hashlib.sha256(b"\x00\x00" * (w * h)).hexdigest()
        try:
            res = self._upload(x, y, w, h, pixels, position, sha)
        except L99Error as e:
            return self._on_upload_error(position, sha, 0, str(e))
        return res["status"] == "DONE"

    def flush(self) -> List[dict]:
        """Upload all pending icons (newest per position) and clear the queue.

        Returns per-position upload status dicts.
        """
        with self._lock:
            pending = dict(self._pending)
            self._pending.clear()
        results: List[dict] = []
        for position in sorted(pending.keys()):
            pixels, sha = pending[position]
            rect = self.rect_for_position(position)
            if rect is None:
                continue
            x, y, w, h = rect
            try:
                res = self._upload(x, y, w, h, pixels, position, sha)
                results.append({"position": position, "status": res["status"], **res})
            except L99Error as e:
                self._on_upload_error(position, sha, len(pixels) * 2, str(e))
                results.append({"position": position, "status": "ERROR", "error": str(e)})
        return results

    def resend_page(self, page: Optional[int] = None) -> List[str]:
        """Re-upload cached icons for the current (or given) page."""
        if self._mailbox is None:
            return []
        return self._mailbox.resend_page(page=page)

    def get_diagnostics(self) -> dict:
        return {
            "connected": self._connected,
            "device_id": self._device_id,
            "profile_id": self._profile_id,
            "reconnect_count": self._reconnect_count,
            "send_failures": self._send_failures,
            "total_records": len(self._records),
            "pending_count": len(self._pending),
            "page_poll_s": self._page_poll_s,
            "backoff_s": self._backoff_s,
            "max_backoff_s": self._max_backoff_s,
            "slots_configured": len(self._cfg["rects"]) if self._cfg else 0,
        }

    def get_records(self) -> List[TransportRecord]:
        return list(self._records)

    # -- internal -----------------------------------------------------------
    def _upload(self, x: int, y: int, w: int, h: int, pixels: list[int],
                position: int, sha256: str) -> dict:
        if self._mailbox is None:
            raise L99Error("no mailbox")
        res = self._mailbox.upload(x, y, w, h, pixels)
        status = res["status"]
        self._logger.info(
            "upload position=%d rect=(%d,%d,%dx%d) status=%s frames=%s seconds=%s",
            position, x, y, w, h, status, res.get("frames"), res.get("seconds"),
        )
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "", profile_id=self._profile_id or "",
            position=position, image_sha256=sha256,
            payload_length=len(pixels) * 2, operation="send_region",
            status=TransportStatus.SENT if status == "DONE" else TransportStatus.FAILED,
            error_message=None if status == "DONE" else status,
        ))
        if self._device_id and self._profile_id:
            self._state_manager.mark_sent_unconfirmed(
                self._device_id, self._profile_id, position
            )
        return res

    def _on_upload_error(self, position: int, sha256: str, payload_length: int,
                         message: str) -> bool:
        self._send_failures += 1
        self._record(TransportRecord(
            timestamp=time.time(),
            device_id=self._device_id or "", profile_id=self._profile_id or "",
            position=position, image_sha256=sha256,
            payload_length=payload_length, operation="send_region",
            status=TransportStatus.FAILED, error_message=message,
        ))
        self._reconnect_with_backoff()
        return False

    def _reconnect_with_backoff(self) -> None:
        """Reconnect with exponential backoff 0.5s..5s, then resend_page()."""
        delay = self._backoff_s
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline and not self._stop_event.is_set():
            try:
                if self.connect(self._device_id, self._profile_id):
                    self._reconnect_count += 1
                    self._record(TransportRecord(
                        timestamp=time.time(),
                        device_id=self._device_id or "", profile_id=self._profile_id or "",
                        position=-1, image_sha256="", payload_length=0,
                        operation="reconnect", status=TransportStatus.RECONNECTED,
                    ))
                    self.resend_page()
                    return
            except L99Error:
                pass
            time.sleep(min(delay, self._max_backoff_s))
            delay = min(delay * 2, self._max_backoff_s)

    # -- page watch ---------------------------------------------------------
    def _start_page_watch(self) -> None:
        self._stop_event.clear()
        self._page_thread = threading.Thread(target=self._page_watch_loop, daemon=True)
        self._page_thread.start()

    def _stop_page_watch(self) -> None:
        self._stop_event.set()
        if self._page_thread is not None:
            self._page_thread.join(timeout=2.0)
            self._page_thread = None

    def _page_watch_loop(self) -> None:
        while not self._stop_event.wait(self._page_poll_s):
            try:
                if not self._connected or self._mailbox is None:
                    continue
                page = self._mailbox.page()
                if self._last_page is None:
                    self._last_page = page
                    continue
                if page != self._last_page:
                    self._last_page = page
                    self.resend_page(page)
            except L99Error:
                self._reconnect_with_backoff()
            except Exception:
                continue

    def _record(self, record: TransportRecord) -> None:
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records.pop(0)
