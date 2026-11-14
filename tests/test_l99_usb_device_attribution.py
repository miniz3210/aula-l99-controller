"""Tests for AULA L99 USB Device Attribution Utility."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "research"))

from scripts.research.l99_usb_device_attribution import (
    verify_capture_sha256,
    run_tshark_extract,
    run_tshark_verbose,
    extract_device_mappings,
    DeviceMapping,
    AmbiguousMapping,
    EXPECTED_SHA256,
    TARGET_DEVICE_ADDRESSES,
)


class TestVerifyCaptureSHA256:
    def test_known_capture_hash(self, tmp_path):
        capture = tmp_path / "test.pcapng"
        capture.write_bytes(b"test data")
        expected = hashlib.sha256(b"test data").hexdigest().upper()
        assert verify_capture_sha256(capture) == expected

    def test_deterministic_hash(self, tmp_path):
        capture = tmp_path / "test.pcapng"
        capture.write_bytes(b"deterministic content")
        h1 = verify_capture_sha256(capture)
        h2 = verify_capture_sha256(capture)
        assert h1 == h2


class TestRunTsharkExtract:
    @patch("scripts.research.l99_usb_device_attribution.subprocess.run")
    def test_successful_extract(self, mock_run):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "1\t15\teeef\t268a\t01\t\n"
        mock_run.return_value = mock_result

        result = run_tshark_extract(Path("test.pcapng"), "15")
        assert len(result) == 1
        assert result[0]["idvendor"] == "eeef"
        assert result[0]["idproduct"] == "268a"

    @patch("scripts.research.l99_usb_device_attribution.subprocess.run")
    def test_tshark_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        import pytest
        with pytest.raises(FileNotFoundError):
            run_tshark_verbose(Path("test.pcapng"), "15")

    @patch("scripts.research.l99_usb_device_attribution.subprocess.run")
    def test_tshark_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)
        result = run_tshark_verbose(Path("test.pcapng"), "15")
        assert result == []

    @patch("scripts.research.l99_usb_device_attribution.subprocess.run")
    def test_tshark_nonzero_exit(self, mock_run):
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        result = run_tshark_verbose(Path("test.pcapng"), "15")
        assert result == []


class TestRunTsharkVerbose:
    @patch("scripts.research.l99_usb_device_attribution.subprocess.run")
    def test_parse_verbose_output(self, mock_run):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """Frame Number: 32
    idVendor: Unknown (0xeeef)
    idProduct: Unknown (0x268a)
    Manufacturer: Unknown
    Product: Unknown"""
        mock_run.return_value = mock_result

        result = run_tshark_verbose(Path("test.pcapng"), "15")
        assert len(result) == 1
        assert result[0]["idvendor"] in ("eeef", "0xeeef")
        assert result[0]["idproduct"] in ("268a", "0x268a")
        assert result[0]["frame"] == 32

    @patch("scripts.research.l99_usb_device_attribution.subprocess.run")
    def test_parse_multiple_frames(self, mock_run):
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """Frame Number: 32
    idVendor: Unknown (0xeeef)
    idProduct: Unknown (0x268a)
