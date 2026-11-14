#!/usr/bin/env python3
"""Unit tests for HFD address cross-reference scanner."""

import struct
import pytest
from scripts.research.hfd_address_xrefs import (
    verify_firmware,
    is_in_prohibited_range,
    scan_raw_pattern,
    check_instruction_context,
    scan_address_xrefs,
    TARGET_ADDRESS,
    TARGET_PATTERN,
    IMAGE_BASE,
    IMAGE_END,
    PROHIBITED_START,
    PROHIBITED_END,
    EXPECTED_SIZE,
    EXPECTED_SHA256,
)


class TestAddressToOffsetConversion:
    """Tests for correct address-to-offset conversion."""

    def test_image_base_to_offset_zero(self):
        assert IMAGE_BASE + 0 == IMAGE_BASE

    def test_image_end_exclusive(self):
        assert IMAGE_END == 0x6005C934
        assert IMAGE_END - IMAGE_BASE == EXPECTED_SIZE

    def test_target_address_pattern(self):
        expected = struct.pack("<I", TARGET_ADDRESS)
        assert TARGET_PATTERN == expected
        assert TARGET_PATTERN == b"\x40\xef\x86\x00"


class TestLittleEndianPatternDetection:
    """Tests for little-endian pattern detection."""

    def test_pattern_bytes(self):
        assert TARGET_PATTERN == b"\x40\xef\x86\x00"

    def test_scan_finds_pattern_at_known_offset(self):
        firmware = bytearray(EXPECTED_SIZE)
        offset = 0x1000
        firmware[offset:offset + 4] = TARGET_PATTERN
        matches = scan_raw_pattern(bytes(firmware))
        assert len(matches) == 1
        assert matches[0] == (offset, IMAGE_BASE + offset)

    def test_scan_finds_multiple_patterns(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x1000:0x1004] = TARGET_PATTERN
        firmware[0x2000:0x2004] = TARGET_PATTERN
        firmware[0x3000:0x3004] = TARGET_PATTERN
        matches = scan_raw_pattern(bytes(firmware))
        assert len(matches) == 3
        assert matches[0] == (0x1000, IMAGE_BASE + 0x1000)
        assert matches[1] == (0x2000, IMAGE_BASE + 0x2000)
        assert matches[2] == (0x3000, IMAGE_BASE + 0x3000)

    def test_scan_no_matches(self):
        firmware = bytearray(EXPECTED_SIZE)
        matches = scan_raw_pattern(bytes(firmware))
        assert matches == []

    def test_scan_pattern_at_end_boundary(self):
        firmware = bytearray(EXPECTED_SIZE)
        offset = EXPECTED_SIZE - 4
        firmware[offset:offset + 4] = TARGET_PATTERN
        matches = scan_raw_pattern(bytes(firmware))
        assert len(matches) == 1
        assert matches[0] == (offset, IMAGE_BASE + offset)

    def test_scan_pattern_overlaps(self):
        firmware = bytearray(b"\x40\xef\x86\x00\x40\xef\x86\x00")
        matches = scan_raw_pattern(bytes(firmware))
        assert len(matches) == 2
        assert matches[0] == (0, IMAGE_BASE + 0)
        assert matches[1] == (4, IMAGE_BASE + 4)


class TestMultipleOccurrences:
    """Tests for handling multiple occurrences."""

    def test_sorted_by_offset(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x5000:0x5004] = TARGET_PATTERN
        firmware[0x1000:0x1004] = TARGET_PATTERN
        firmware[0x3000:0x3004] = TARGET_PATTERN
        matches = scan_raw_pattern(bytes(firmware))
        assert matches[0][0] == 0x1000
        assert matches[1][0] == 0x3000
        assert matches[2][0] == 0x5000


