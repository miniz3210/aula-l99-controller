#!/usr/bin/env python3
"""
Offline validator for V9.2 boundary collector output.

Validates that the collector JSON produced by V92BoundaryCollector.java
meets the Session C requirements for the bounded function-boundary and
control-flow analysis around 0x60049B90.

Read-only: never mutates firmware, Ghidra project, or accepted artifacts.
"""

import json
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Accepted bounds from the Session C specification
TARGET_ADDRESS = 0x60049B90
WINDOW_START = 0x60049A90
WINDOW_END = 0x60049C90

VALID_CLASSIFICATIONS = {
    "RECOVERABLE_FUNCTION_BODY",
    "PROBABLE_FUNCTION_ENTRY",
    "FALL_THROUGH_REGION",
    "JUMP_TABLE_TARGET",
    "SHARED_BASIC_BLOCK",
    "MISALIGNED_DECODE",
    "DATA_AS_CODE",
    "UNRESOLVED_CODE_REGION",
    "INSUFFICIENT_EVIDENCE",
}

REQUIRED_TOP_LEVEL_KEYS = [
    "schema",
    "program_identity",
    "target",
    "window",
    "raw_bytes",
    "instruction_inventory",
    "incoming_references",
    "outgoing_references",
    "nearest_functions",
    "candidate_blocks",
    "boundary_features",
    "classification",
    "evidence",
]


