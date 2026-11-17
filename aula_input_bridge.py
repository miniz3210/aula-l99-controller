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
import logging
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
from aula_bridge.companion_optin_config import load as load_companion_config, CompanionOptInConfigError
from aula_bridge.companion_button_mapping import load_companion_button_mapping, CompanionButtonMappingError
from aula_bridge.companion_http_transport import CompanionHttpTransportError
from aula_bridge.devices import (
    RAWINPUT,
    RAWINPUTDEVICE,
    RIDI_DEVICEINFO,
    RIDI_DEVICENAME,
    RIDEV_INPUTSINK,
    WM_INPUT,
    GetRawInputData,
    parse_vid_pid_from_path,
    user32,
    kernel32,
)

RIM_TYPEKEYBOARD = 1
RI_KEY_BREAK = 0x0001
RID_INPUT = 0x10000003
PM_REMOVE = 0x0001
CLASS_ALREADY_EXISTS = 1410

LOG_LEVEL_CHOICES = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LOG_LEVEL_DEFAULT = "WARNING"

logger = logging.getLogger(__name__)


def _dbg(*parts):
    print("RAWDBG:", *parts, file=sys.stderr, flush=True)

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


def configure_logging(level: str = LOG_LEVEL_DEFAULT) -> None:
    """Configure root logging once for the production entry point.

    Uses a concise stderr format with timestamp, level, logger name, and
    message. No file handler. Default WARNING preserves quiet production
    behavior.
    """
    logging.basicConfig(
        level=getattr(logging, level, logging.WARNING),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AULA L99 firmware-free Windows input bridge POC"
    )
    parser.add_argument("--config", help="Path to bridge config JSON")
    parser.add_argument(
        "--log-level",
        choices=LOG_LEVEL_CHOICES,
        default=LOG_LEVEL_DEFAULT,
        help="Set the logging level (default: WARNING)",
    )
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
    parser.add_argument(
        "--enable-companion",
        action="store_true",
        help="Enable Companion opt-in (requires --companion-config)",
    )
    parser.add_argument(
        "--companion-config",
        help="Path to Companion opt-in configuration JSON",
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
    _dbg("CAPTURE mode diagnostics start")

    hinstance = kernel32.GetModuleHandleW(None)
    _dbg("hinstance", hex(int(hinstance)))

    def wndproc(hwnd, msg, wparam, lparam):
        try:
            if msg == WM_INPUT:
                _dbg("CAPTURE wndproc WM_INPUT hDevice via lParam", hex(int(lparam)))
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except Exception as exc:
            _dbg("CAPTURE wndproc exception", repr(exc))
            raise

    wndproc_ptr = WNDPROC(wndproc)
    _dbg("wndproc_ptr strong ref held", repr(wndproc_ptr))

    wc = WNDCLASSW()
    wc.lpfnWndProc = wndproc_ptr
    wc.hInstance = hinstance
    wc.lpszMenuName = None
    wc.lpszClassName = "AulaRawCaptureWindow-%d" % os.getpid()
    ctypes.set_last_error(0)
    register_result = user32.RegisterClassW(ctypes.byref(wc))
    register_atom = register_result if register_result != 0 else 0
    register_last_error = ctypes.get_last_error()
    register_success = register_atom != 0
    _dbg("RegisterClassW result", register_atom, "GetLastError", register_last_error, "success", register_success)
    if not register_success:
        if register_last_error != CLASS_ALREADY_EXISTS:
            raise OSError("RegisterClassW failed with error %d" % register_last_error)

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
        hwnd_last_error = ctypes.get_last_error()
        _dbg("CreateWindowExW result hwnd", hex(int(hwnd)) if hwnd else None, "GetLastError", hwnd_last_error)
        if not hwnd:
            raise OSError("CreateWindowExW failed")

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = wintypes.USHORT(0x01)
        rid.usUsage = wintypes.USHORT(0x06)
        rid.dwFlags = wintypes.DWORD(RIDEV_INPUTSINK)
        rid.hwndTarget = hwnd
        _dbg("RAWINPUTDEVICE usage_page", hex(rid.usUsagePage), "usage", hex(rid.usUsage), "flags", hex(rid.dwFlags), "hwndTarget", hex(int(rid.hwndTarget)))

        rid_result = user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid))
        rid_last_error = ctypes.get_last_error()
        _dbg("RegisterRawInputDevices result", rid_result, "GetLastError", rid_last_error)
        if not rid_result:
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

        _dbg("CAPTURE entering message loop")
        while running:
            msg = wintypes.MSG()
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_INPUT:
                    _dbg("CAPTURE received WM_INPUT hDevice", hex(int(msg.lParam)) if msg.lParam else None)
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
                    _dbg("CAPTURE WM_INPUT hDevice", hex(int(h_device)) if h_device is not None else None)

                    path = device_path(h_device)

                    vid = None
                    pid = None
                    if path is not None:
                        parsed = parse_vid_pid_from_path(path)
                        if parsed is not None:
                            vid, pid = parsed

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
    only after successful provider emit. Dispatcher exceptions are caught,
    logged with exception(), and isolated from the Windows message loop.
    """
    provider.emit(event)
    if event.event in {"short_press", "hold", "secondary_hold"}:
        try:
            dispatcher.dispatch(event)
        except Exception:
            logger.exception(
                "Dispatch failed: event=%s key=%s device=%s seq=%d; isolated from message loop",
                event.event,
                event.key,
                event.device,
                event.seq,
            )


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
    _dbg("NORMAL process_raw_input entered")
    try:
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
            _dbg("NORMAL process_raw_input GetRawInputData returned -1")
            return

        if raw.header.dwType != RIM_TYPEKEYBOARD:
            _dbg("NORMAL process_raw_input non-keyboard dwType", raw.header.dwType)
            return

        h_device = raw.header.hDevice
        _dbg("NORMAL process_raw_input hDevice", hex(int(h_device)) if h_device is not None else None)

        name_len = wintypes.UINT(0)
        if (
            user32.GetRawInputDeviceInfoW(
                h_device, RIDI_DEVICENAME, None, ctypes.byref(name_len)
            )
            == -1
            or name_len.value == 0
        ):
            _dbg("NORMAL process_raw_input GetRawInputDeviceInfoW name_len failed")
            return
        name_buf = ctypes.create_unicode_buffer(name_len.value)
        if (
            user32.GetRawInputDeviceInfoW(
                h_device, RIDI_DEVICENAME, name_buf, ctypes.byref(name_len)
            )
            == -1
        ):
            _dbg("NORMAL process_raw_input GetRawInputDeviceInfoW name read failed")
            return

        _dbg("NORMAL process_raw_input device_name", name_buf.value)
        _dbg("NORMAL process_raw_input MI_00 match", "MI_00" in name_buf.value.upper())

        if "MI_00" not in name_buf.value.upper():
            _dbg("NORMAL process_raw_input not MI_00, skipping")
            return

        parsed = parse_vid_pid_from_path(name_buf.value)
        if parsed is None:
            _dbg("NORMAL process_raw_input parse_vid_pid_from_path failed")
            return
        vid, pid = parsed
        device = "%04X:%04X" % (vid, pid)
        _dbg("NORMAL process_raw_input device", device, "config vid/pid", config.vid, config.pid)

        if vid != config.vid or pid != config.pid:
            _dbg("NORMAL process_raw_input VID/PID mismatch, skipping")
            return

        vkey = raw.keyboard.VKey
        flags = raw.keyboard.Flags
        is_break = bool(flags & RI_KEY_BREAK)

        key = key_map.key_for_return_value(vkey)
        if key is None:
            key = key_map.key_for_make_code(raw.keyboard.MakeCode, flags, vkey)
        if key is None:
            _dbg("NORMAL process_raw_input no key mapping for vkey", hex(vkey), "make_code", hex(raw.keyboard.MakeCode))
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
    except Exception as exc:
        _dbg("NORMAL process_raw_input exception", repr(exc))
        raise


def build_companion_transport(companion_config, mapping_path: str):
    """Build Companion transport for the enabled path.

    Constructs CompanionHttpSender, CompanionHttpTransport, and
    CompanionDispatchAdapter, then wraps the adapter in a bounded
    CompanionDispatchWorker (queue capacity 8) so the Windows message-loop
    thread only performs non-blocking queue admission. The Worker, not the
    raw adapter, is injected into ActionDispatcher.
    """
    from aula_bridge.companion_http_transport import CompanionHttpTransport
    from aula_bridge.companion_http_sender import CompanionHttpSender
    from aula_bridge.companion_dispatch_adapter import CompanionDispatchAdapter
    from aula_bridge.companion_dispatch_worker import CompanionDispatchWorker

    button_mapping = load_companion_button_mapping(mapping_path)

    # Prepare transport configuration - do not construct real HTTP sender
    # This phase validates initialization and configuration only
    http_sender = CompanionHttpSender()
    http_transport = CompanionHttpTransport(
        http_sender=http_sender,
        host=companion_config.host,
        port=companion_config.port,
        timeout=companion_config.timeout,
    )
    dispatch_adapter = CompanionDispatchAdapter(
        http_transport=http_transport,
        button_mapping=button_mapping,
    )
    return CompanionDispatchWorker(
        transport=dispatch_adapter,
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    # Configure logging once before runtime components start.
    configure_logging(args.log_level)

    # Validate CLI flags
    if args.enable_companion and not args.companion_config:
        print("ERROR: --enable-companion requires --companion-config PATH")
        return 1
    if args.companion_config and not args.enable_companion:
        print("ERROR: --companion-config requires --enable-companion")
        return 1

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

    # Initialize Companion if enabled
    worker = None
    if args.enable_companion:
        try:
            companion_config = load_companion_config(args.companion_config)
        except CompanionOptInConfigError as e:
            print(f"ERROR: Invalid Companion config: {e}")
            return 1
        except CompanionButtonMappingError as e:
            print(f"ERROR: Invalid button mapping: {e}")
            return 1

        if not companion_config.enabled:
            print("ERROR: Companion config has enabled=false but --enable-companion was specified")
            return 1

        if companion_config.mapping_file is None:
            print("ERROR: Companion config requires mapping_file when enabled=true")
            return 1

        # Validate button mapping exists and is valid
        try:
            load_companion_button_mapping(companion_config.mapping_file)
        except CompanionButtonMappingError as e:
            print(f"ERROR: Invalid button mapping: {e}")
            return 1
        except OSError as e:
            print(f"ERROR: Cannot read button mapping file: {e}")
            return 1

        # Construct transport inside Worker wrapper; any construction error
        # fails fast and does not silently enable Companion.
        try:
            transport = build_companion_transport(companion_config, companion_config.mapping_file)
        except (CompanionOptInConfigError, CompanionButtonMappingError, OSError,
                  CompanionHttpTransportError) as e:
            print(f"ERROR: Failed to initialize Companion transport: {e}")
            return 1
        worker = transport
        print("Companion opt-in enabled. Transport configured.")
    else:
        transport = MockTransport()
        print("Companion disabled. Using MockTransport.")

    action_map = ActionMap()
    try:
        dispatcher = ActionDispatcher(transport=transport, action_map=action_map)
    except Exception as init_exc:
        if worker is not None:
            try:
                worker.close()
            except Exception as cleanup_exc:
                # Report both the original initialization failure and the
                # cleanup failure without hiding either.
                raise RuntimeError(
                    "Dispatcher initialization failed and Worker cleanup also failed: "
                    f"{init_exc!r}; cleanup: {cleanup_exc!r}"
                ) from init_exc
        raise

    # Register keyboard Raw Input on a hidden message-only window so the
    # normal Bridge path receives WM_INPUT (same as --capture-raw).
    _dbg("NORMAL mode diagnostics start")

    hinstance = kernel32.GetModuleHandleW(None)
    _dbg("NORMAL hinstance", hex(int(hinstance)))

    def wndproc(hwnd, msg, wparam, lparam):
        try:
            if msg == WM_INPUT:
                _dbg("NORMAL wndproc WM_INPUT hDevice via lParam", hex(int(lparam)) if lparam else None)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except Exception as exc:
            _dbg("NORMAL wndproc exception", repr(exc))
            raise

    wndproc_ptr = WNDPROC(wndproc)
    _dbg("NORMAL wndproc_ptr strong ref held", repr(wndproc_ptr))

    wc = WNDCLASSW()
    wc.lpfnWndProc = wndproc_ptr
    wc.hInstance = hinstance
    wc.lpszMenuName = None
    wc.lpszClassName = "AulaBridgeWindow-%d" % os.getpid()
    ctypes.set_last_error(0)
    register_result = user32.RegisterClassW(ctypes.byref(wc))
    register_atom = register_result if register_result != 0 else 0
    register_last_error = ctypes.get_last_error()
    register_success = register_atom != 0
    _dbg("NORMAL RegisterClassW result", register_atom, "GetLastError", register_last_error, "success", register_success)
    if not register_success:
        if register_last_error != CLASS_ALREADY_EXISTS:
            raise OSError("RegisterClassW failed with error %d" % register_last_error)

    hwnd = None
    class_registered_by_us = register_success
    try:
        hwnd = user32.CreateWindowExW(
            0,
            wc.lpszClassName,
            "AulaBridge",
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
        hwnd_last_error = ctypes.get_last_error()
        _dbg("NORMAL CreateWindowExW result hwnd", hex(int(hwnd)) if hwnd else None, "GetLastError", hwnd_last_error)
        if not hwnd:
            raise OSError("CreateWindowExW failed")

        rid = RAWINPUTDEVICE()
        rid.usUsagePage = wintypes.USHORT(0x01)
        rid.usUsage = wintypes.USHORT(0x06)
        rid.dwFlags = wintypes.DWORD(RIDEV_INPUTSINK)
        rid.hwndTarget = hwnd
        _dbg("NORMAL RAWINPUTDEVICE usage_page", hex(rid.usUsagePage), "usage", hex(rid.usUsage), "flags", hex(rid.dwFlags), "hwndTarget", hex(int(rid.hwndTarget)))

        rid_result = user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid))
        rid_last_error = ctypes.get_last_error()
        _dbg("NORMAL RegisterRawInputDevices result", rid_result, "GetLastError", rid_last_error)
        if not rid_result:
            raise OSError("RegisterRawInputDevices failed")

    except Exception:
        if hwnd is not None:
            try:
                user32.DestroyWindow(hwnd)
            except OSError:
                pass
        if class_registered_by_us:
            try:
                user32.UnregisterClassW(wc.lpszClassName, hinstance)
            except OSError:
                pass
        raise

    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    print("Bridge running. Provider=%s log=%s" % (config.provider, provider.path))
    print("Press Ctrl+C to stop.")

    try:
        _dbg("NORMAL entering message loop")
        while running:
            msg = wintypes.MSG()
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_INPUT:
                    _dbg("NORMAL received WM_INPUT hDevice", hex(int(msg.lParam)) if msg.lParam else None)
                    process_raw_input(msg, config, key_map, machine, provider, dispatcher)
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            now = int(time.time() * 1000)
            machine.set_time(now)
            for result in machine.tick(now):
                handle_result(provider, dispatcher, result)

            time.sleep(0.01)
    finally:
        # Shutdown: dispatcher.close() invokes Worker.close() (transport is the
        # Worker). Avoid duplicate Worker.close() calls. provider.close() runs
        # even if dispatcher.close() raises.
        dispatcher_close_error = None
        try:
            dispatcher.close()
        except Exception as exc:  # noqa: BLE001
            dispatcher_close_error = exc
        provider.close()
        if dispatcher_close_error is not None:
            raise dispatcher_close_error

        # Destroy the Raw Input message-only window and unregister the class.
        if hwnd is not None:
            try:
                user32.DestroyWindow(hwnd)
            except OSError:
                pass
        if class_registered_by_us:
            try:
                user32.UnregisterClassW(wc.lpszClassName, hinstance)
            except OSError:
                pass

        if worker is not None and worker.is_alive:
            # Worker.close() already reports if the worker remains alive after
            # the bounded join timeout. An in-flight HTTP request cannot be
            # forcibly cancelled; a full shutdown is not falsely claimed here.
            pass

    print("Bridge stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