class TestNoMatchBehavior:
    """Tests for no-match behavior."""

    def test_empty_firmware(self):
        matches = scan_raw_pattern(b"")
        assert matches == []

    def test_firmware_without_pattern(self):
        firmware = bytes([0xFF] * EXPECTED_SIZE)
        matches = scan_raw_pattern(firmware)
        assert matches == []

    def test_partial_pattern_at_end(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[EXPECTED_SIZE - 2:] = TARGET_PATTERN[:2]
        matches = scan_raw_pattern(bytes(firmware))
        assert matches == []


class TestFirmwareIdentityRejection:
    """Tests for firmware identity verification."""

    def test_size_mismatch_rejected(self):
        firmware = bytes(EXPECTED_SIZE - 1)
        ok, error = verify_firmware(firmware)
        assert not ok
        assert "size mismatch" in error

    def test_sha256_mismatch_rejected(self):
        firmware = bytes([0x00] * EXPECTED_SIZE)
        ok, error = verify_firmware(firmware)
        assert not ok
        assert "SHA256 mismatch" in error

    def test_correct_firmware_accepted(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[:4] = TARGET_PATTERN
        ok, error = verify_firmware(bytes(firmware))
        assert not ok
        assert "SHA256 mismatch" in error


class TestProhibitedRangeHandling:
    """Tests for prohibited range handling."""

    def test_prohibited_range_constants(self):
        assert PROHIBITED_START == 0x60031198
        assert PROHIBITED_END == 0x600315D0

    def test_address_in_prohibited_range(self):
        assert is_in_prohibited_range(PROHIBITED_START)
        assert is_in_prohibited_range(PROHIBITED_END)
        assert is_in_prohibited_range((PROHIBITED_START + PROHIBITED_END) // 2)

    def test_address_outside_prohibited_range(self):
        assert not is_in_prohibited_range(PROHIBITED_START - 1)
        assert not is_in_prohibited_range(PROHIBITED_END + 1)
        assert not is_in_prohibited_range(IMAGE_BASE)
        assert not is_in_prohibited_range(IMAGE_END - 1)

    def test_context_analysis_flags_prohibited(self):
        firmware = bytearray(EXPECTED_SIZE)
        prohibited_offset = PROHIBITED_START - IMAGE_BASE
        firmware[prohibited_offset:prohibited_offset + 4] = TARGET_PATTERN
        ctx = check_instruction_context(bytes(firmware), prohibited_offset)
        assert ctx["is_prohibited"] is True


class TestDeterministicOrdering:
    """Tests for deterministic, sorted results."""

    def test_raw_matches_sorted_by_offset(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x5000:0x5004] = TARGET_PATTERN
        firmware[0x1000:0x1004] = TARGET_PATTERN
        firmware[0x3000:0x3004] = TARGET_PATTERN
        matches = scan_raw_pattern(bytes(firmware))
        offsets = [m[0] for m in matches]
        assert offsets == sorted(offsets)

    def test_context_analysis_follows_raw_matches_order(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x5000:0x5004] = TARGET_PATTERN
        firmware[0x1000:0x1004] = TARGET_PATTERN
        raw_matches = scan_raw_pattern(bytes(firmware))
        context_analysis = [check_instruction_context(bytes(firmware), off) for off, _ in raw_matches]
        ctx_offsets = [c["file_offset"] for c in context_analysis]
        assert ctx_offsets == [0x1000, 0x5000]


class TestClearClassification:
    """Tests for clear classification of raw matches."""

    def test_raw_match_flagged(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x1000:0x1004] = TARGET_PATTERN
        raw_matches = scan_raw_pattern(bytes(firmware))
        context_analysis = [check_instruction_context(bytes(firmware), off) for off, _ in raw_matches]
        assert raw_matches[0][0] == 0x1000
        assert context_analysis[0]["raw_match"] is True

    def test_instruction_kind_classification(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x1000:0x1004] = TARGET_PATTERN

        # Little-endian: high byte at offset+1
        firmware[0x1000] = 0x00
        firmware[0x1001] = 0x70
        ctx = check_instruction_context(bytes(firmware), 0x1000)
        assert ctx["instruction_kind"] == "jmpi"

        firmware[0x1000] = 0x00
        firmware[0x1001] = 0x7F
        ctx = check_instruction_context(bytes(firmware), 0x1000)
        assert ctx["instruction_kind"] == "jsri"

        firmware[0x1000] = 0x00
        firmware[0x1001] = 0x00
        ctx = check_instruction_context(bytes(firmware), 0x1000)
        assert ctx["instruction_kind"] == "other"

    def test_unaligned_instruction_flagged(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x1001:0x1005] = TARGET_PATTERN
        ctx = check_instruction_context(bytes(firmware), 0x1001)
        assert ctx["instruction_kind"] == "unaligned"

    def test_truncated_instruction_flagged(self):
        firmware = bytearray(EXPECTED_SIZE - 1)
        firmware[EXPECTED_SIZE - 2] = 0x40
        ctx = check_instruction_context(bytes(firmware), EXPECTED_SIZE - 2)
        assert ctx["instruction_kind"] == "truncated"


class TestFullScanIntegration:
    """Integration tests for full scan function."""

    def test_scan_returns_structured_results(self):
        firmware = bytearray(EXPECTED_SIZE)
        firmware[0x1000:0x1004] = TARGET_PATTERN
        results = scan_address_xrefs(bytes(firmware))
        assert "firmware_verified" in results
        assert "raw_matches" in results
        assert "context_analysis" in results

    def test_scan_rejects_invalid_firmware(self):
        firmware = bytes(100)
        results = scan_address_xrefs(firmware)
        assert results["firmware_verified"] is False
        assert "error" in results
        assert results["raw_matches"] == []
        assert results["context_analysis"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])