class ValidationError(Exception):
    """Raised when a validation gate fails."""


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_hex(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if not value.startswith("0x"):
            return None
        try:
            return int(value, 16)
        except ValueError:
            return None
    return None


def format_hex(value: int) -> str:
    return "0x%08X" % value


def validate_top_level_keys(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in data:
            errors.append("missing top-level key: %s" % key)
    return errors


def validate_target(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    target = data.get("target", {})
    if not isinstance(target, dict):
        errors.append("target must be an object")
        return errors
    addr = parse_hex(target.get("address"))
    if addr is None:
        errors.append("target address is missing or malformed")
    elif addr != TARGET_ADDRESS:
        errors.append(
            "target address %s differs from required 0x60049B90" % format_hex(addr)
        )
    return errors


def validate_window(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    window = data.get("window", {})
    if not isinstance(window, dict):
        errors.append("window must be an object")
        return errors
    start = parse_hex(window.get("start"))
    end = parse_hex(window.get("end"))
    if start is None:
        errors.append("window start is missing or malformed")
    elif start < WINDOW_START:
        errors.append("window start %s below allowed 0x60049A90" % format_hex(start))
    if end is None:
        errors.append("window end is missing or malformed")
    elif end > WINDOW_END:
        errors.append("window end %s exceeds allowed 0x60049C90" % format_hex(end))
    if start is not None and end is not None and end < start:
        errors.append("window end %s is before start %s" % (format_hex(end), format_hex(start)))
    return errors


def validate_raw_bytes(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    raw = data.get("raw_bytes", {})
    if not isinstance(raw, dict):
        errors.append("raw_bytes must be an object")
        return errors
    if not raw.get("present", False):
        errors.append("raw bytes are absent")
    if "bytes" not in raw or raw["bytes"] is None:
        errors.append("raw bytes list is absent")
    if "hex" not in raw or not raw["hex"]:
        errors.append("raw bytes hex string is absent")
    if "size" not in raw:
        errors.append("raw bytes size is absent")
    return errors


def validate_instruction_inventory(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    inv = data.get("instruction_inventory", [])
    if not isinstance(inv, list):
        errors.append("instruction_inventory must be a list")
        return errors
    if len(inv) == 0:
        errors.append("instruction inventory is empty")
    prev_offset: Optional[int] = None
    for i, ins in enumerate(inv):
        if not isinstance(ins, dict):
            errors.append("instruction %d is not an object" % i)
            continue
        addr = parse_hex(ins.get("address"))
        if addr is None:
            errors.append("instruction %d address is missing or malformed" % i)
        if prev_offset is not None and addr is not None and addr < prev_offset:
            errors.append("instruction addresses not sorted at index %d" % i)
        prev_offset = addr
        for field in ("length", "mnemonic", "flow_type"):
            if field not in ins:
                errors.append("instruction %d missing field: %s" % (i, field))
    return errors


def validate_addresses_sorted(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    # incoming_references sorted by from_address
    for key in ("incoming_references", "outgoing_references"):
        refs = data.get(key, [])
        if not isinstance(refs, list):
            errors.append("%s must be a list" % key)
            continue
        prev: Optional[int] = None
        for i, r in enumerate(refs):
            if not isinstance(r, dict):
                errors.append("%s[%d] is not an object" % (key, i))
                continue
            fa = parse_hex(r.get("from_address"))
            if fa is None:
                errors.append("%s[%d] from_address missing or malformed" % (key, i))
            elif prev is not None and fa < prev:
                errors.append("%s not sorted by from_address at index %d" % (key, i))
            prev = fa
    return errors


def validate_classification(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    cls = data.get("classification", {})
    if not isinstance(cls, dict):
        errors.append("classification must be an object")
        return errors
    name = cls.get("classification")
    if name is None:
        errors.append("classification name is missing")
    elif name not in VALID_CLASSIFICATIONS:
        errors.append("classification %s is not valid" % name)
    if "evidence_summary" not in cls:
        errors.append("classification lacks supporting evidence")
    return errors


def validate_probable_entry_requires_flow(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    cls = data.get("classification", {})
    if not isinstance(cls, dict):
        return errors
    if cls.get("classification") == "PROBABLE_FUNCTION_ENTRY":
        evidence = data.get("evidence", {})
        if not isinstance(evidence, dict):
            errors.append("probable entry requires evidence object")
            return errors
        if not evidence.get("has_incoming_control_flow", False):
            errors.append("probable function classification made without control-flow evidence")
    return errors


def validate_no_mutation_markers(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    markers = data.get("mutations_reported", [])
    if not isinstance(markers, list):
        errors.append("mutations_reported must be a list")
        return errors
    if len(markers) > 0:
        errors.append("existing project mutation is reported: %s" % markers)
    # Also check boundary_features for mutation claims
    bf = data.get("boundary_features", {})
    if isinstance(bf, dict) and bf.get("existing_project_mutation") is True:
        errors.append("boundary_features reports existing project mutation")
    return errors


def validate_nearest_functions_empty(data: Dict[str, Any]) -> List[str]:
    """Nearest-function result must be handled explicitly (null allowed, not missing)."""
    errors: List[str] = []
    nf = data.get("nearest_functions", {})
    if not isinstance(nf, dict):
        errors.append("nearest_functions must be an object")
        return errors
    for key in ("previous", "next"):
        if key not in nf:
            errors.append("nearest_functions missing key: %s" % key)
    return errors


def validate_deterministic(output_path: Path) -> List[str]:
    """Deterministic output: re-serialization must be byte-identical when sorted keys."""
    errors: List[str] = []
    try:
        data = load_json(output_path)
        serialized = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)
        # Re-parse and re-serialize to confirm stability
        reparsed = json.loads(serialized)
        serialized2 = json.dumps(reparsed, indent=2, sort_keys=True, ensure_ascii=True)
        if serialized != serialized2:
            errors.append("output is not deterministic under re-serialization")
    except Exception as e:
        errors.append("determinism check failed: %s" % e)
    return errors


def validate(data: Dict[str, Any], output_path: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    errors.extend(validate_top_level_keys(data))
    errors.extend(validate_target(data))
    errors.extend(validate_window(data))
    errors.extend(validate_raw_bytes(data))
    errors.extend(validate_instruction_inventory(data))
    errors.extend(validate_addresses_sorted(data))
    errors.extend(validate_classification(data))
    errors.extend(validate_probable_entry_requires_flow(data))
    errors.extend(validate_no_mutation_markers(data))
    errors.extend(validate_nearest_functions_empty(data))
    errors.extend(validate_deterministic(output_path))
    return len(errors) == 0, errors


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: validate_boundary.py <collector_output.json>", file=sys.stderr)
        return 2
    output_path = Path(argv[1])
    if not output_path.exists():
        print("FAIL: collector output not found: %s" % output_path, file=sys.stderr)
        return 1
    try:
        data = load_json(output_path)
    except Exception as e:
        print("FAIL: cannot parse JSON: %s" % e, file=sys.stderr)
        return 1
    ok, errors = validate(data, output_path)
    if ok:
        print("PASS: all validation gates satisfied")
        return 0
    print("FAIL: %d validation error(s)" % len(errors), file=sys.stderr)
    for e in errors:
        print("  - %s" % e, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
