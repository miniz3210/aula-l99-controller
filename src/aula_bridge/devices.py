"""Raw Input device attribution for the AULA L99 Windows input bridge POC.

Uses the Windows Raw Input API (RegisterRawInputDevices / GetRawInputData) to
attribute keyboard events to a specific physical HID device by VID/PID.
Identification is read-only: the device is observed, not opened or suppressed.

IMPORTANT LIMITATION: Raw Input identifies the physical device that produced an
input event but does not provide WH_KEYBOARD_LL-style global suppression. The
bridge cannot block the key from reaching other applications. Device attribution
and global key suppression are separate concerns and are NOT combined in this
POC.

L99 wired identity: VID 0x0C45 / PID 0x800A on MI_00. The L99 physical
keyboard and screen Numpad share MI_00 and are distinguishable only by key
codes (make code + E0/flags), not by Raw Input device handle.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import List, Optional
import re

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Raw Input flags.
RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00000010
RIDEV_CAPTUREMOUSE = 0x00000200
RIDEV_NOLEGACY = 0x00000030

# Raw Input data types.
RIM_TYPEKEYBOARD = 1
RIM_TYPEMOUSE = 0
RIM_TYPEHID = 2

# Raw Input header flags.
RI_KEY_MAKE = 0
RI_KEY_BREAK = 1
RI_KEY_E0 = 2
RI_KEY_E1 = 4

# WM_INPUT message.
WM_INPUT = 0x00FF

# GetRawInputData return codes.
RID_HEADER = 0x10000005
RID_INPUT = 0x10000003

# GetRawInputDeviceInfo commands.
RIDI_DEVICEINFO = 0x2000000B
RIDI_DEVICENAME = 0x20000007

# HID usage page / usage for keyboard devices.
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_KEYBOARD = 0x06

# Verified L99 wired identity.
L99_VID = 0x0C45
L99_PID = 0x800A

# VID_XXXX&PID_XXXX substring inside a Raw Input device path.
VID_PID_PATH_RE = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")


def parse_vid_pid_from_path(device_path: str) -> Optional[tuple[int, int]]:
    """Extract VID and PID from a Raw Input device path such as
    HID#VID_0C45&PID_800A&MI_00.

    Returns (vid, pid) as integers, or None when no VID/PID substring is found.
    """
    m = VID_PID_PATH_RE.search(device_path)
    if not m:
        return None
    return int(m.group(1), 16), int(m.group(2), 16)


def is_l99_path(device_path: str) -> bool:
    """Return True when a Raw Input device path matches the L99 wired identity
    VID 0x0C45 / PID 0x800A on MI_00.

    The L99 physical keyboard and screen Numpad share MI_00, so any MI_00 path
    with VID 0x0C45 / PID 0x800A is accepted. Distinguishing physical keys from
    screen Numpad requires key codes (make code + E0/flags), not the device
    handle or path.
    """
    parsed = parse_vid_pid_from_path(device_path)
    if parsed is None:
        return False
    vid, pid = parsed
    return vid == L99_VID and pid == L99_PID and "MI_00" in device_path.upper()


def is_l99_vid_pid(vid: int, pid: int) -> bool:
    """Return True when VID/PID matches the L99 wired identity."""
    return vid == L99_VID and pid == L99_PID


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [
        ("hDevice", wintypes.HANDLE),
        ("dwType", wintypes.DWORD),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("keyboard", RAWKEYBOARD),
    ]


class RID_DEVICE_INFO_HID(ctypes.Structure):
    _fields_ = [
        ("dwVendorId", wintypes.DWORD),
        ("dwProductId", wintypes.DWORD),
        ("dwVersionNumber", wintypes.DWORD),
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
    ]


class RID_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("hid", RID_DEVICE_INFO_HID),
        ("_reserved", wintypes.ULONG * 2),
    ]


# Configure Windows API function signatures.
user32.GetRawInputDeviceList.argtypes = [
    ctypes.POINTER(RAWINPUTDEVICELIST),
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT,
]
user32.GetRawInputDeviceList.restype = wintypes.INT

user32.GetRawInputDeviceInfoW.argtypes = [
    wintypes.HANDLE,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.UINT),
]
user32.GetRawInputDeviceInfoW.restype = wintypes.INT

user32.GetRawInputData.argtypes = [
    ctypes.c_void_p,
    wintypes.UINT,
    ctypes.c_void_p,
    ctypes.POINTER(wintypes.UINT),
    wintypes.UINT,
]
user32.GetRawInputData.restype = wintypes.INT

GetRawInputData = user32.GetRawInputData


@dataclass
class RawInputDevice:
    """A Raw Input-attributed HID device."""

    device_name: str
    vid: int
    pid: int
    usage_page: int
    usage: int
    handle: int

    @property
    def vid_pid(self) -> str:
        return "%04X:%04X" % (self.vid, self.pid)

    def matches(self, vid: int, pid: int) -> bool:
        return self.vid == vid and self.pid == pid


def _get_raw_input_device_info_list() -> List[RawInputDevice]:
    """Enumerate Raw Input devices and return those with VID/PID info."""
    devices: List[RawInputDevice] = []
    p_num_devices = wintypes.UINT()

    if user32.GetRawInputDeviceList(
        None, ctypes.byref(p_num_devices), ctypes.sizeof(RAWINPUTDEVICELIST)
    ) == -1:
        return devices

    if p_num_devices.value == 0:
        return devices

    rid_list = (RAWINPUTDEVICELIST * p_num_devices.value)()
    if user32.GetRawInputDeviceList(
        rid_list, ctypes.byref(p_num_devices), ctypes.sizeof(RAWINPUTDEVICELIST)
    ) == -1:
        return devices

    for i in range(p_num_devices.value):
        h_device = rid_list[i].hDevice
        dev_type = rid_list[i].dwType
        if dev_type != RIM_TYPEKEYBOARD:
            continue

        cb_size = wintypes.UINT(ctypes.sizeof(RID_DEVICE_INFO))
        rid = RID_DEVICE_INFO()
        rid.cbSize = ctypes.sizeof(RID_DEVICE_INFO)

        result = user32.GetRawInputDeviceInfoW(
            h_device,
            RIDI_DEVICEINFO,
            ctypes.byref(rid),
            ctypes.byref(cb_size),
        )
        if result == -1:
            continue

        # Get device name length (in characters for W version).
        name_len = wintypes.UINT(0)
        user32.GetRawInputDeviceInfoW(
            h_device, RIDI_DEVICENAME, None, ctypes.byref(name_len)
        )
        if name_len.value == 0:
            continue
        name_buf = ctypes.create_unicode_buffer(name_len.value)
        user32.GetRawInputDeviceInfoW(
            h_device, RIDI_DEVICENAME, name_buf, ctypes.byref(name_len)
        )

        vid = rid.hid.dwVendorId
        pid = rid.hid.dwProductId

        devices.append(
            RawInputDevice(
                device_name=name_buf.value,
                vid=vid,
                pid=pid,
                usage_page=rid.hid.usUsagePage,
                usage=rid.hid.usUsage,
                handle=int(h_device),
            )
        )
    return devices


def enumerate_raw_input_devices() -> List[RawInputDevice]:
    """Return all Raw Input devices with VID/PID information."""
    return _get_raw_input_device_info_list()


def find_target_device(vid: int, pid: int) -> Optional[RawInputDevice]:
    """Find the first Raw Input device matching the given VID/PID.

    Returns None when no matching device is present (device not plugged in or
    not in wired HID mode). Callers must treat None as "not available" rather
    than as a fatal error, because the bridge should still run and surface the
    absence in logs.
    """
    for dev in enumerate_raw_input_devices():
        if dev.matches(vid, pid):
            return dev
    return None


def is_target_device(device: Optional[RawInputDevice], vid: int, pid: int) -> bool:
    """Return True when device is not None and matches the target VID/PID."""
    return device is not None and device.matches(vid, pid)
