"""Provider interface and dry-run JSON-logging provider for the bridge POC.

The provider is the only component that performs output. This POC implements a
single dry-run provider that writes deterministic structured JSON lines to a log
file. No Companion requests, no USB/HID/COM/screen commands are ever sent.

Event schema (one JSON object per line):
  {"event":"key_down","key":"numpad_1","device":"0C45:800A"}
  {"event":"short_press","key":"numpad_1","duration_ms":183,"device":"0C45:800A"}
  {"event":"hold","key":"numpad_1","duration_ms":700,"device":"0C45:800A"}
  {"event":"key_up","key":"numpad_1","held":true,"device":"0C45:800A"}
  {"event":"repeat_ignored","key":"numpad_1","device":"0C45:800A"}
  {"event":"secondary_hold","key":"numpad_1","duration_ms":2000,"device":"0C45:800A"}

The dry-run provider is deterministic: events are appended in call order, one
line per event, with stable field ordering and no timestamps (timestamps would
make output non-deterministic across runs). A sequence number is included for
ordering assertions in tests.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderEvent:
    """A structured event to emit through a provider."""

    event: str
    key: str
    device: str
    duration_ms: Optional[int] = None
    held: Optional[bool] = None
    seq: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "event": self.event,
            "key": self.key,
            "device": self.device,
            "seq": self.seq,
        }
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        if self.held is not None:
            data["held"] = self.held
        return data


class BridgeProvider:
    """Abstract provider interface for bridge output."""

    def emit(self, event: ProviderEvent) -> None:
        raise NotImplementedError

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class DryRunProvider(BridgeProvider):
    """Dry-run provider that writes deterministic structured JSON lines.

    Events are appended to a JSONL file in call order. Field order is stable.
    No Companion requests, no device access, no writes other than the log file.
    """

    def __init__(self, log_file: str, log_dir: str = "logs") -> None:
        self.log_file = log_file
        self.log_dir = log_dir
        self._path = os.path.join(log_dir, log_file)
        self._seq = 0
        self._emitted: List[ProviderEvent] = []
        os.makedirs(log_dir, exist_ok=True)
        # Truncate/initialize the log file for a fresh run.
        with open(self._path, "w", encoding="utf-8") as fh:
            fh.write("")

    def emit(self, event: ProviderEvent) -> None:
        self._seq += 1
        event.seq = self._seq
        self._emitted.append(event)
        line = json.dumps(event.to_dict(), separators=(",", ":"), sort_keys=False)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.flush()

    @property
    def events(self) -> List[ProviderEvent]:
        return list(self._emitted)

    @property
    def path(self) -> str:
        return self._path
