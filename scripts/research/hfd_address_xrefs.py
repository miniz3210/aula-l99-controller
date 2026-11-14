#!/usr/bin/env python3
"""Bounded deterministic offline scanner for references to address 0x0086EF40.

Implements byte-pattern scanning for little-endian 32-bit representation of
0x0086EF40 in verified AULA L99 screen firmware (HFD_Code_V2.3.bin).

Does not perform recursive disassembly, CFG traversal, or instruction
validation. Raw byte-pattern matches are clearly distinguished from any
verified instruction references.
"""

import hashlib
import struct
from pathlib import Path
from typing import List, Tuple, Dict, Any


FIRMWARE_PATH = Path("tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin")
EXPECTED_SIZE = 313652
EXPECTED_SHA256 = "A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03"
IMAGE_BASE = 0x60010000
IMAGE_END = 0x6005C934
PROHIBITED_START = 0x60031198
PROHIBITED_END = 0x600315D0
TARGET_ADDRESS = 0x0086EF40
TARGET_PATTERN = struct.pack("<I", TARGET_ADDRESS)


def verify_firmware(firmware_bytes: bytes) -> Tuple[bool, str]:
    """Verify firmware size and SHA256. Returns (ok, error_message)."""
    if len(firmware_bytes) != EXPECTED_SIZE:
        return False, f"size mismatch: expected {EXPECTED_SIZE}, got {len(firmware_bytes)}"
    sha256 = hashlib.sha256(firmware_bytes).hexdigest().upper()
    if sha256 != EXPECTED_SHA256:
        return False, f"SHA256 mismatch: expected {EXPECTED_SHA256}, got {sha256}"
    return True, ""


def is_in_prohibited_range(addr: int) -> bool:
    """Check if address falls in prohibited range."""
    return PROHIBITED_START <= addr <= PROHIBITED_END


def scan_raw_pattern(firmware_bytes: bytes) -> List[Tuple[int, int]]:
    """Scan for raw byte-pattern matches of target address.

    Returns list of (file_offset, image_address) tuples, sorted by offset.
    """
    matches = []
    pattern_len = len(TARGET_PATTERN)
    for offset in range(len(firmware_bytes) - pattern_len + 1):
        if firmware_bytes[offset:offset + pattern_len] == TARGET_PATTERN:
            image_addr = IMAGE_BASE + offset
            matches.append((offset, image_addr))
    return matches


def check_instruction_context(firmware_bytes: bytes, offset: int) -> Dict[str, Any]:
    """Bounded local inspection of instruction context at match offset.

    Only inspects the immediate 2-byte instruction word containing the match.
    Does not perform recursive disassembly or control-flow analysis.
    """
    image_addr = IMAGE_BASE + offset
    result = {
        "file_offset": offset,
        "image_address": hex(image_addr),
        "raw_match": True,
        "instruction_word": None,
        "instruction_address": None,
        "instruction_kind": None,
        "is_prohibited": is_in_prohibited_range(image_addr),
    }

    if offset % 2 != 0:
        result["instruction_kind"] = "unaligned"
        return result

    if offset + 2 > len(firmware_bytes):
        result["instruction_kind"] = "truncated"
        return result

    inst_word = struct.unpack_from("<H", firmware_bytes, offset)[0]
    result["instruction_word"] = hex(inst_word)
    result["instruction_address"] = hex(image_addr)

    inst_high = (inst_word >> 8) & 0xFF
    if inst_high == 0x70:
        result["instruction_kind"] = "jmpi"
    elif inst_high == 0x7F:
        result["instruction_kind"] = "jsri"
    else:
        result["instruction_kind"] = "other"

    return result


def scan_address_xrefs(firmware_bytes: bytes) -> Dict[str, Any]:
    """Main scan function returning structured results."""
    ok, error = verify_firmware(firmware_bytes)
    if not ok:
        return {
            "firmware_verified": False,
            "error": error,
            "raw_matches": [],
            "context_analysis": [],
        }

    raw_matches = scan_raw_pattern(firmware_bytes)
    context_analysis = [check_instruction_context(firmware_bytes, off) for off, _ in raw_matches]

    return {
        "firmware_verified": True,
        "firmware_size": len(firmware_bytes),
        "firmware_sha256": hashlib.sha256(firmware_bytes).hexdigest().upper(),
        "image_base": hex(IMAGE_BASE),
        "image_end": hex(IMAGE_END),
        "prohibited_range": f"{hex(PROHIBITED_START)}-{hex(PROHIBITED_END)}",
        "target_address": hex(TARGET_ADDRESS),
        "target_pattern_bytes": TARGET_PATTERN.hex().upper(),
        "raw_match_count": len(raw_matches),
        "raw_matches": [
            {"file_offset": off, "image_address": hex(addr)}
            for off, addr in raw_matches
        ],
        "context_analysis": context_analysis,
    }


def format_report(results: Dict[str, Any]) -> str:
    """Format results as human-readable report."""
    lines = []
    lines.append("=" * 60)
    lines.append("HFD Address Cross-Reference Scanner Report")
    lines.append("=" * 60)
    lines.append(f"Firmware: {FIRMWARE_PATH}")
    lines.append(f"Target Address: {results.get('target_address', 'N/A')}")
    lines.append(f"Target Pattern (LE): {results.get('target_pattern_bytes', 'N/A')}")
    lines.append("")

    if not results.get("firmware_verified", False):
        lines.append(f"FIRMWARE VERIFICATION FAILED: {results.get('error', 'unknown')}")
        return "\n".join(lines)

    lines.append(f"Firmware Verified: YES")
    lines.append(f"  Size: {results['firmware_size']} bytes (expected {EXPECTED_SIZE})")
    lines.append(f"  SHA256: {results['firmware_sha256']}")
    lines.append(f"  Image Base: {results['image_base']}")
    lines.append(f"  Image End:  {results['image_end']}")
    lines.append(f"  Prohibited Range: {results['prohibited_range']}")
    lines.append("")
    lines.append(f"Raw Byte-Pattern Matches: {results['raw_match_count']}")
    lines.append("-" * 60)

    for i, match in enumerate(results["raw_matches"]):
        lines.append(f"  Match {i + 1}:")
        lines.append(f"    File Offset: 0x{match['file_offset']:06X} ({match['file_offset']})")
        lines.append(f"    Image Addr:  {match['image_address']}")

    lines.append("")
    lines.append("Bounded Local Instruction Context Analysis:")
    lines.append("-" * 60)

    for ctx in results["context_analysis"]:
        lines.append(f"  Offset 0x{ctx['file_offset']:06X} -> {ctx['image_address']}:")
        lines.append(f"    Raw Match: {ctx['raw_match']}")
        lines.append(f"    Instruction Word: {ctx['instruction_word']}")
        lines.append(f"    Instruction Addr: {ctx['instruction_address']}")
        lines.append(f"    Instruction Kind: {ctx['instruction_kind']}")
        lines.append(f"    In Prohibited Range: {ctx['is_prohibited']}")

    lines.append("")
    lines.append("Classification:")
    lines.append("-" * 60)
    lines.append("  RAW MATCH: Byte pattern found in firmware image.")
    lines.append("  VERIFIED INSTRUCTION REFERENCE: Requires full instruction")
    lines.append("    decoding and control-flow validation (not performed here).")
    lines.append("  This scanner ONLY reports raw byte-pattern matches.")

    return "\n".join(lines)


def main():
    firmware_bytes = FIRMWARE_PATH.read_bytes()
    results = scan_address_xrefs(firmware_bytes)
    print(format_report(results))


if __name__ == "__main__":
    main()