Frame Number: 40
    idVendor: Unknown (0xeeef)
    idProduct: Unknown (0x268a)"""
        mock_run.return_value = mock_result

        result = run_tshark_verbose(Path("test.pcapng"), "15")
        assert len(result) == 2
        assert result[0]["frame"] == 32
        assert result[1]["frame"] == 40


class TestExtractDeviceMappings:
    @patch("scripts.research.l99_usb_device_attribution.run_tshark_verbose")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_extract_all_four_devices(self, mock_verify, mock_verbose):
        mock_verify.return_value = EXPECTED_SHA256

        def verbose_side_effect(cap, addr, tshark_path=None):
            if addr == "6":
                return [{"frame": 80, "idvendor": "05e3", "idproduct": "0626", "vendor_name": "Genesys Logic, Inc.", "product_name": "Hub"}]
            elif addr == "13":
                return [{"frame": 26, "idvendor": "1a86", "idproduct": "8091", "vendor_name": "QinHeng Electronics", "product_name": "Unknown"}]
            elif addr == "15":
                return [{"frame": 32, "idvendor": "eeef", "idproduct": "268a", "vendor_name": "Unknown", "product_name": "Unknown"}]
            elif addr == "16":
                return [{"frame": 38, "idvendor": "0c45", "idproduct": "800a", "vendor_name": "Microdia", "product_name": "Vivitar Vivicam3350B"}]
            return []

        mock_verbose.side_effect = verbose_side_effect

        mappings, ambiguous = extract_device_mappings(Path("test.pcapng"))

        assert len(mappings) == 4
        assert len(ambiguous) == 0

        mapped_addrs = {m.device_address for m in mappings}
        assert mapped_addrs == {"6", "13", "15", "16"}

        m6 = next(m for m in mappings if m.device_address == "6")
        assert m6.vid == "05E3"
        assert m6.pid == "0626"

        m13 = next(m for m in mappings if m.device_address == "13")
        assert m13.vid == "1A86"
        assert m13.pid == "8091"

        m15 = next(m for m in mappings if m.device_address == "15")
        assert m15.vid == "EEEF"
        assert m15.pid == "268A"

        m16 = next(m for m in mappings if m.device_address == "16")
        assert m16.vid == "0C45"
        assert m16.pid == "800A"

    @patch("scripts.research.l99_usb_device_attribution.run_tshark_verbose")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_ambiguous_mapping(self, mock_verify, mock_verbose):
        mock_verify.return_value = EXPECTED_SHA256

        def verbose_side_effect(cap, addr, tshark_path=None):
            if addr == "6":
                return [
                    {"frame": 80, "idvendor": "05e3", "idproduct": "0626"},
                    {"frame": 90, "idvendor": "1234", "idproduct": "5678"},
                ]
            return []

        mock_verbose.side_effect = verbose_side_effect

        mappings, ambiguous = extract_device_mappings(Path("test.pcapng"))

        assert len(mappings) == 0
        assert len(ambiguous) == 1
        assert ambiguous[0].device_address == "6"
        assert len(ambiguous[0].candidates) == 2

    @patch("scripts.research.l99_usb_device_attribution.run_tshark_verbose")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_missing_descriptor(self, mock_verify, mock_verbose):
        mock_verify.return_value = EXPECTED_SHA256
        mock_verbose.return_value = []

        mappings, ambiguous = extract_device_mappings(Path("test.pcapng"))

        assert len(mappings) == 0
        assert len(ambiguous) == 0


class TestDeviceMapping:
    def test_to_json(self):
        m = DeviceMapping(
            device_address="15",
            vid="EEEF",
            pid="268A",
            vendor_name="Unknown",
            product_name="Unknown",
            descriptor_frame=32,
            descriptor_type="DEVICE",
            capture_sha256=EXPECTED_SHA256
        )
        j = m.to_json()
        assert j["device_address"] == "15"
        assert j["vid"] == "EEEF"
        assert j["pid"] == "268A"

    def test_sorting_by_device_address(self):
        m1 = DeviceMapping("6", "05E3", "0626", "", "", 80, "DEVICE", EXPECTED_SHA256)
        m2 = DeviceMapping("15", "EEEF", "268A", "", "", 32, "DEVICE", EXPECTED_SHA256)
        m3 = DeviceMapping("13", "1A86", "8091", "", "", 26, "DEVICE", EXPECTED_SHA256)
        mappings = [m1, m2, m3]
        sorted_mappings = sorted(mappings, key=lambda m: int(m.device_address))
        assert [m.device_address for m in sorted_mappings] == ["6", "13", "15"]


class TestAmbiguousMapping:
    def test_to_json(self):
        a = AmbiguousMapping(
            device_address="6",
            candidates=[{"frame": 80, "vid": "05E3", "pid": "0626"}],
            capture_sha256=EXPECTED_SHA256
        )
        j = a.to_json()
        assert j["device_address"] == "6"
        assert len(j["candidates"]) == 1


class TestMainFunction:
    @patch("scripts.research.l99_usb_device_attribution.extract_device_mappings")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_main_sha256_mismatch(self, mock_verify, mock_extract, capsys):
        mock_verify.return_value = "WRONG_HASH"

        from scripts.research.l99_usb_device_attribution import main
        result = main([])
        assert result == 1

    @patch("scripts.research.l99_usb_device_attribution.extract_device_mappings")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_main_success(self, mock_verify, mock_extract, capsys):
        mock_verify.return_value = EXPECTED_SHA256
        mock_extract.return_value = ([], [])

        from scripts.research.l99_usb_device_attribution import main
        result = main([])
        assert result == 0

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["capture_sha256"] == EXPECTED_SHA256


class TestDeterministicOutput:
    @patch("scripts.research.l99_usb_device_attribution.run_tshark_verbose")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_deterministic_ordering(self, mock_verify, mock_verbose):
        mock_verify.return_value = EXPECTED_SHA256

        def verbose_side_effect(cap, addr, tshark_path=None):
            if addr == "6":
                return [{"frame": 80, "idvendor": "05e3", "idproduct": "0626"}]
            elif addr == "13":
                return [{"frame": 26, "idvendor": "1a86", "idproduct": "8091"}]
            elif addr == "15":
                return [{"frame": 32, "idvendor": "eeef", "idproduct": "268a"}]
            elif addr == "16":
                return [{"frame": 38, "idvendor": "0c45", "idproduct": "800a"}]
            return []

        mock_verbose.side_effect = verbose_side_effect

        mappings1, _ = extract_device_mappings(Path("test.pcapng"))
        mappings2, _ = extract_device_mappings(Path("test.pcapng"))

        assert [m.device_address for m in mappings1] == [m.device_address for m in mappings2]
        assert [m.vid for m in mappings1] == [m.vid for m in mappings2]
        assert [m.pid for m in mappings1] == [m.pid for m in mappings2]


class TestCaptureLocalAddresses:
    @patch("scripts.research.l99_usb_device_attribution.run_tshark_verbose")
    @patch("scripts.research.l99_usb_device_attribution.verify_capture_sha256")
    def test_preserves_capture_local_addresses(self, mock_verify, mock_verbose):
        mock_verify.return_value = EXPECTED_SHA256

        def verbose_side_effect(cap, addr, tshark_path=None):
            return [{"frame": 100, "idvendor": "abcd", "idproduct": "ef01"}]

        mock_verbose.side_effect = verbose_side_effect

        mappings, _ = extract_device_mappings(Path("test.pcapng"))

        for m in mappings:
            assert m.device_address in TARGET_DEVICE_ADDRESSES
            assert m.device_address in ("6", "13", "15", "16")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])