#!/usr/bin/env python3
"""Offline validator for V92ComputedCallCollector JSON output.

Fail-closed validator. Reads the deterministic JSON document produced by
V92ComputedCallCollector and enforces the Session A invariants.

Read-only: never modifies the input JSON or any firmware artifact.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

EXPECTED_CALL_SITES: List[str] = [
    "0x60049D9C", "0x60049E12", "0x60049E14", "0x60049E6A", "0x60049EEA",
    "0x60049EF0", "0x60049F7E", "0x60045016", "0x60045034",
]

EXPECTED_POINTER_CELLS: List[str] = [
    "0x60049F88", "0x60049F94", "0x60049F98", "0x600450BC",
]

LOADED_START = 0x60000000
LOADED_END = 0x6004C933

OUT_OF_RANGE_DESTINATIONS: Set[int] = {0x6004D08C, 0x6004D140, 0x60053524}
IN_RANGE_RESOLVED_TARGET = 0x60044FEC

ALLOWED_CONFIDENCE = {
    "DIRECT_IN_RANGE_CALL",
    "POINTER_CELL_IN_RANGE_CALL",
    "INDIRECT_CALLBACK_CALL",
    "OUT_OF_RANGE_COMPUTED_INTERPRETATION",
    "POSSIBLE_MCORE_REFERENCE_ANALYSIS_ERROR",
    "UNRESOLVED",
}

VALIDATION_ERRORS: List[str] = []


def fail(msg: str) -> None:
    VALIDATION_ERRORS.append(msg)


def normalize_address(value: Any) -> int:
    """Normalize an address to an int. Fail closed on malformed input."""
    if value is None:
        fail(f"address is null/missing: {value!r}")
        raise ValueError("null address")
    if isinstance(value, bool):
        fail(f"address is boolean, not a number: {value!r}")
        raise ValueError("boolean address")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s.lower().startswith("0x"):
            s = s[2:]
        try:
            return int(s, 16)
        except ValueError:
            fail(f"malformed address string: {value!r}")
            raise
    fail(f"address has unsupported type: {type(value).__name__} value={value!r}")
    raise ValueError("unsupported address type")


def in_loaded_memory(addr: int) -> bool:
    return LOADED_START <= addr <= LOADED_END


def require_keys(obj: Dict[str, Any], keys: List[str], where: str) -> None:
    for k in keys:
        if k not in obj:
            fail(f"missing key '{k}' in {where}")


def validate_program_identity(program_identity: Dict[str, Any]) -> None:
    require_keys(program_identity, ["program", "image_base", "image_end"], "program_identity")
    if not program_identity.get("program"):
        fail("program identity missing program name")
    try:
        normalize_address(program_identity.get("image_base"))
        normalize_address(program_identity.get("image_end"))
    except ValueError:
        fail("program identity has malformed image_base/image_end")


def validate_memory_range(memory_range: Dict[str, Any]) -> None:
    require_keys(memory_range, ["loaded_start", "loaded_end", "size_bytes"], "memory_range")
    try:
        start = normalize_address(memory_range.get("loaded_start"))
        end = normalize_address(memory_range.get("loaded_end"))
    except ValueError:
        fail("memory range has malformed addresses")
        return
    if start != LOADED_START:
        fail(f"loaded_start {start:#x} != expected {LOADED_START:#x}")
    if end != LOADED_END:
        fail(f"loaded_end {end:#x} != expected {LOADED_END:#x}")


def validate_call_sites(call_sites: List[Dict[str, Any]]) -> None:
    if not isinstance(call_sites, list):
        fail("call_sites is not a list")
        return

    seen: Set[str] = set()
    found_sites: Set[str] = set()

    for row in call_sites:
        if not isinstance(row, dict):
            fail("call_sites entry is not an object")
            continue

        site_raw = row.get("call_site_address")
        try:
            site_addr = normalize_address(site_raw)
        except ValueError:
            fail(f"call site has malformed address: {site_raw!r}")
            continue

        site_hex = f"0x{site_addr:08X}"
        found_sites.add(site_hex)

        if site_hex in seen:
            fail(f"duplicate call site row: {site_hex}")
        seen.add(site_hex)

        # Required fields present
        require_keys(row, [
            "raw_instruction_bytes", "instruction_text", "mnemonic",
            "operands", "instruction_flows", "references",
            "computed_destination", "computed_destination_in_loaded_memory",
            "recovered_function_at_destination", "valid_instruction_at_destination",
            "ghidra_reports_computed_call", "confidence_classification",
            "derivation_evidence",
        ], f"call site {site_hex}")

        # Raw bytes must be present and non-empty
        raw = row.get("raw_instruction_bytes")
        if not isinstance(raw, str) or len(raw) == 0:
            fail(f"call site {site_hex} missing raw instruction bytes")

        # instruction text present
        if not isinstance(row.get("instruction_text"), str) or len(row.get("instruction_text", "")) == 0:
            fail(f"call site {site_hex} missing instruction text")

        # operands typed
        operands = row.get("operands")
        if not isinstance(operands, list):
            fail(f"call site {site_hex} operands is not a list")
        else:
            for op in operands:
                if not isinstance(op, dict):
                    fail(f"call site {site_hex} operand is not an object")
                    continue
                if "type" not in op:
                    fail(f"call site {site_hex} operand missing type")
                if op.get("type") not in {
                    "register", "scalar", "memory address", "code address",
                    "data address", "external or out-of-range address", "other",
                }:
                    fail(f"call site {site_hex} operand has invalid type: {op.get('type')!r}")

        # Computed destination evidence source required
        computed = row.get("computed_destination")
        if computed is not None:
            try:
                computed_addr = normalize_address(computed)
            except ValueError:
                fail(f"call site {site_hex} computed destination malformed: {computed!r}")
                continue
            # If computed destination is out of range, it must NOT be marked confirmed/direct
            if not in_loaded_memory(computed_addr):
                conf = row.get("confidence_classification")
                if conf in ("DIRECT_IN_RANGE_CALL", "POINTER_CELL_IN_RANGE_CALL"):
                    fail(
                        f"call site {site_hex} out-of-range destination {computed} "
                        f"marked as confirmed call: {conf}"
                    )

        # Confidence must be allowed
        conf = row.get("confidence_classification")
        if conf not in ALLOWED_CONFIDENCE:
            fail(f"call site {site_hex} invalid confidence: {conf!r}")

        # Pointer cell raw bytes required when a pointer cell is loaded
        pcrb = row.get("pointer_cell_raw_bytes")
        pcell = row.get("pointer_cell_loaded_near_call")
        if pcell is not None and (not isinstance(pcrb, str) or len(pcrb) == 0):
            fail(f"call site {site_hex} has pointer cell {pcell} but missing raw bytes")

    # Exactly nine requested call-site rows
    missing = [s for s in EXPECTED_CALL_SITES if s not in found_sites]
    if missing:
        fail(f"missing call sites: {missing}")
    extra = [s for s in sorted(found_sites) if s not in set(EXPECTED_CALL_SITES)]
    if extra:
        fail(f"unexpected call sites present: {extra}")
    if len(call_sites) != len(EXPECTED_CALL_SITES):
        fail(
            f"call site count {len(call_sites)} != expected {len(EXPECTED_CALL_SITES)}"
        )

    # Deterministic sorting by address
    addrs = []
    for row in call_sites:
        try:
            addrs.append(normalize_address(row.get("call_site_address")))
        except ValueError:
            pass
    if addrs != sorted(addrs):
        fail("call sites not sorted deterministically by address")


def validate_pointer_cells(pointer_cells: List[Dict[str, Any]]) -> None:
    if not isinstance(pointer_cells, list):
        fail("pointer_cells is not a list")
        return

    seen: Set[str] = set()
    found: Set[str] = set()

    for row in pointer_cells:
        if not isinstance(row, dict):
            fail("pointer_cells entry is not an object")
            continue

        cell_raw = row.get("cell_address")
        try:
            cell_addr = normalize_address(cell_raw)
        except ValueError:
            fail(f"pointer cell has malformed address: {cell_raw!r}")
            continue

        cell_hex = f"0x{cell_addr:08X}"
        found.add(cell_hex)
        if cell_hex in seen:
            fail(f"duplicate pointer cell row: {cell_hex}")
        seen.add(cell_hex)

        require_keys(row, [
            "loaded_memory_status", "memory_block_name",
            "raw_bytes_minus8_plus15", "aligned_reads",
            "decoded_16_le", "decoded_16_be",
            "decoded_32_le", "decoded_32_be",
            "references_to_cell", "instructions_reading_cell",
            "cell_behavior",
        ], f"pointer cell {cell_hex}")

        # Raw bytes required
        raw = row.get("raw_bytes_minus8_plus15")
        if not isinstance(raw, str) or len(raw) == 0:
            fail(f"pointer cell {cell_hex} missing raw bytes")

    missing = [s for s in EXPECTED_POINTER_CELLS if s not in found]
    if missing:
        fail(f"missing pointer cells: {missing}")
    extra = [s for s in sorted(found) if s not in set(EXPECTED_POINTER_CELLS)]
    if extra:
        fail(f"unexpected pointer cells present: {extra}")
    if len(pointer_cells) != len(EXPECTED_POINTER_CELLS):
        fail(
            f"pointer cell count {len(pointer_cells)} != expected {len(EXPECTED_POINTER_CELLS)}"
        )

    addrs = []
    for row in pointer_cells:
        try:
            addrs.append(normalize_address(row.get("cell_address")))
        except ValueError:
            pass
    if addrs != sorted(addrs):
        fail("pointer cells not sorted deterministically by address")


def validate_computed_destinations(dests: List[Dict[str, Any]]) -> None:
    if not isinstance(dests, list):
        fail("computed_destinations is not a list")
        return
    for row in dests:
        if not isinstance(row, dict):
            fail("computed_destinations entry is not an object")
            continue
        dest_raw = row.get("computed_destination")
        try:
            dest_addr = normalize_address(dest_raw)
        except ValueError:
            fail(f"computed destination malformed: {dest_raw!r}")
            continue
        # Evidence source required
        sources = row.get("evidence_source_call_sites")
        if not isinstance(sources, list) or len(sources) == 0:
            fail(f"computed destination {dest_raw} missing evidence source call sites")
        # Out-of-range destinations flagged
        if not in_loaded_memory(dest_addr):
            if dest_addr in OUT_OF_RANGE_DESTINATIONS:
                continue  # expected out-of-range
            fail(f"unexpected out-of-range computed destination: {dest_raw}")


def validate_summary(summary: Dict[str, Any], call_sites: List[Dict[str, Any]],
                     pointer_cells: List[Dict[str, Any]]) -> None:
    if not isinstance(summary, dict):
        fail("validation_summary is not an object")
        return
    if not summary.get("all_call_sites_present"):
        fail("summary: all_call_sites_present is false")
    if not summary.get("all_pointer_cells_present"):
        fail("summary: all_pointer_cells_present is false")


def validate_file(path: Path) -> bool:
    VALIDATION_ERRORS.clear()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"FAIL: cannot read {path}: {e}")
        return False

    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON in {path}: {e}")
        return False

    if not isinstance(doc, dict):
        print("FAIL: top-level JSON is not an object")
        return False

    require_keys(doc, ["schema", "program_identity", "memory_range",
                       "call_sites", "pointer_cells", "computed_destinations",
                       "validation_summary"], "top-level")

    validate_program_identity(doc.get("program_identity", {}))
    validate_memory_range(doc.get("memory_range", {}))
    validate_call_sites(doc.get("call_sites", []))
    validate_pointer_cells(doc.get("pointer_cells", []))
    validate_computed_destinations(doc.get("computed_destinations", []))
    validate_summary(doc.get("validation_summary", {}),
                     doc.get("call_sites", []), doc.get("pointer_cells", []))

    # Rule: out-of-range destination cannot be classified as direct confirmed call
    for row in doc.get("call_sites", []):
        site_raw = row.get("call_site_address")
        try:
            site_addr = normalize_address(site_raw)
        except ValueError:
            continue
        computed_raw = row.get("computed_destination")
        if computed_raw is None:
            continue
        try:
            computed_addr = normalize_address(computed_raw)
        except ValueError:
            continue
        if not in_loaded_memory(computed_addr):
            conf = row.get("confidence_classification")
            if conf in ("DIRECT_IN_RANGE_CALL", "POINTER_CELL_IN_RANGE_CALL"):
                fail(
                    f"call site {site_raw}: out-of-range destination {computed_raw} "
                    f"classified as {conf}"
                )

    # Rule: COMPUTED_CALL alone does not establish confirmation
    for row in doc.get("call_sites", []):
        site_raw = row.get("call_site_address")
        ghidra_cc = row.get("ghidra_reports_computed_call")
        conf = row.get("confidence_classification")
        if ghidra_cc is True and conf in ("DIRECT_IN_RANGE_CALL", "POINTER_CELL_IN_RANGE_CALL"):
            func = row.get("recovered_function_at_destination")
            insn = row.get("valid_instruction_at_destination")
            if func is None and not insn:
                fail(
                    f"call site {site_raw}: COMPUTED_CALL alone used to confirm "
                    f"destination without function or valid instruction"
                )

    # Rule: addresses 0x6004D08C, 0x6004D140, 0x60053524 outside loaded range
    for dst in OUT_OF_RANGE_DESTINATIONS:
        if in_loaded_memory(dst):
            fail(f"destination {dst:#x} incorrectly considered in loaded memory")

    # Rule: resolved target 0x60044FEC can remain in range
    if not in_loaded_memory(IN_RANGE_RESOLVED_TARGET):
        fail(f"resolved target {IN_RANGE_RESOLVED_TARGET:#x} not in loaded memory")

    return len(VALIDATION_ERRORS) == 0


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_computed_calls.py <collected_json>")
        return 2
    path = Path(argv[1])
    ok = validate_file(path)
    if ok:
        print(f"PASS: {path} validated successfully (fail-closed, {len(VALIDATION_ERRORS)} errors)")
        return 0
    print(f"FAIL: {path} had {len(VALIDATION_ERRORS)} validation error(s):")
    for err in VALIDATION_ERRORS:
        print(f"  - {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
