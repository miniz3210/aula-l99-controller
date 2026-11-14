#!/usr/bin/env python3
"""Offline literal-pool resolution helper for MCore jmpi/jsri instructions.

Read-only helper to inspect and validate MCore jmpi/jsri literal-pool targets.
Does not integrate into CFG traversal. Never modifies firmware bytes.
"""

import struct
from typing import Dict, Any, Optional, Union

# Prohibited range constants (from hfd_cfg.py)
PROHIBITED_START = 0x60031198
PROHIBITED_END = 0x600315D0


def resolve_literal_pool_target(
    firmware_bytes: bytes,
    image_base: int,
    instruction_address: int,
    instruction_word: int,
) -> Dict[str, Any]:
    """Resolve MCore jmpi/jsri literal-pool target for offline validation.

    Args:
        firmware_bytes: The firmware image as bytes
        image_base: The base address of the firmware image
        instruction_address: Address of the jmpi/jsri instruction
        instruction_word: The 16-bit instruction word at that address

    Returns:
        Dict containing structured validation results with fields:
        - instruction_address
        - instruction_word
        - instruction_kind
        - literal_pool_address
        - literal_raw_bytes
        - loaded_target_address
        - validation_status
        - evidence_classification
        - failure_reason
    """

    result = {
        "instruction_address": instruction_address,
        "instruction_word": hex(instruction_word),
        "instruction_kind": None,
        "literal_pool_address": None,
        "literal_raw_bytes": None,
        "loaded_target_address": None,
        "validation_status": "FAILED",
        "evidence_classification": "INFERRED",
        "failure_reason": None,
    }

    # Validate basic inputs
    if not isinstance(firmware_bytes, (bytes, bytearray)):
        result["failure_reason"] = "invalid_firmware_bytes_type"
        return result

    # Check instruction alignment (must be 2-byte aligned)
    if instruction_address % 2 != 0:
        result["failure_reason"] = "unaligned_instruction_address"
        return result

    # Check instruction inside image bounds (strict two-byte bounds)
    firmware_size = len(firmware_bytes)
    image_end = image_base + firmware_size
    if not (image_base <= instruction_address < image_end - 1):
        result["failure_reason"] = "instruction_address_out_of_image"
        return result

    # Decode instruction category to determine if it's a jmpi/jsri
    # Per mcdis.py LJ class:
    #   jmpi: code 0x7000 (high byte 0x70)
    #   jsri: code 0x7F00 (high byte 0x7F)
    inst_high = (instruction_word >> 8) & 0xFF

    # Check for jmpi (0x7000 + register): high byte = 0x70
    if inst_high == 0x70:
        instruction_kind = "jmpi"
    # Check for jsri (0x7F00 + register): high byte = 0x7F
    elif inst_high == 0x7F:
        instruction_kind = "jsri"
    else:
        result["failure_reason"] = "invalid_opcode_not_jmpi_jsri"
        return result

    result["instruction_kind"] = instruction_kind

    # Extract register from instruction word (low 4 bits for LJ class)
    reg_field = instruction_word & 0xF

    result["instruction_word"] = hex(instruction_word)

    # Calculate literal pool address per mcdis.py:
    # p = (addr + 2 + ((inst & 0xFF) << 2)) & ~3
    literal_pool_address = (
        instruction_address
        + 2
        + ((instruction_word & 0xFF) << 2)
    ) & ~3

    # Strict four-byte pool bounds: pool address + 3 must fit inside image
    if not (image_base <= literal_pool_address <= image_end - 4):
        result["failure_reason"] = "literal_pool_address_out_of_image"
        return result

    # Check literal pool address alignment (must be 4-byte aligned per formula)
    if literal_pool_address % 4 != 0:
        result["failure_reason"] = "unaligned_literal_pool_address"
        return result

    # Read 4-byte literal from literal pool
    pool_offset = literal_pool_address - image_base
    if pool_offset < 0 or pool_offset + 4 > firmware_size:
        result["failure_reason"] = "literal_pool_truncated_firmware"
        return result

    literal_bytes = firmware_bytes[pool_offset:pool_offset + 4]
    if len(literal_bytes) < 4:
        result["failure_reason"] = "literal_pool_truncated_firmware"
        return result

    # Parse the 4-byte target as little-endian u32
    loaded_target_address = struct.unpack_from("<I", literal_bytes, 0)[0]

    result["literal_raw_bytes"] = f"0x{loaded_target_address:08X}"

    # Validate target is 2-byte aligned
    if loaded_target_address % 2 != 0:
        result["failure_reason"] = "unaligned_target"
        return result

    # Validate target inside image
    if not (image_base <= loaded_target_address < image_end):
        result["failure_reason"] = "target_out_of_image"
        return result

    # Validate target not in prohibited range
    if PROHIBITED_START <= loaded_target_address <= PROHIBITED_END:
        result["failure_reason"] = "target_in_prohibited_range"
        return result

    # All validations passed
    result["literal_pool_address"] = hex(literal_pool_address)
    result["loaded_target_address"] = hex(loaded_target_address)
    result["validation_status"] = "PASSED"
    result["evidence_classification"] = "VERIFIED"

    return result


def is_valid_jmpi_jsri_instruction(instruction_word: int) -> bool:
    """Check if an instruction word is a valid jmpi or jsri encoding.

    Args:
        instruction_word: 16-bit instruction word

    Returns:
        True if valid jmpi/jsri encoding, False otherwise
    """
    # Per mcdis.py LJ class:
    #   jmpi: code 0x7000 (high byte 0x70)
    #   jsri: code 0x7F00 (high byte 0x7F)
    high_byte = (instruction_word >> 8) & 0xFF
    if high_byte == 0x70:
        return True  # jmpi pattern (0x7000-0x70FF)
    if high_byte == 0x7F:
        return True  # jsri pattern (0x7F00-0x7FFF)
    return False


if __name__ == "__main__":
    # Simple test/example usage
    print("MCore Literal Pool Resolution Helper")
    print("Usage: python mcore_literal_pool.py [test_mode]")
    print("Run 'python -m pytest test_mcore_literal_pool.py' for tests.")
