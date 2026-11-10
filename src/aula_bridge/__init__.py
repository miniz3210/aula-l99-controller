"""AULA L99 Windows input bridge package.

Firmware-free POC: Raw Input device-aware keyboard attribution, deterministic
short/hold state machine, logical key mapping, and a provider-agnostic dry-run
output provider. No Companion integration, no USB/HID/COM writes, no flashing.
"""

from .config import BridgeConfig, load_config
from .devices import RawInputDevice, find_target_device, enumerate_raw_input_devices, is_target_device
from .keymap import LogicalKeyMap, RETURN_VALUE_TO_KEY
from .state_machine import KeyStateMachine, KeyEvent, PressResult
from .provider import DryRunProvider

__all__ = [
    "BridgeConfig",
    "load_config",
    "RawInputDevice",
    "find_target_device",
    "enumerate_raw_input_devices",
    "is_target_device",
    "LogicalKeyMap",
    "RETURN_VALUE_TO_KEY",
    "KeyStateMachine",
    "KeyEvent",
    "PressResult",
    "DryRunProvider",
]
