"""Immutable action mapping for the AULA L99 offline dispatcher.

Maps (logical_key, event_type) to (command, payload) deterministically.
No network transport, no I/O, no mutation of ProviderEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ActionMapEntry:
    """Immutable mapping from logical key + event type to command + payload."""

    logical_key: str
    event_type: str
    command: str
    payload: str


# Supported action event types
SUPPORTED_EVENT_TYPES = frozenset({
    "short_press",
    "hold",
    "secondary_hold",
})

# Default action map: maps (logical_key, event_type) -> (command, payload)
# These are deterministic defaults; can be overridden by configuration.
DEFAULT_ACTION_MAP: Dict[Tuple[str, str], Tuple[str, str]] = {}

# Generate default mappings for all 17 numpad keys
NUM_PAD_KEYS = [
    "numpad_num",
    "numpad_divide",
    "numpad_multiply",
    "numpad_minus",
    "numpad_7",
    "numpad_8",
    "numpad_9",
    "numpad_plus",
    "numpad_4",
    "numpad_5",
    "numpad_6",
    "numpad_1",
    "numpad_2",
    "numpad_3",
    "numpad_enter",
    "numpad_0",
    "numpad_decimal_delete",
]

for key in NUM_PAD_KEYS:
    DEFAULT_ACTION_MAP[(key, "short_press")] = (f"{key}_press", "")
    DEFAULT_ACTION_MAP[(key, "hold")] = (f"{key}_hold", "")
    DEFAULT_ACTION_MAP[(key, "secondary_hold")] = (f"{key}_secondary_hold", "")


class ActionMap:
    """Immutable action map for deterministic offline dispatch."""

    # Class-level defaults for test access
    DEFAULT_ACTION_MAP = DEFAULT_ACTION_MAP
    NUM_PAD_KEYS = NUM_PAD_KEYS

    def __init__(self, mapping: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None) -> None:
        """Initialize with optional custom mapping.

        Args:
            mapping: Custom (logical_key, event_type) -> (command, payload) map.
                     If provided, merges with DEFAULT_ACTION_MAP (custom overrides defaults).
        """
        self._mapping: Dict[Tuple[str, str], Tuple[str, str]] = dict(DEFAULT_ACTION_MAP)
        if mapping is not None:
            self._mapping.update(mapping)

    def lookup(self, logical_key: str, event_type: str) -> Optional[ActionMapEntry]:
        """Look up action mapping for a logical key and event type.

        Returns:
            ActionMapEntry if mapped, None if unknown key or unsupported event type.
        """
        if event_type not in SUPPORTED_EVENT_TYPES:
            return None

        cmd_payload = self._mapping.get((logical_key, event_type))
        if cmd_payload is None:
            return None

        return ActionMapEntry(
            logical_key=logical_key,
            event_type=event_type,
            command=cmd_payload[0],
            payload=cmd_payload[1],
        )

    def has_mapping(self, logical_key: str, event_type: str) -> bool:
        """Check if a mapping exists for the given key and event type."""
        return self.lookup(logical_key, event_type) is not None

    def all_mappings(self) -> Tuple[ActionMapEntry, ...]:
        """Return all mappings as an immutable tuple for deterministic ordering."""
        entries = []
        for (key, event_type), (cmd, payload) in sorted(self._mapping.items()):
            entries.append(
                ActionMapEntry(
                    logical_key=key,
                    event_type=event_type,
                    command=cmd,
                    payload=payload,
                )
            )
        return tuple(entries)