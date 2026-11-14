#!/usr/bin/env python3
"""Tests for MCore literal-pool resolution helper.

Validates jmpi/jsri literal-pool target resolution for offline verification.
"""

import struct
import unittest
from pathlib import Path

# Add the research scripts directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "research"))

from mcore_literal_pool import resolve_literal_pool_target, is_valid_jmpi_jsri_instruction

IMAGE_BASE = 0x60010000
LARGE_SIZE = 0x100000  # 1 MB, large enough to hold all synthetic targets


def make_firmware(size=LARGE_SIZE):
    """Return a zero-filled firmware bytearray of the given size."""
    return bytearray(size)


def set_instruction(firmware, image_base, address, word):
    """Write a 16-bit instruction word at the given address."""
    off = address - image_base
    firmware[off:off + 2] = struct.pack("<H", word)


def set_literal(firmware, image_base, address, value):
    """Write a 4-byte little-endian u32 literal at the given address."""
    off = address - image_base
    firmware[off:off + 4] = struct.pack("<I", value)


class TestMCoreLiteralPool(unittest.TestCase):
    """Test the MCore literal-pool resolution helper."""

    def test_is_valid_jmpi_jsri_instruction(self):
        """Test instruction validation function."""
        # Valid jmpi (0x7000 + reg): high byte = 0x70
        self.assertTrue(is_valid_jmpi_jsri_instruction(0x7000))
        self.assertTrue(is_valid_jmpi_jsri_instruction(0x7001))  # reg 1
        self.assertTrue(is_valid_jmpi_jsri_instruction(0x700F))  # reg 15

        # Valid jsri (0x7F00 + reg): high byte = 0x7F
        self.assertTrue(is_valid_jmpi_jsri_instruction(0x7F00))
        self.assertTrue(is_valid_jmpi_jsri_instruction(0x7F01))  # reg 1

        # Invalid opcodes
        self.assertFalse(is_valid_jmpi_jsri_instruction(0x0000))  # unknown
        self.assertFalse(is_valid_jmpi_jsri_instruction(0xE000))  # cond branch
        self.assertFalse(is_valid_jmpi_jsri_instruction(0xF000))  # jr (uncond_branch), not jmpi/jsri
        self.assertFalse(is_valid_jmpi_jsri_instruction(0x8000))  # other

    # STEP 4 test 1: Opcode 0x7000 at address mod 4 = 0.
    def test_jmpi_0x7000_addr_mod4_0(self):
        """jmpi 0x7000 at address mod 4 == 0 resolves pool at (addr+2)&~3."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000  # mod 4 == 0
        target = 0x600522AE
        pool = (addr + 2 + ((0x7000 & 0xFF) << 2)) & ~3  # == addr
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["instruction_kind"], "jmpi")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertEqual(result["loaded_target_address"], hex(target))
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(result["evidence_classification"], "VERIFIED")

    # STEP 4 test 2: Opcode 0x7000 at address mod 4 = 2.
    def test_jmpi_0x7000_addr_mod4_2(self):
        """jmpi 0x7000 at address mod 4 == 2 resolves pool at addr + 2."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1002  # mod 4 == 2
        target = 0x60052294
        pool = (addr + 2 + ((0x7000 & 0xFF) << 2)) & ~3  # == addr + 2
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["instruction_kind"], "jmpi")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertEqual(result["loaded_target_address"], hex(target))
        self.assertEqual(result["validation_status"], "PASSED")

    # STEP 4 test 3: Opcode 0x7001 at address mod 4 = 0.
    def test_jmpi_0x7001_addr_mod4_0(self):
        """jmpi 0x7001 at address mod 4 == 0 resolves pool at addr + 4."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000  # mod 4 == 0
        target = 0x60054EC8
        pool = (addr + 2 + ((0x7001 & 0xFF) << 2)) & ~3  # == addr + 4
        set_instruction(firmware, IMAGE_BASE, addr, 0x7001)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7001)

        self.assertEqual(result["instruction_kind"], "jmpi")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertEqual(result["loaded_target_address"], hex(target))
        self.assertEqual(result["validation_status"], "PASSED")

    # STEP 4 test 4: Opcode 0x7001 at address mod 4 = 2.
    def test_jmpi_0x7001_addr_mod4_2(self):
        """jmpi 0x7001 at address mod 4 == 2 resolves pool at addr + 6."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1002  # mod 4 == 2
        target = 0x60052294
        pool = (addr + 2 + ((0x7001 & 0xFF) << 2)) & ~3  # == addr + 6
        set_instruction(firmware, IMAGE_BASE, addr, 0x7001)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7001)

        self.assertEqual(result["instruction_kind"], "jmpi")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertEqual(result["loaded_target_address"], hex(target))
        self.assertEqual(result["validation_status"], "PASSED")

    # STEP 4 test 5: Pool address differs from site+2.
    def test_pool_address_differs_from_site_plus_2(self):
        """Pool address must not fall back to site + 2."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000  # mod 4 == 0
        target = 0x600522AE
        pool = (addr + 2 + ((0x7001 & 0xFF) << 2)) & ~3  # == addr + 4
        self.assertNotEqual(pool, addr + 2)
        set_instruction(firmware, IMAGE_BASE, addr, 0x7001)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7001)

        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertNotEqual(result["literal_pool_address"], hex(addr + 2))

    # STEP 4 test 6: Pool near image end.
    def test_pool_near_image_end(self):
        """Pool exactly at image_end - 4 passes strict bounds."""
        size = 0x1000
        firmware = make_firmware(size=size)
        image_end = IMAGE_BASE + size  # 0x60011000
        pool = image_end - 4  # 0x60010FFC, mod 4 == 0
        addr = pool  # mod 4 == 0, instruction at addr inside image
        target = addr  # target inside image, even
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertEqual(result["loaded_target_address"], hex(target))

    # STEP 4 test 7: Truncated literal read.
    def test_truncated_literal_read(self):
        """Pool whose 4 bytes exceed image bounds fails."""
        size = 0x1003  # image_end mod 4 == 3
        firmware = make_firmware(size=size)
        image_end = IMAGE_BASE + size  # mod 4 == 3
        pool = image_end - 3  # leaves only 3 bytes
        addr = pool - 2  # mod 4 == 2 for 0x7000 -> pool = addr + 2
        target = 0x600522AE
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["validation_status"], "FAILED")
        self.assertIsNotNone(result["failure_reason"])
        self.assertTrue(
            "truncated" in result["failure_reason"]
            or "out_of_image" in result["failure_reason"]
        )

    # STEP 4 test 8: Invalid opcode.
    def test_invalid_opcode(self):
        """Non jmpi/jsri opcode fails."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000
        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0xE000)

        self.assertEqual(result["validation_status"], "FAILED")
        self.assertIn("invalid_opcode", result["failure_reason"])

    # STEP 4 test 9: Prohibited target.
    def test_prohibited_range_target(self):
        """Target inside prohibited range fails."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000
        pool = (addr + 2 + ((0x7000 & 0xFF) << 2)) & ~3
        target = 0x60031200  # inside [0x60031198, 0x600315D0]
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["validation_status"], "FAILED")
        self.assertIn("prohibited_range", result["failure_reason"])

    # STEP 4 test 10: Unaligned target.
    def test_unaligned_target(self):
        """Odd target address fails."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000
        pool = (addr + 2 + ((0x7000 & 0xFF) << 2)) & ~3
        target = 0x600522AF  # odd
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["validation_status"], "FAILED")
        self.assertIn("unaligned_target", result["failure_reason"])

    # STEP 4 test 5b: jsri classification via resolve_literal_pool_target.
    def test_jsri_0x7F00_classification(self):
        """jsri 0x7F00 is classified as jsri and resolves to target."""
        firmware = make_firmware()
        addr = IMAGE_BASE + 0x1000  # mod 4 == 0
        target = 0x600522AE
        pool = (addr + 2 + ((0x7F00 & 0xFF) << 2)) & ~3  # == addr
        set_instruction(firmware, IMAGE_BASE, addr, 0x7F00)
        set_literal(firmware, IMAGE_BASE, pool, target)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7F00)

        self.assertEqual(result["instruction_kind"], "jsri")
        self.assertEqual(result["literal_pool_address"], hex(pool))
        self.assertEqual(result["loaded_target_address"], hex(target))
        self.assertEqual(result["validation_status"], "PASSED")
        self.assertEqual(result["evidence_classification"], "VERIFIED")

    # STEP 4 test 8: Pool address outside image.
    def test_literal_pool_address_out_of_image(self):
        """Computed literal pool address beyond image end fails."""
        size = 0x10
        firmware = make_firmware(size=size)
        image_end = IMAGE_BASE + size
        addr = image_end - 2  # last 2-byte instruction slot, mod 4 == 2
        target = 0x600522AE
        set_instruction(firmware, IMAGE_BASE, addr, 0x7000)

        result = resolve_literal_pool_target(firmware, IMAGE_BASE, addr, 0x7000)

        self.assertEqual(result["validation_status"], "FAILED")
        self.assertEqual(result["failure_reason"], "literal_pool_address_out_of_image")

    def test_never_modifies_firmware(self):
        """Test that helper never modifies firmware bytes."""
        original_firmware = bytearray(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F")
        firmware_copy = bytearray(original_firmware)

        addr = IMAGE_BASE
        result = resolve_literal_pool_target(
            firmware_copy, IMAGE_BASE, addr, 0x7000
        )

        # Verify firmware unchanged
        self.assertEqual(original_firmware, firmware_copy)

    def test_mcore_literal_pool_structure(self):
        """Test that the helper produces expected structured output."""
        firmware = make_firmware()

        addr = IMAGE_BASE
        result = resolve_literal_pool_target(
            firmware, IMAGE_BASE, addr, 0xF000
        )

        # Check all expected fields are present
        expected_fields = {
            "instruction_address",
            "instruction_word",
            "instruction_kind",
            "literal_pool_address",
            "literal_raw_bytes",
            "loaded_target_address",
            "validation_status",
            "evidence_classification",
            "failure_reason",
        }

        self.assertEqual(set(result.keys()), expected_fields)

    def test_out_of_image_instruction(self):
        """Test instruction address outside image."""
        firmware = make_firmware()

        result = resolve_literal_pool_target(
            firmware, IMAGE_BASE, IMAGE_BASE + 0x100000, 0x7000
        )

        self.assertEqual(result["validation_status"], "FAILED")
        self.assertIn("out_of_image", result["failure_reason"])


if __name__ == "__main__":
    unittest.main()
