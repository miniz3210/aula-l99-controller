"""AULA L99 Windows input bridge POC entry point.

Firmware-free input-only bridge:
  1. Raw Input attributes keyboard events to VID 0C45 / PID 800A.
  2. Verified Mini Numpad return values map to 17 logical key IDs.
  3. Deterministic short/hold state machine per logical key.
  4. Dry-run provider writes deterministic structured JSON logs.

No Companion requests. No global keyboard suppression. No USB/HID/COM/screen
commands. No firmware modification or flashing.

Raw Input identifies the physical device but does not provide WH_KEYBOARD_LL
 style global suppression; the key is still delivered to other applications.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import json
import os
import signal
import sys
import time
from typing import Dict, Optional, Set

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge import (
    BridgeConfig,
    KeyEvent,
    KeyStateMachine,
    LogicalKeyMap,
    PressResult,
    RawInputDevice,
    find_target_device,
    is_target_device,
    load_config,
)
from aula_bridge.provider import DryRunProvider, ProviderEvent
from aula_bridge.dispatcher import ActionDispatcher, MockTransport
from aula_bridge.action_mapping import ActionMap
from aula_bridge.devices import (
    RAWINPUT,
    RAWINPUTDEVICE,
    RID_DEVICE_INFO,
    RIDI_DEVICEINFO,
    RIDI_DEVICENAME,
    RIDEV_INPUTSINK,
    WM_INPUT,
    GetRawInputData,
    user32,
    kernel32,
)

RIM_TYPEKEYBOARD = 1
RI_KEY_BREAK = 0x0001
RID_INPUT = 0x10000003
PM_REMOVE = 0x0001
CLASS_ALREADY_EXISTS = 1410

HWND_MESSAGE = wintypes.HWND(-3)

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)

class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


user32.RegisterRawInputDevices.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICE),
    wintypes.UINT,
    wintypes.UINT,
]
user32.RegisterRawInputDevices.restype = wintypes.BOOL

user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
user32.RegisterClassW.restype = wintypes.ATOM

user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
user32.UnregisterClassW.restype = wintypes.BOOL

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    ctypes.c_void_p,
]
user32.CreateWindowExW.restype = wintypes.HWND

user32.DestroyWindow.argtypes = [wintypes.HWND]
user32.DestroyWindow.restype = wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

user32.PeekMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
    wintypes.UINT,
]
user32.PeekMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_long

user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostQuitMessage.restype = None

kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AULA L99 firmware-free Windows input bridge POC"
    )
    parser.add_argument("--config", help="Path to bridge config JSON")
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="Enumerate Raw Input devices and exit",
    )
    parser.add_argument(
        "--capture-raw",
        action="store_true",
        help="Run raw Raw Input keyboard capture mode and exit",
    )
    return parser.parse_args(argv)


def list_devices() -> int:
    from aula_bridge.devices import enumerate_raw_input_devices

    devs = enumerate_raw_input_devices()
    print("Raw Input devices:")
    for d in devs:
        marker = " <-- TARGET" if d.matches(0x0C45, 0x800A) else ""
        print(
            "  %s  vid=%04X pid=%04X usage_page=%04X usage=%04X%s"
            % (d.device_name, d.vid, d.pid, d.usage_page, d.usage, marker)
        )
    return 0


def _process_raw_keyboard_event(
    raw: RAWINPUT,
    device_path: Optional[str],
    vid: Optional[int],
    pid: Optional[int],
    pressed_keys: Set[int],
) -> dict:
    """Decode one WM_INPUT keyboard RAWINPUT into a JSON-serializable dict."""
    kb = raw.keyboard
    flags = kb.Flags
    vkey = kb.VKey
    is_break = bool(flags & RI_KEY_BREAK)

    if not is_break:
        is_repeat = vkey in pressed_keys
        pressed_keys.add(vkey)
    else:
        is_repeat = False
        pressed_keys.discard(vkey)

    return {
        "timestamp": int(time.time() * 1000),
        "hDevice": int(raw.header.hDevice) if raw.header.hDevice is not None else None,
        "device_path": device_path,
        "vid": vid,
        "pid": pid,
        "make_code": kb.MakeCode,
        "flags": flags,
        "vkey": vkey,
        "message": kb.Message,
        "key_down": not is_break,
        "key_up": is_break,
        "is_repeat": is_repeat,
    }


def capture_raw() -> int:
    """Run manual Raw Input keyboard capture mode.

    Registers keyboard Raw Input (usage page 0x01, usage 0x06) with
    RIDEV_INPUTSINK on a hidden message window, then prints one concise JSON
    line per WM_INPUT keyboard event. No VID/PID filtering, no mapping, no
    state machine, no provider, no suppression. Raw observation only.
    """
    hinstance = kernel32.GetModuleHandleW(None)

    def wndproc(hwnd, msg, wparam, lparam):
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    wndproc_ptr = WNDPROC(wndproc)

    wc = WNDCLASSW()
    wc.lpfnWndProc = wndproc_ptr
    wc.hInstance = hinstance
    wc.lpszMenuName = None
    wc.lpszClassName = "AulaRawCaptureWindow-%d" % os.getpid()
    ctypes.set_last_error(0)
    register_success = user32.RegisterClassW(ctypes.byref(wc)) != 0
    if not register_success:
        last_error = ctypes.get_last_error()
        if last_error != CLASS_ALREADY_EXISTS:
            raise OSError("RegisterClassW failed with error %d" % last_error)

    hwnd = None
    class_registered_by_us = register_success
    try:

        hwnd = user32.CreateWindowExW(
            0,
            wc.lpszClassName,
            "AulaRawCapture",
            0,
            0,
            0,
            0,
            0,
            HWND_MESSAGE,
            None,
            hinstance,
            None,
        )
        if not hwnd:
            raise OSError("CreateWindowExW failed")

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = wintypes.USHORT(0x01)
        rid.usUsage = wintypes.USHORT(0x06)
        rid.dwFlags = wintypes.DWORD(RIDEV_INPUTSINK)
        rid.hwndTarget = hwnd

        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            raise OSError("RegisterRawInputDevices failed")

        device_cache: Dict[int, Optional[str]] = {}

        def device_path(h_device) -> Optional[str]:
            if h_device is None or int(h_device) == 0:
                return None
            handle = int(h_device)
            if handle in device_cache:
                return device_cache[handle]
            name_len = wintypes.UINT(0)
            if (
                user32.GetRawInputDeviceInfoW(
                    h_device, RIDI_DEVICENAME, None, ctypes.byref(name_len)
                )
                == -1
                or name_len.value == 0
            ):
                device_cache[handle] = None
                return None
            buf = ctypes.create_unicode_buffer(name_len.value)
            if (
                user32.GetRawInputDeviceInfoW(
                    h_device, RIDI_DEVICENAME, buf, ctypes.byref(name_len)
                )
                == -1
            ):
                device_cache[handle] = None
                return None
            device_cache[handle] = buf.value
            return buf.value

        print("Raw capture active. Press Ctrl+C to stop.")

        running = True
        pressed_keys: Set[int] = set()

        def handle_signal(signum, frame):
            nonlocal running
            running = False

        signal.signal(signal.SIGINT, handle_signal)

        while running:
            msg = wintypes.MSG()
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_INPUT:
                    data_size = wintypes.UINT(ctypes.sizeof(RAWINPUT))
                    raw = RAWINPUT()
                    if (
                        GetRawInputData(
                            ctypes.cast(msg.lParam, ctypes.c_void_p),
                            RID_INPUT,
                            ctypes.byref(raw),
                            ctypes.byref(data_size),
                            ctypes.sizeof(raw.header),
                        )
                        == -1
                    ):
                        continue

                    if raw.header.dwType != RIM_TYPEKEYBOARD:
                        continue

                    h_device = raw.header.hDevice
                    path = device_path(h_device)

                    vid = None
                    pid = None
                    if h_device is not None and int(h_device) != 0:
                        dev_info = RID_DEVICE_INFO()
                        dev_info.cbSize = ctypes.sizeof(RID_DEVICE_INFO)
                        cb_size = wintypes.UINT(ctypes.sizeof(RID_DEVICE_INFO))
                        if (
                            user32.GetRawInputDeviceInfoW(
                                h_device, RIDI_DEVICEINFO,
                                ctypes.byref(dev_info), ctypes.byref(cb_size),
                            )
                            != -1
                        ):
                            vid = dev_info.hid.dwVendorId
                            pid = dev_info.hid.dwProductId

                    entry = _process_raw_keyboard_event(raw, path, vid, pid, pressed_keys)
                    print(json.dumps(entry, separators=(",", ":"), sort_keys=False))

                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            time.sleep(0.01)
    finally:
        print("Raw capture stopped.")
        cleanup_error = None
        if hwnd is not None:
            try:
                user32.DestroyWindow(hwnd)
            except OSError as exc:
                cleanup_error = exc
        if class_registered_by_us:
            try:
                user32.UnregisterClassW(wc.lpszClassName, hinstance)
            except OSError as exc:
                if cleanup_error is not None:
                    raise
                raise
        if cleanup_error is not None:
            raise cleanup_error

    return 0


def build_machine(config: BridgeConfig) -> KeyStateMachine:
    return KeyStateMachine(
        short_threshold_ms=config.short_threshold_ms,
        hold_threshold_ms=config.hold_threshold_ms,
        secondary_hold_ms=config.secondary_hold_ms,
        secondary_hold_enabled=config.secondary_hold_enabled,
        stuck_key_timeout_ms=config.stuck_key_timeout_ms,
        now_ms=int(time.time() * 1000),
    )


def emit_key_down(provider: DryRunProvider, dispatcher: ActionDispatcher, key: str, device: str) -> None:
    emit_and_dispatch(provider, dispatcher, ProviderEvent(event="key_down", key=key, device=device))


def emit_short_press(provider: DryRunProvider, dispatcher: ActionDispatcher, key: str, device: str, duration_ms: int) -> None:
    emit_and_dispatch(
        provider,
        dispatcher,
        ProviderEvent(
            event="short_press", key=key, device=device, duration_ms=duration_ms
        )
    )


def emit_hold(provider: DryRunProvider, dispatcher: ActionDispatcher, key: str, device: str, duration_ms: int) -> None:
    emit_and_dispatch(provider, dispatcher, ProviderEvent(event="hold", key=key, device=device, duration_ms=duration_ms))


def emit_secondary_hold(provider: DryRunProvider, dispatcher: ActionDispatcher, key: str, device: str, duration_ms: int) -> None:
    emit_and_dispatch(
        provider,
        dispatcher,
        ProviderEvent(
            event="secondary_hold", key=key, device=device, duration_ms=duration_ms
        )
    )


def emit_repeat_ignored(provider: DryRunProvider, dispatcher: ActionDispatcher, key: str, device: str) -> None:
    emit_and_dispatch(provider, dispatcher, ProviderEvent(event="repeat_ignored", key=key, device=device))


def emit_key_up(provider: DryRunProvider, dispatcher: ActionDispatcher, key: str, device: str, held: bool) -> None:
    emit_and_dispatch(provider, dispatcher, ProviderEvent(event="key_up", key=key, device=device, held=held))


def emit_and_dispatch(
    provider: DryRunProvider,
    dispatcher: ActionDispatcher,
    event: ProviderEvent,
) -> None:
    """Emit event to provider first, then dispatch if supported.

    Provider emits first to preserve seq assignment. Dispatcher is called
    only after successful provider emit. Dispatcher exceptions are caught
    and isolated from the Windows message loop.
    """
    provider.emit(event)
    if event.event in {"short_press", "hold", "secondary_hold"}:
        try:
            dispatcher.dispatch(event)
        except Exception:
            pass


def handle_result(provider: DryRunProvider, dispatcher: ActionDispatcher, result: PressResult) -> None:
    device = result.device
    if result.action == "short_press":
        emit_short_press(provider, dispatcher, result.key, device, result.duration_ms or 0)
    elif result.action == "hold":
        emit_hold(provider, dispatcher, result.key, device, result.duration_ms or 0)
    elif result.action == "secondary_hold":
        emit_secondary_hold(provider, dispatcher, result.key, device, result.duration_ms or 0)
    elif result.action == "repeat_ignored":
        emit_repeat_ignored(provider, dispatcher, result.key, device)
    # ACTION_NONE emits nothing (dead-zone / suppressed ups are silent).


def process_raw_input(
    msg: wintypes.MSG,
    config: BridgeConfig,
    key_map: LogicalKeyMap,
    machine: KeyStateMachine,
    provider: DryRunProvider,
    dispatcher: ActionDispatcher,
) -> None:
    """Handle one WM_INPUT message: attribute, map, drive state machine."""
    data_size = wintypes.UINT(ctypes.sizeof(RAWINPUT))
    raw = RAWINPUT()
    if (
        GetRawInputData(
            ctypes.cast(msg.lParam, ctypes.c_void_p),
            RID_INPUT,
            ctypes.byref(raw),
            ctypes.byref(data_size),
            ctypes.sizeof(raw.header),
        )
        == -1
    ):
        return

    if raw.header.dwType != RIM_TYPEKEYBOARD:
        return

    h_device = raw.header.hDevice
    dev_info = RID_DEVICE_INFO()
    dev_info.cbSize = ctypes.sizeof(RID_DEVICE_INFO)
    cb_size = wintypes.UINT(ctypes.sizeof(RID_DEVICE_INFO))
    if (
        user32.GetRawInputDeviceInfoW(
            h_device, RIDI_DEVICEINFO, ctypes.byref(dev_info), ctypes.byref(cb_size)
        )
        == -1
    ):
        return

    vid = dev_info.hid.dwVendorId
    pid = dev_info.hid.dwProductId
    device = "%04X:%04X" % (vid, pid)

    if vid != config.vid or pid != config.pid:
        return

    vkey = raw.keyboard.VKey
    flags = raw.keyboard.Flags
    is_break = bool(flags & RI_KEY_BREAK)

    key = key_map.key_for_return_value(vkey)
    if key is None:
        return

    now = int(time.time() * 1000)
    machine.set_time(now)

    if is_break:
        for result in machine.key_up(key, device, now):
            if result.action == "short_press":
                emit_short_press(provider, dispatcher, key, device, result.duration_ms or 0)
            elif result.action == "hold":
                emit_key_up(provider, dispatcher, key, device, held=True)
            elif result.action == "repeat_ignored":
                emit_repeat_ignored(provider, dispatcher, key, device)
    else:
        emit_key_down(provider, dispatcher, key, device)
        for result in machine.key_down(key, device, now):
            if result.action == "repeat_ignored":
                emit_repeat_ignored(provider, dispatcher, key, device)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)

    if args.list_devices:
        return list_devices()

    if args.capture_raw:
        return capture_raw()

    target = find_target_device(config.vid, config.pid)
    if target is None:
        print(
            "WARNING: target Raw Input device %04X:%04X not found. "
            "Bridge runs but attributes no events." % (config.vid, config.pid)
        )
    else:
        print("Target device found: %s (%s)" % (target.device_name, target.vid_pid))

    key_map = LogicalKeyMap()
    machine = build_machine(config)
    provider = DryRunProvider(log_file=config.log_file, log_dir=config.log_dir)
    transport = MockTransport()
    action_map = ActionMap()
    dispatcher = ActionDispatcher(transport=transport, action_map=action_map)

    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("Bridge running. Provider=%s log=%s" % (config.provider, provider.path))
    print("Press Ctrl+C to stop.")

    while running:
        msg = wintypes.MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            if msg.message == WM_INPUT:
                process_raw_input(msg, config, key_map, machine, provider, dispatcher)
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        now = int(time.time() * 1000)
        machine.set_time(now)
        for result in machine.tick(now):
            handle_result(provider, dispatcher, result)

        time.sleep(0.01)

    dispatcher.close()
    provider.close()
    print("Bridge stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
