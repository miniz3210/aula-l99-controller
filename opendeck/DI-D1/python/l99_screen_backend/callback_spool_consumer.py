"""Local callback spool consumer for OD2-B-R2.

Watches the local callback spool directory produced by the Rust plugin,
validates each spool event, processes the normalized PNG, converts to RGB565,
submits to MockTransport, and archives/removes processed events.

Local-only: no TCP listeners, no physical USB writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from l99_screen_backend.backend import ScreenBackend, ImageUpdateRequest
from l99_screen_backend.image_processor import ImageProcessor
from l99_screen_backend.state_manager import PhysicalConfirmStatus


SPOOL_SCHEMA_VERSION = 1
SUPPORTED_OPERATIONS = {"SET_IMAGE", "CLEAR_POSITION", "CLEAR_ALL"}
DEVICE_ID = "al-l99-0001"
PROFILE_ID = "default"
MAX_EVENT_BYTES = 2_000_000  # max event file size (metadata only, image is separate)
MAX_RETRY_COUNT = 3

SUPPORTED_TRANSPORTS = {"mock", "cemu_tcp"}
DEFAULT_TRANSPORT = "mock"
DEFAULT_CEMU_HOST = "127.0.0.1"
DEFAULT_CEMU_PORT = 7799


@dataclass
class ProcessingResult:
    """Result of processing a single spool event."""
    event_id: str
    operation: str
    position: Optional[int]
    accepted: bool
    rgb565_sha256: Optional[str] = None
    rgb565_bytes: int = 0
    error: Optional[str] = None
    archived: bool = False
    quarantined: bool = False


@dataclass
class ConsumerStats:
    """Consumer runtime statistics."""
    processed: int = 0
    accepted: int = 0
    rejected: int = 0
    quarantined: int = 0
    duplicates_suppressed: int = 0
    errors: list[str] = field(default_factory=list)


class CallbackSpoolConsumer:
    """Polls and consumes callback spool events produced by the Rust plugin.

    Contract:
      - Reads JSON event files from the spool directory
      - Validates schema_version, event_id, device_id, position, operation
      - Verifies normalized PNG SHA-256
      - Resizes to 80x120, converts RGB565 LE
      - Submits to MockTransport (SENT_UNCONFIRMED)
      - Archives or quarantines processed payloads
      - No physical USB access
    """

    def __init__(
        self,
        spool_dir: str | Path = "runtime/callback_spool",
        backend: Optional[ScreenBackend] = None,
        max_retries: int = MAX_RETRY_COUNT,
        transport: str = DEFAULT_TRANSPORT,
        cemu_host: str = DEFAULT_CEMU_HOST,
        cemu_port: int = DEFAULT_CEMU_PORT,
    ) -> None:
        if transport not in SUPPORTED_TRANSPORTS:
            raise ValueError(
                f"unsupported transport: {transport!r} (supported: {sorted(SUPPORTED_TRANSPORTS)})"
            )
        self.transport = transport
        self.cemu_host = cemu_host
        self.cemu_port = int(cemu_port)
        self.spool_dir = Path(spool_dir)
        self.inbox_dir = self.spool_dir
        self.quarantine_dir = self.spool_dir / "quarantine"
        self.archive_dir = self.spool_dir / "archive"
        self.backend = backend or ScreenBackend()
        self._processor = ImageProcessor()
        self._max_retries = max_retries
        self._running = False
        self._stats = ConsumerStats()
        self._processed_event_ids: set[str] = set()
        self._on_result: Optional[Callable[[ProcessingResult], None]] = None

    @property
    def stats(self) -> ConsumerStats:
        return self._stats

    @property
    def processed_event_ids(self) -> set[str]:
        return set(self._processed_event_ids)

    def set_result_callback(self, callback: Callable[[ProcessingResult], None]) -> None:
        self._on_result = callback

    # ------------------------------------------------------------------ #
    # Schema / validation helpers
    # ------------------------------------------------------------------ #
    def _validate_event(self, data: dict) -> tuple[bool, Optional[str]]:
        """Validate the spool event schema and required fields."""
        if not isinstance(data, dict):
            return False, "Event is not a JSON object"

        # schema_version
        sv = data.get("schema_version")
        if sv != SPOOL_SCHEMA_VERSION:
            return False, f"Unsupported schema_version: {sv} (expected {SPOOL_SCHEMA_VERSION})"

        # event_id
        event_id = data.get("event_id")
        if not event_id or not isinstance(event_id, str):
            return False, "Missing or invalid event_id"

        # device_id
        device_id = data.get("device_id")
        if device_id != DEVICE_ID:
            return False, f"Invalid device_id: {device_id} (expected {DEVICE_ID})"

        # position
        position = data.get("position")

        # operation
        operation = data.get("operation")
        if operation not in SUPPORTED_OPERATIONS:
            return False, f"Invalid or missing operation: {operation}"

        # timestamp_utc (must be present)
        if "timestamp_utc" not in data:
            return False, "Missing timestamp_utc"

        # For SET_IMAGE: require normalized_png_sha256 and normalized_png_file
        if operation == "SET_IMAGE":
            if not data.get("normalized_png_sha256"):
                return False, "SET_IMAGE missing normalized_png_sha256"
            if not data.get("normalized_png_file"):
                return False, "SET_IMAGE missing normalized_png_file"

        return True, None

    def _validate_png_sha256(
        self, payload_path: Path, expected_sha256: str
    ) -> tuple[bool, Optional[str]]:
        """Verify the PNG payload file SHA-256 matches expected."""
        if not payload_path.exists():
            return False, f"Payload file not found: {payload_path}"

        # Reject path traversal in payload filename
        resolved = payload_path.resolve()
        spool_resolved = self.spool_dir.resolve()
        try:
            resolved.relative_to(spool_resolved)
        except ValueError:
            return False, "Payload path escapes spool directory"

        try:
            data = payload_path.read_bytes()
        except OSError as e:
            return False, f"Cannot read payload file: {e}"

        if len(data) > MAX_EVENT_BYTES:
            return False, f"Payload {len(data)} bytes exceeds limit"

        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "Payload is not a valid PNG (magic bytes mismatch)"

        actual = hashlib.sha256(data).hexdigest()
        if actual != expected_sha256:
            return False, f"SHA-256 mismatch: expected {expected_sha256}, got {actual}"

        return True, None

    def _is_duplicate(self, event_id: str) -> bool:
        return event_id in self._processed_event_ids

    def _mark_processed(self, event_id: str) -> None:
        self._processed_event_ids.add(event_id)

    # ------------------------------------------------------------------ #
    # Event processing
    # ------------------------------------------------------------------ #
    def process_event_file(self, event_path: Path) -> ProcessingResult:
        """Process a single spool event file."""
        event_id = event_path.stem

        # Duplicate check
        if self._is_duplicate(event_id):
            self._stats.duplicates_suppressed += 1
            return ProcessingResult(
                event_id=event_id,
                operation="DUPLICATE",
                position=None,
                accepted=True,
                archived=True,
            )

        # Read and parse event JSON
        try:
            raw = event_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            self._stats.rejected += 1
            return ProcessingResult(
                event_id=event_id,
                operation="UNKNOWN",
                position=None,
                accepted=False,
                error=f"Invalid event JSON: {e}",
                quarantined=True,
            )

        # Schema validation
        ok, err = self._validate_event(data)
        if not ok:
            self._stats.rejected += 1
            self._quarantine(event_path, data, err)
            return ProcessingResult(
                event_id=data.get("event_id", event_id),
                operation=data.get("operation", "UNKNOWN"),
                position=data.get("position"),
                accepted=False,
                error=err,
                quarantined=True,
            )

        operation = data["operation"]
        position = data.get("position")
        timestamp = time.time()

        # For CLEAR operations
        if operation == "CLEAR_POSITION" and position is not None:
            result = self._process_clear(position, timestamp)
            self._finalize(event_path, event_id, operation, position, result)
            return result

        if operation == "CLEAR_ALL":
            restored = self.backend.handle_reconnect(DEVICE_ID, PROFILE_ID)
            cleared = 0
            for pos in range(self.backend.layout.TOTAL_POSITIONS):
                req = ImageUpdateRequest(
                    device_id=DEVICE_ID,
                    profile_id=PROFILE_ID,
                    position=pos,
                    data_url=None,
                    timestamp=timestamp,
                )
                r = self.backend.process_image_update(req)
                if r.success:
                    cleared += 1
            self._finalize(
                event_path,
                event_id,
                operation,
                None,
                ProcessingResult(
                    event_id=event_id,
                    operation=operation,
                    position=None,
                    accepted=True,
                    archived=True,
                ),
            )
            self._stats.processed += 1
            self._stats.accepted += 1
            return ProcessingResult(
                event_id=event_id,
                operation=operation,
                position=None,
                accepted=True,
                archived=True,
            )

        # SET_IMAGE path
        if operation == "SET_IMAGE":
            sha256 = data["normalized_png_sha256"]
            png_file = data["normalized_png_file"]
            payload_path = self.spool_dir / png_file

            ok, err = self._validate_png_sha256(payload_path, sha256)
            if not ok:
                self._stats.rejected += 1
                self._quarantine(event_path, data, err)
                return ProcessingResult(
                    event_id=event_id,
                    operation=operation,
                    position=position,
                    accepted=False,
                    error=err,
                    quarantined=True,
                )

            # Read payload and build data URL for processor
            try:
                png_bytes = payload_path.read_bytes()
            except OSError as e:
                self._stats.rejected += 1
                self._quarantine(event_path, data, f"Cannot read payload: {e}")
                return ProcessingResult(
                    event_id=event_id,
                    operation=operation,
                    position=position,
                    accepted=False,
                    error=f"Cannot read payload: {e}",
                    quarantined=True,
                )

            import base64

            b64 = base64.b64encode(png_bytes).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"

            processed, err = self._processor.process_image(position, data_url, timestamp)
            if err or processed is None:
                self._stats.rejected += 1
                self._quarantine(event_path, data, err or "image processing failed")
                return ProcessingResult(
                    event_id=event_id,
                    operation=operation,
                    position=position,
                    accepted=False,
                    error=err,
                    quarantined=True,
                )

            # Submit to backend (cache + state + mock transport)
            request = ImageUpdateRequest(
                device_id=DEVICE_ID,
                profile_id=PROFILE_ID,
                position=position,
                data_url=data_url,
                timestamp=timestamp,
            )
            backend_result = self.backend.process_image_update(request)

            self._stats.processed += 1
            if backend_result.success:
                self._stats.accepted += 1
            else:
                self._stats.rejected += 1

            result = ProcessingResult(
                event_id=event_id,
                operation=operation,
                position=position,
                accepted=backend_result.success,
                rgb565_sha256=processed.sha256,
                rgb565_bytes=len(processed.rgb565_data),
                error=backend_result.error,
                archived=True,
            )
            self._finalize(event_path, event_id, operation, position, result)
            return result

        # Unknown operation (should not reach here due to validation)
        self._stats.rejected += 1
        self._quarantine(event_path, data, f"Unsupported operation: {operation}")
        return ProcessingResult(
            event_id=event_id,
            operation=operation,
            position=position,
            accepted=False,
            error=f"Unsupported operation: {operation}",
            quarantined=True,
        )

    def _process_clear(self, position: int, timestamp: float) -> ProcessingResult:
        request = ImageUpdateRequest(
            device_id=DEVICE_ID,
            profile_id=PROFILE_ID,
            position=position,
            data_url=None,
            timestamp=timestamp,
        )
        backend_result = self.backend.process_image_update(request)
        self._stats.processed += 1
        if backend_result.success:
            self._stats.accepted += 1
        else:
            self._stats.rejected += 1
        return ProcessingResult(
            event_id="",
            operation="CLEAR_POSITION",
            position=position,
            accepted=backend_result.success,
            error=backend_result.error,
            archived=True,
        )

    def _finalize(
        self,
        event_path: Path,
        event_id: str,
        operation: str,
        position: Optional[int],
        result: ProcessingResult,
    ) -> None:
        self._mark_processed(event_id)
        if self._on_result:
            try:
                result_copy = ProcessingResult(
                    event_id=event_id,
                    operation=operation,
                    position=position,
                    accepted=result.accepted,
                    rgb565_sha256=result.rgb565_sha256,
                    rgb565_bytes=result.rgb565_bytes,
                    error=result.error,
                    archived=result.archived,
                    quarantined=result.quarantined,
                )
                self._on_result(result_copy)
            except Exception:
                pass

    def _quarantine(
        self, event_path: Path, data: dict, reason: str
    ) -> None:
        """Move an invalid event and its payload to quarantine."""
        try:
            self.quarantine_dir.mkdir(parents=True, exist_ok=True)
            dest = self.quarantine_dir / event_path.name
            shutil.move(str(event_path), str(dest))
            # Write a sidecar with the rejection reason
            meta = dest.with_suffix(".rejected.json")
            meta.write_text(
                json.dumps({"reason": reason, "event": data}, indent=2),
                encoding="utf-8",
            )
            # Quarantine associated payload if any
            png_file = data.get("normalized_png_file")
            if png_file:
                payload_path = self.spool_dir / png_file
                if payload_path.exists():
                    shutil.move(str(payload_path), str(self.quarantine_dir / payload_path.name))
            self._stats.quarantined += 1
        except OSError:
            pass

    def _archive(self, event_path: Path, data: dict) -> None:
        """Archive a successfully processed event and its payload."""
        try:
            self.archive_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(event_path), str(self.archive_dir / event_path.name))
            png_file = data.get("normalized_png_file")
            if png_file:
                payload_path = self.spool_dir / png_file
                if payload_path.exists():
                    shutil.move(str(payload_path), str(self.archive_dir / payload_path.name))
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Polling loop
    # ------------------------------------------------------------------ #
    def scan_once(self) -> list[ProcessingResult]:
        """Scan the spool directory once and process all pending events.

        Returns a list of processing results.
        """
        results: list[ProcessingResult] = []
        if not self.inbox_dir.exists():
            return results

        event_files = sorted(
            [p for p in self.inbox_dir.iterdir() if p.suffix == ".json" and p.name.endswith(".json")]
        )

        for event_path in event_files:
            # Skip temporary files
            if event_path.suffix == ".tmp":
                continue
            result = self.process_event_file(event_path)
            results.append(result)
            if result.archived and not result.quarantined:
                # Re-read data for archiving (may have been moved in quarantine)
                try:
                    data = json.loads(event_path.read_text(encoding="utf-8")) if event_path.exists() else {}
                except Exception:
                    data = {}
                if not result.quarantined:
                    self._archive(event_path, data)

        return results

    def run_forever(self, poll_interval: float = 0.5, max_iterations: Optional[int] = None) -> None:
        """Run the consumer loop until stopped or max_iterations reached."""
        self._running = True
        iterations = 0
        while self._running:
            self.scan_once()
            iterations += 1
            if max_iterations is not None and iterations >= max_iterations:
                break
            time.sleep(poll_interval)
        self._running = False

    def stop(self) -> None:
        self._running = False

    def get_stats_dict(self) -> dict:
        return {
            "processed": self._stats.processed,
            "accepted": self._stats.accepted,
            "rejected": self._stats.rejected,
            "quarantined": self._stats.quarantined,
            "duplicates_suppressed": self._stats.duplicates_suppressed,
            "errors": self._stats.errors,
            "processed_event_count": len(self._processed_event_ids),
        }
