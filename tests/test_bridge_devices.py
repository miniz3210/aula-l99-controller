#!/usr/bin/env python3
"""Mocked unit tests for Raw Input device enumeration and capture raw mode.

No connected hardware is required. Windows Raw Input API calls are mocked.
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import sys
import unittest
from typing import Set
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import aula_bridge
from aula_bridge import devices
from aula_bridge.devices import (
    RIDI_DEVICEINFO,
    RIDI_DEVICENAME,
    RIM_TYPEKEYBOARD,
    RIM_TYPEMOUSE,
    RID_DEVICE_INFO,
    RAWINPUT,
    RAWINPUTDEVICELIST,
    RAWKEYBOARD,
    RAWINPUTHEADER,
    GetRawInputData,
)

CLASS_ALREADY_EXISTS = 1410


def _set_ptr_value(arg, value):
    """Set the pointed-to value on a ctypes pointer arg (may be CArgObject)."""
    ptr = ctypes.cast(arg, ctypes.POINTER(wintypes.UINT))
    ptr.contents.value = value


def _set_rid_from_ptr(arg, vid, pid):
    rid = ctypes.cast(arg, ctypes.POINTER(RID_DEVICE_INFO)).contents
    rid.cbSize = ctypes.sizeof(RID_DEVICE_INFO)
    rid.dwType = RIM_TYPEKEYBOARD
    rid.hid.dwVendorId = vid
    rid.hid.dwProductId = pid
    rid.hid.usUsagePage = 0x01
    rid.hid.usUsage = 0x06


class PackageExportsTests(unittest.TestCase):
    def test_aula_bridge_exports_required_symbols(self):
        for name in (
            "is_target_device",
            "find_target_device",
            "enumerate_raw_input_devices",
            "RawInputDevice",
        ):
            self.assertTrue(hasattr(aula_bridge, name), name)

    def test_devices_exports_get_raw_input_data(self):
        self.assertTrue(callable(GetRawInputData))


class DeviceListStructureTests(unittest.TestCase):
    def test_raw_input_device_list_fields(self):
        fields = dict(RAWINPUTDEVICELIST._fields_)
        self.assertIn("hDevice", fields)
        self.assertIn("dwType", fields)
        self.assertEqual(fields["hDevice"], wintypes.HANDLE)
        self.assertEqual(fields["dwType"], wintypes.DWORD)

    def test_rid_device_info_fields(self):
        fields = dict(RID_DEVICE_INFO._fields_)
        self.assertIn("cbSize", fields)
        self.assertIn("dwType", fields)
        self.assertIn("hid", fields)

    def test_ridi_constants_match_windows_sdk(self):
        self.assertEqual(devices.RIDI_DEVICEINFO, 0x2000000B)
        self.assertEqual(devices.RIDI_DEVICENAME, 0x20000007)

    def test_rid_device_info_size_is_thirty_two_bytes(self):
        self.assertEqual(ctypes.sizeof(RID_DEVICE_INFO), 32)


class EnumerationTests(unittest.TestCase):
    def _setup_success_mock(self, vid=0x0C45, pid=0x800A, name="\\\\?\\HID#VID_0C45&PID_800A"):
        def device_list_side_effect(p_list, p_num_devices, size):
            _set_ptr_value(p_num_devices, 1)
            if p_list is not None:
                p_list[0].hDevice = wintypes.HANDLE(1234)
                p_list[0].dwType = RIM_TYPEKEYBOARD
            return 1

        def device_info_side_effect(h_device, ui_command, p_data, pcb_size):
            if ui_command == RIDI_DEVICEINFO:
                _set_rid_from_ptr(p_data, vid, pid)
                _set_ptr_value(pcb_size, ctypes.sizeof(RID_DEVICE_INFO))
                return 0
            if ui_command == RIDI_DEVICENAME:
                if p_data is None:
                    _set_ptr_value(pcb_size, len(name))
                    return len(name)
                buf = ctypes.cast(
                    p_data, ctypes.POINTER(wintypes.WCHAR * (len(name) + 1))
                ).contents
                buf.value = name
                _set_ptr_value(pcb_size, len(name))
                return len(name)
            return -1

        self._mock_list = mock.patch.object(
            devices.user32,
            "GetRawInputDeviceList",
            side_effect=device_list_side_effect,
        )
        self._mock_info = mock.patch.object(
            devices.user32,
            "GetRawInputDeviceInfoW",
            side_effect=device_info_side_effect,
        )
        self._mock_list.start()
        self._mock_info.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_successful_enumeration_of_one_keyboard_device(self):
        self._setup_success_mock()
        devs = devices.enumerate_raw_input_devices()
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].vid, 0x0C45)
        self.assertEqual(devs[0].pid, 0x800A)

    def test_vid_pid_extraction_from_ridi_deviceinfo(self):
        self._setup_success_mock(vid=0x0C45, pid=0x800A)
        devs = devices.enumerate_raw_input_devices()
        self.assertEqual(devs[0].vid_pid, "0C45:800A")

    def test_non_keyboard_entries_ignored(self):
        def device_list_side_effect(p_list, p_num_devices, size):
            _set_ptr_value(p_num_devices, 2)
            if p_list is not None:
                p_list[0].hDevice = wintypes.HANDLE(1)
                p_list[0].dwType = RIM_TYPEMOUSE
                p_list[1].hDevice = wintypes.HANDLE(2)
                p_list[1].dwType = RIM_TYPEKEYBOARD
            return 2

        def device_info_side_effect(h_device, ui_command, p_data, pcb_size):
            if ui_command == RIDI_DEVICEINFO:
                _set_rid_from_ptr(p_data, 0x0C45, 0x800A)
                _set_ptr_value(pcb_size, ctypes.sizeof(RID_DEVICE_INFO))
                return 0
            if ui_command == RIDI_DEVICENAME:
                name = "kbd1"
                if p_data is None:
                    _set_ptr_value(pcb_size, len(name))
                    return len(name)
                buf = ctypes.cast(
                    p_data, ctypes.POINTER(wintypes.WCHAR * (len(name) + 1))
                ).contents
                buf.value = name
                _set_ptr_value(pcb_size, len(name))
                return len(name)
            return -1

        mock_list = mock.patch.object(
            devices.user32,
            "GetRawInputDeviceList",
            side_effect=device_list_side_effect,
        )
        mock_info = mock.patch.object(
            devices.user32,
            "GetRawInputDeviceInfoW",
            side_effect=device_info_side_effect,
        )
        mock_list.start()
        mock_info.start()
        self.addCleanup(mock.patch.stopall)

        devs = devices.enumerate_raw_input_devices()
        self.assertEqual(len(devs), 1)
        self.assertEqual(devs[0].handle, 2)

    def test_target_vid_pid_match(self):
        self._setup_success_mock(vid=0x0C45, pid=0x800A)
        dev = devices.find_target_device(0x0C45, 0x800A)
        self.assertIsNotNone(dev)
        self.assertTrue(dev.matches(0x0C45, 0x800A))
        self.assertTrue(aula_bridge.is_target_device(dev, 0x0C45, 0x800A))

    def test_non_target_vid_pid_rejection(self):
        self._setup_success_mock(vid=0x0C45, pid=0x800A)
        self.assertIsNone(devices.find_target_device(0x1234, 0x5678))
        self.assertFalse(aula_bridge.is_target_device(None, 0x0C45, 0x800A))

    def test_get_raw_input_device_info_w_failure_skips_not_crash(self):
        def device_list_side_effect(p_list, p_num_devices, size):
            _set_ptr_value(p_num_devices, 1)
            if p_list is not None:
                p_list[0].hDevice = wintypes.HANDLE(999)
                p_list[0].dwType = RIM_TYPEKEYBOARD
            return 1

        def device_info_failure(h_device, ui_command, p_data, pcb_size):
            return -1

        mock_list = mock.patch.object(
            devices.user32,
            "GetRawInputDeviceList",
            side_effect=device_list_side_effect,
        )
        mock_info = mock.patch.object(
            devices.user32,
            "GetRawInputDeviceInfoW",
            side_effect=device_info_failure,
        )
        mock_list.start()
        mock_info.start()
        self.addCleanup(mock.patch.stopall)

        devs = devices.enumerate_raw_input_devices()
        self.assertEqual(len(devs), 0)


class CaptureRawTests(unittest.TestCase):
    """Mocked tests for capture_raw event formatting and device-path caching."""

    def setUp(self):
        import aula_input_bridge
        self.bridge = aula_input_bridge
        self.pressed_keys: Set[int] = set()

    def _make_raw(self, h_device_value, vkey, flags, make_code, message):
        kb = RAWKEYBOARD(
            MakeCode=wintypes.USHORT(make_code),
            Flags=wintypes.USHORT(flags),
            Reserved=wintypes.USHORT(0),
            VKey=wintypes.USHORT(vkey),
            Message=wintypes.UINT(message),
            ExtraInformation=wintypes.ULONG(0),
        )
        header = RAWINPUTHEADER(
            dwType=wintypes.DWORD(RIM_TYPEKEYBOARD),
            dwSize=wintypes.DWORD(ctypes.sizeof(RAWINPUT)),
            hDevice=wintypes.HANDLE(h_device_value),
            wParam=wintypes.WPARAM(0),
        )
        return RAWINPUT(header=header, keyboard=kb)

    def _process(self, raw, h_device_value, vid=None, pid=None, path="/kbd/path"):
        return self.bridge._process_raw_keyboard_event(raw, path, vid, pid, self.pressed_keys)

    def test_non_null_hdevice_event_formatting(self):
        self.pressed_keys = set()
        raw = self._make_raw(1234, 0x31, 0x0000, 0x02, 0x0100)
        entry = self._process(raw, 1234, vid=0x0C45, pid=0x800A)
        self.assertEqual(entry["hDevice"], 1234)
        self.assertEqual(entry["vid"], 0x0C45)
        self.assertEqual(entry["pid"], 0x800A)
        self.assertEqual(entry["vkey"], 0x31)
        self.assertEqual(entry["make_code"], 0x02)
        self.assertEqual(entry["flags"], 0x0000)
        self.assertEqual(entry["message"], 0x0100)
        self.assertTrue(entry["key_down"])
        self.assertFalse(entry["key_up"])
        self.assertFalse(entry["is_repeat"])
        self.assertIsInstance(entry["timestamp"], int)
        self.assertEqual(entry["device_path"], "/kbd/path")

    def test_null_hdevice_event_formatting(self):
        self.pressed_keys = set()
        raw = self._make_raw(0, 0x31, 0x0000, 0x02, 0x0100)
        entry = self._process(raw, 0, vid=None, pid=None, path=None)
        self.assertIsNone(entry["hDevice"])
        self.assertIsNone(entry["device_path"])
        self.assertIsNone(entry["vid"])
        self.assertIsNone(entry["pid"])
        self.assertEqual(entry["vkey"], 0x31)
        self.assertTrue(entry["key_down"])

    def test_device_path_caching(self):
        # Caching is exercised inside capture_raw; here we assert path pass-through.
        self.pressed_keys = set()
        raw = self._make_raw(4321, 0x32, 0x0000, 0x03, 0x0100)
        entry1 = self._process(raw, 4321, path="/kbd1")
        entry2 = self._process(raw, 4321, path="/kbd1")
        self.assertEqual(entry1["device_path"], "/kbd1")
        self.assertEqual(entry2["device_path"], "/kbd1")

    def test_key_down_decoding(self):
        self.pressed_keys = set()
        raw = self._make_raw(100, 0x41, 0x0000, 0x04, 0x0100)
        entry = self._process(raw, 100)
        self.assertTrue(entry["key_down"])
        self.assertFalse(entry["key_up"])
        self.assertFalse(entry["is_repeat"])

    def test_key_up_decoding(self):
        self.pressed_keys = set()
        raw = self._make_raw(100, 0x41, 0x0001, 0x04, 0x0101)
        entry = self._process(raw, 100)
        self.assertFalse(entry["key_down"])
        self.assertTrue(entry["key_up"])
        self.assertFalse(entry["is_repeat"])

    def test_repeat_detection(self):
        self.pressed_keys = set()
        raw1 = self._make_raw(100, 0x41, 0x0000, 0x04, 0x0100)
        raw2 = self._make_raw(100, 0x41, 0x0000, 0x04, 0x0100)
        e1 = self._process(raw1, 100)
        self.assertFalse(e1["is_repeat"])
        e2 = self._process(raw2, 100)
        self.assertTrue(e2["is_repeat"])

    def test_no_vid_pid_filtering(self):
        self.pressed_keys = set()
        raw = self._make_raw(1234, 0x31, 0x0000, 0x02, 0x0100)
        entry = self._process(raw, 1234, vid=0x1234, pid=0x5678)
        self.assertEqual(entry["vid"], 0x1234)
        self.assertEqual(entry["pid"], 0x5678)


    def test_wndclassw_abi(self):
        import aula_input_bridge
        wc = aula_input_bridge.WNDCLASSW()
        self.assertEqual(ctypes.sizeof(wc), 72)
        
        # Verify field order and basic types
        fields = aula_input_bridge.WNDCLASSW._fields_
        self.assertEqual(fields[0][0], "style")
        self.assertEqual(fields[1][0], "lpfnWndProc")
        self.assertEqual(fields[2][0], "cbClsExtra")
        self.assertEqual(fields[3][0], "cbWndExtra")
        self.assertEqual(fields[4][0], "hInstance")
        self.assertEqual(fields[9][0], "lpszClassName")


    def setUp(self):
        self.addCleanup(mock.patch.stopall)
        import aula_input_bridge
        self.bridge = aula_input_bridge
        self._hinstance = wintypes.HINSTANCE(42)

    def _base_patches(self, register_result, last_error=None):
        patches = [
            mock.patch.object(
                self.bridge.user32, "RegisterClassW", return_value=register_result
            ),
            mock.patch.object(
                self.bridge.kernel32,
                "GetModuleHandleW",
                return_value=self._hinstance,
            ),
            mock.patch.object(
                self.bridge.user32, "CreateWindowExW", return_value=wintypes.HWND(1)
            ),
            mock.patch.object(
                self.bridge.user32, "RegisterRawInputDevices", return_value=True
            ),
            mock.patch.object(self.bridge, "signal"),
            mock.patch.object(
                self.bridge.user32, "DestroyWindow", return_value=True
            ),
            mock.patch.object(
                self.bridge.user32, "UnregisterClassW", return_value=True
            ),
            mock.patch.object(
                self.bridge.time, "sleep", side_effect=SystemExit(0)
            ),
        ]
        if last_error is not None:
            patches.append(
                mock.patch.object(
                    ctypes, "get_last_error", return_value=last_error
                )
            )
        return patches

    def _run_capture(self, register_result, last_error=None):
        patches = self._base_patches(register_result, last_error)
        for p in patches:
            p.__enter__()
        try:
            try:
                self.bridge.capture_raw()
            except SystemExit:
                pass
        finally:
            for p in reversed(patches):
                p.__exit__(None, None, None)

    def test_successful_class_registration(self):
        registered = []

        def fake_register(wc_ptr):
            registered.append(wc_ptr)
            return 1

        patches = self._base_patches(1)
        patches[0] = mock.patch.object(
            self.bridge.user32, "RegisterClassW", side_effect=fake_register
        )
        for p in patches:
            p.__enter__()
        try:
            try:
                self.bridge.capture_raw()
            except SystemExit:
                pass
        finally:
            for p in reversed(patches):
                p.__exit__(None, None, None)
        self.assertEqual(len(registered), 1)

    def test_error_class_already_exists_is_not_fatal(self):
        self._run_capture(0, CLASS_ALREADY_EXISTS)

    def test_other_register_errors_include_error_code(self):
        with self.assertRaises(OSError) as ctx:
            self._run_capture(0, 5)
        self.assertIn("RegisterClassW failed with error 5", str(ctx.exception))

    def test_hinstance_passed_to_registration_and_window(self):
        hinstance = wintypes.HINSTANCE(999)
        capture = {}

        def fake_register(wc_ptr):
            capture["wc_ptr"] = wc_ptr
            return 1

        def fake_create(*args, **kwargs):
            capture["create_args"] = args
            return wintypes.HWND(1)

        patches = self._base_patches(1)
        patches[0] = mock.patch.object(
            self.bridge.user32, "RegisterClassW", side_effect=fake_register
        )
        patches[1] = mock.patch.object(
            self.bridge.kernel32, "GetModuleHandleW", return_value=hinstance
        )
        patches[2] = mock.patch.object(
            self.bridge.user32, "CreateWindowExW", side_effect=fake_create
        )
        for p in patches:
            p.__enter__()
        try:
            try:
                self.bridge.capture_raw()
            except SystemExit:
                pass
        finally:
            for p in reversed(patches):
                p.__exit__(None, None, None)

        wc = ctypes.cast(capture["wc_ptr"], ctypes.POINTER(self.bridge.WNDCLASSW)).contents
        self.assertEqual(int(wc.hInstance), int(hinstance.value))
        self.assertEqual(capture["create_args"][10], hinstance)

    def test_strong_callback_reference_retained(self):
        captured = {}

        def fake_register(wc_ptr):
            captured["wc_ptr"] = wc_ptr
            return 1

        patches = self._base_patches(1)
        patches[0] = mock.patch.object(
            self.bridge.user32, "RegisterClassW", side_effect=fake_register
        )
        for p in patches:
            p.__enter__()
        try:
            try:
                self.bridge.capture_raw()
            except SystemExit:
                pass
        finally:
            for p in reversed(patches):
                p.__exit__(None, None, None)

        self.assertIn("wc_ptr", captured)
        wc = ctypes.cast(captured["wc_ptr"], ctypes.POINTER(self.bridge.WNDCLASSW)).contents
        self.assertIsInstance(wc.lpfnWndProc, self.bridge.WNDPROC)
        
        # Verify WNDPROC result type is pointer-sized signed integer
        self.assertEqual(self.bridge.WNDPROC._restype_, ctypes.c_ssize_t)


    def test_cleanup_only_unregisters_when_registered_by_us(self):
        unregistered = []

        def fake_unregister(class_name, hinstance):
            unregistered.append((class_name, hinstance))
            return True

        patches = self._base_patches(1)
        patches[-2] = mock.patch.object(
            self.bridge.user32, "UnregisterClassW", side_effect=fake_unregister
        )
        for p in patches:
            p.__enter__()
        try:
            try:
                self.bridge.capture_raw()
            except SystemExit:
                pass
        finally:
            for p in reversed(patches):
                p.__exit__(None, None, None)

        self.assertEqual(len(unregistered), 1)
        self.assertEqual(unregistered[0][1], self._hinstance)


class VIDPIDPathParsingTests(unittest.TestCase):
    def test_parse_vid_pid_from_l99_path(self):
        vid, pid = devices.parse_vid_pid_from_path(
            "\\\\?\\HID#VID_0C45&PID_800A&MI_00#7&1a2b3c4d&0&0000"
        )
        self.assertEqual(vid, 0x0C45)
        self.assertEqual(pid, 0x800A)

    def test_parse_vid_pid_missing_returns_none(self):
        self.assertIsNone(devices.parse_vid_pid_from_path("\\\\?\\HID#unknown"))
        self.assertIsNone(devices.parse_vid_pid_from_path("not-a-path"))
        # A syntactically valid VID/PID still parses (non-L99 values are fine).
        vid, pid = devices.parse_vid_pid_from_path("\\\\?\\HID#VID_1234&PID_5678")
        self.assertEqual((vid, pid), (0x1234, 0x5678))

    def test_is_l99_path_accepted(self):
        self.assertTrue(devices.is_l99_path("\\\\?\\HID#VID_0C45&PID_800A&MI_00#7&...&0&0000"))

    def test_is_l99_path_non_l99_rejected(self):
        self.assertFalse(devices.is_l99_path("\\\\?\\HID#VID_1234&PID_5678&MI_00#7&...&0&0000"))
        self.assertFalse(devices.is_l99_path("\\\\?\\HID#VID_0C45&PID_800A&MI_01#7&...&0&0000"))
        self.assertFalse(devices.is_l99_path("not-a-path"))


class L99PathAcceptanceTests(unittest.TestCase):
    def test_mi_00_l99_path_accepted(self):
        self.assertTrue(devices.is_l99_path("\\\\?\\HID#VID_0C45&PID_800A&MI_00#7&1a2b3c4d&0&0000"))

    def test_non_l99_device_rejected(self):
        self.assertFalse(devices.is_l99_path("\\\\?\\HID#VID_1234&PID_5678&MI_00#7&1a2b3c4d&0&0000"))

    def test_is_l99_vid_pid(self):
        self.assertTrue(devices.is_l99_vid_pid(0x0C45, 0x800A))
        self.assertFalse(devices.is_l99_vid_pid(0x0C45, 0x0001))
        self.assertFalse(devices.is_l99_vid_pid(0x0000, 0x800A))


if __name__ == "__main__":
    unittest.main()
