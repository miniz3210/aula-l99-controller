"""Logical key mapping for the AULA L99 Mini Numpad.

Maps verified input sources to 17 logical key IDs. The mapping is
provider-agnostic: it produces logical key names that any output provider can
consume.

Two input sources are supported:

1. L99 physical keyboard (MI_00): verified return values 0x0030-0x0040 map to
   the 16 action keys. HOME (0x0020) is screen-internal navigation and emits no
   Windows input event, so it is NOT in the Windows logical-key map.

2. Screen Numpad (MI_00, shared with the physical keyboard): mapped by make_code
   plus relevant E0/flags, NOT by VKey. Num Lock ON/OFF changes VKey but not
   make_code, so both Num Lock states produce the same logical key. The physical
   keyboard and screen Numpad share MI_00 and are distinguishable only by key
   codes, not by Raw Input device handle.

See docs/PROJECT_HANDOVER.md section 8 (Page 21 Mini Numpad) for the verified
return codes and button layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

# Verified L99 physical keyboard return values -> logical key IDs.
# 16 action keys (0x0030-0x0040). HOME 0x0020 intentionally omitted.
RETURN_VALUE_TO_KEY: Dict[int, str] = {
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

KEY_TO_RETURN_VALUE = {v: k for k, v in RETURN_VALUE_TO_KEY.items()}

# Screen Numpad make_code -> logical key ID. Mapped by make_code (+E0/flags),
# not VKey, so Num Lock ON/OFF yields the same logical key.
# Verified live capture: NumPad 1 make_code=79, NumPad 2 make_code=80.
SCREEN_MAKE_CODE_TO_KEY: Dict[int, str] = {
    79: "numpad_1",
    80: "numpad_2",
}

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


@dataclass
class LogicalKeyMap:
    """Bidirectional mapping between return values / make codes and logical key IDs."""

    return_value_to_key: Dict[int, str] = field(default_factory=lambda: dict(RETURN_VALUE_TO_KEY))
    key_to_return_value: Dict[str, int] = field(default_factory=lambda: dict(KEY_TO_RETURN_VALUE))
    screen_make_code_to_key: Dict[int, str] = field(default_factory=lambda: dict(SCREEN_MAKE_CODE_TO_KEY))

    def key_for_return_value(self, return_value: int) -> Optional[str]:
        """Map an L99 physical keyboard return value to a logical key."""
        return self.return_value_to_key.get(return_value)

    def return_value_for_key(self, key: str) -> Optional[int]:
        return self.key_to_return_value.get(key)

    def key_for_make_code(self, make_code: int, flags: int = 0, vkey: Optional[int] = None) -> Optional[str]:
        """Map a screen Numpad event by make_code (+E0/flags), ignoring VKey.

        VKey is accepted for interface completeness but deliberately ignored so
        that Num Lock ON (VKey 97/98) and Num Lock OFF (VKey 35/40) produce the
        same logical key for the same make_code.
        """
        del flags, vkey  # intentionally unused: make_code is the identity
        return self.screen_make_code_to_key.get(make_code)

    def is_numpad_key(self, key: str) -> bool:
        return key in NUM_PAD_KEYS

    def all_keys(self) -> list[str]:
        return list(self.return_value_to_key.values())
