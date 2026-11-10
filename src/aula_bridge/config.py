"""Configuration for the AULA L99 Windows input bridge POC.

All values are read from a JSON config file (default: config/bridge_config.json
next to the entry point) with sensible built-in defaults. No Companion settings
are present; provider selection supports only the dry-run provider in this POC.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict

# Default configuration values.
DEFAULT_VID = 0x0C45
DEFAULT_PID = 0x800A
DEFAULT_SHORT_THRESHOLD_MS = 500
DEFAULT_HOLD_THRESHOLD_MS = 700
DEFAULT_SECONDARY_HOLD_MS = 2000
DEFAULT_SECONDARY_HOLD_ENABLED = False
DEFAULT_STUCK_KEY_TIMEOUT_MS = 5000
DEFAULT_PROVIDER = "dry_run"
DEFAULT_LOG_FILE = "bridge_events.jsonl"
DEFAULT_LOG_DIR = "logs"

# Verified Mini Numpad return values (0x0030-0x0040) -> logical key IDs.
# See docs/PROJECT_HANDOVER.md section 8 (Page 21 Mini Numpad).
DEFAULT_KEY_MAPPINGS: Dict[int, str] = {
    0x0030: "numpad_num",
    0x0031: "numpad_divide",
    0x0032: "numpad_multiply",
    0x0033: "numpad_minus",
    0x0034: "numpad_7",
    0x0035: "numpad_8",
    0x0036: "numpad_9",
    0x0037: "numpad_plus",
    0x0038: "numpad_4",
    0x0039: "numpad_5",
    0x003A: "numpad_6",
    0x003B: "numpad_1",
    0x003C: "numpad_2",
    0x003D: "numpad_3",
    0x003E: "numpad_enter",
    0x003F: "numpad_0",
    0x0040: "numpad_decimal_delete",
}

CONFIG_ENV_VAR = "AULA_BRIDGE_CONFIG"


@dataclass
class BridgeConfig:
    """Immutable configuration for the input bridge POC."""

    vid: int = DEFAULT_VID
    pid: int = DEFAULT_PID
    short_threshold_ms: int = DEFAULT_SHORT_THRESHOLD_MS
    hold_threshold_ms: int = DEFAULT_HOLD_THRESHOLD_MS
    secondary_hold_ms: int = DEFAULT_SECONDARY_HOLD_MS
    secondary_hold_enabled: bool = DEFAULT_SECONDARY_HOLD_ENABLED
    stuck_key_timeout_ms: int = DEFAULT_STUCK_KEY_TIMEOUT_MS
    provider: str = DEFAULT_PROVIDER
    log_file: str = DEFAULT_LOG_FILE
    log_dir: str = DEFAULT_LOG_DIR
    key_mappings: Dict[int, str] = field(default_factory=lambda: dict(DEFAULT_KEY_MAPPINGS))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["key_mappings"] = {str(k): v for k, v in self.key_mappings.items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BridgeConfig":
        mappings = {}
        for k, v in data.get("key_mappings", {}).items():
            mappings[int(k, 0) if isinstance(k, str) and k.startswith("0x") else int(k)] = v
        return cls(
            vid=int(data.get("vid", DEFAULT_VID), 0) if isinstance(data.get("vid"), str) else int(data.get("vid", DEFAULT_VID)),
            pid=int(data.get("pid", DEFAULT_PID), 0) if isinstance(data.get("pid"), str) else int(data.get("pid", DEFAULT_PID)),
            short_threshold_ms=int(data.get("short_threshold_ms", DEFAULT_SHORT_THRESHOLD_MS)),
            hold_threshold_ms=int(data.get("hold_threshold_ms", DEFAULT_HOLD_THRESHOLD_MS)),
            secondary_hold_ms=int(data.get("secondary_hold_ms", DEFAULT_SECONDARY_HOLD_MS)),
            secondary_hold_enabled=bool(data.get("secondary_hold_enabled", DEFAULT_SECONDARY_HOLD_ENABLED)),
            stuck_key_timeout_ms=int(data.get("stuck_key_timeout_ms", DEFAULT_STUCK_KEY_TIMEOUT_MS)),
            provider=str(data.get("provider", DEFAULT_PROVIDER)),
            log_file=str(data.get("log_file", DEFAULT_LOG_FILE)),
            log_dir=str(data.get("log_dir", DEFAULT_LOG_DIR)),
            key_mappings=mappings,
        )


def default_config_path() -> str:
    """Return the default config path next to this file's config directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "config", "bridge_config.json")


def load_config(path: str | None = None) -> BridgeConfig:
    """Load configuration from a JSON file, falling back to defaults.

    Missing or unreadable config files produce the default configuration so the
    POC can run without any config file present.
    """
    config_path = path or os.environ.get(CONFIG_ENV_VAR) or default_config_path()
    if config_path and os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return BridgeConfig.from_dict(data)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            return BridgeConfig()
    return BridgeConfig()


def save_config(config: BridgeConfig, path: str) -> None:
    """Persist configuration to a JSON file (used for scaffolding only)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(config.to_dict(), fh, indent=2, sort_keys=True)
