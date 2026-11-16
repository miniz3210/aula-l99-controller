#!/usr/bin/env python3
"""Offline validator for V92SharedStateCollector JSON output.

Fail-closed validator. Reads the deterministic JSON document produced by
V92SharedStateCollector (Ghidra 12.1.4) and enforces the Session B invariants.

Read-only: never modifies the input JSON or any firmware artifact.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

LOADED_START = 0x60000000
LOADED_END = 0x6004C933

EXPECTED_ADDRESSES: List[str] = [
    "0x00821528", "0x600450A8", "0x600450B0", "0x600450B4",
    "0x600450BC", "0x0086CF28", "0x0086DF28",
]

EXPECTED_ADDRESSES_SET: Set[str] = set(EXPECTED_ADDRESSES)

ALLOWED_DIRECTIONS = {
    "READ", "WRITE", "READ_WRITE", "ADDRESS_TAKEN", "PARAMETER",
    "COMPUTED_CALL", "UNKNOWN",
}

ALLOWED_CLASSIFICATIONS = {
    "CALLBACK_POINTER", "BUFFER_POINTER", "DATA_POINTER", "LENGTH_VALUE",
    "MODE_OR_STATE", "COMMAND_VALUE", "QUEUE_OR_INDEX", "UNKNOWN",
}

ALLOWED_CONFIDENCE = {
    "CONFIRMED", "PROBABLE", "UNRESOLVED", "INSUFFICIENT_EVIDENCE",
}

TOP_LEVEL_FIELDS = [
    "schema", "program_identity", "memory_range", "requested_states",
    "access_records", "callback_chains", "initializer_candidates",
    "shared_function_matrix", "classification_summary", "validation_summary",
]

REQUESTED_STATE_FIELDS = [
    "requested_address", "normalized_address", "address_space",
    "address_classification", "memory_block_name", "initialized_status",
    "block_readable", "block_writable", "block_executable",
    "raw_bytes", "raw_byte_start_address", "raw_byte_count",
    "incoming_references", "outgoing_references", "source_instruction",
    "source_function", "reference_type", "inferred_access_direction",
    "inferred_access_width", "preceding_instruction", "following_instruction",
    "containing_function", "referenced_by_0x60049D98",
    "referenced_by_0x60049E5C", "referenced_by_0x60044FEC",
    "referenced_by_another_function", "write_or_initializer_candidates",
    "initializer_candidate_addresses",
    "load_to_register_to_call_evidence", "bounded_decompiler_snippet",
    "evidence_backed_state_classification", "confidence",
    "exact_supporting_evidence",
]

ACCESS_RECORD_FIELDS = [
    "requested_state_address", "source_instruction", "source_function",
    "reference_type", "access_direction", "access_width_evidence",
]

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
    require_keys(program_identity, ["program", "image_base", "image_end"],
                 "program_identity")
    if not program_identity.get("program"):
        fail("program identity missing program name")
    try:
        normalize_address(program_identity.get("image_base"))
        normalize_address(program_identity.get("image_end"))
    except ValueError:
        fail("program identity has malformed image_base/image_end")


def validate_memory_range(memory_range: Dict[str, Any]) -> None:
    require_keys(memory_range, ["loaded_start", "loaded_end", "size_bytes"],
                 "memory_range")
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


def validate_address_classification(value: Any, where: str) -> None:
    allowed = {"LOADED_FIRMWARE", "RAM_OR_EXTERNAL_SPACE",
               "OUTSIDE_LOADED_MEMORY", "UNRESOLVED"}
    if value not in allowed:
        fail(f"{where} invalid address_classification: {value!r}")


def validate_direction(value: Any, where: str) -> None:
    if value not in ALLOWED_DIRECTIONS:
        fail(f"{where} invalid access_direction: {value!r}")


def validate_classification(value: Any, where: str) -> None:
    if value not in ALLOWED_CLASSIFICATIONS:
        fail(f"{where} invalid state classification: {value!r}")


def validate_confidence(value: Any, where: str) -> None:
    if value not in ALLOWED_CONFIDENCE:
        fail(f"{where} invalid confidence: {value!r}")


def is_stack_address(addr: int, expected: Set[str]) -> bool:
    # Stack-space exclusion applies to requested-state rows. The three
    # externally-requested states 0x00821528, 0x0086CF28, 0x0086DF28 lie in the
    # 0x008XXXXX range but are legitimate requested global-state addresses, not
    # stack addresses. Any other address in stack space is excluded.
    norm = f"0x{addr:08X}"
    if norm in expected:
        return False
    return 0x00800000 <= addr <= 0x0087FFFF


def validate_requested_states(states: List[Dict[str, Any]]) -> None:
    if not isinstance(states, list):
        fail("requested_states is not a list")
        return

    seen: Set[str] = set()
    found: Set[str] = set()

    for row in states:
        if not isinstance(row, dict):
            fail("requested_states entry is not an object")
            continue

        require_keys(row, REQUESTED_STATE_FIELDS, "requested_state row")

        addr_raw = row.get("requested_address")
        norm_raw = row.get("normalized_address")
        try:
            addr = normalize_address(addr_raw)
            norm = normalize_address(norm_raw)
        except ValueError:
            fail(f"requested state has malformed address: {addr_raw!r}/{norm_raw!r}")
            continue

        norm_hex = f"0x{norm:08X}"
        found.add(norm_hex)
        if norm_hex in seen:
            fail(f"duplicate requested state address: {norm_hex}")
        seen.add(norm_hex)

        validate_address_classification(row.get("address_classification"),
                                        f"requested state {norm_hex}")
        validate_direction(row.get("inferred_access_direction"),
                           f"requested state {norm_hex}")
        validate_classification(row.get("evidence_backed_state_classification"),
                                f"requested state {norm_hex}")
        validate_confidence(row.get("confidence"),
                            f"requested state {norm_hex}")

        # Stack references excluded
        if is_stack_address(addr, EXPECTED_ADDRESSES_SET):
            fail(f"requested state {norm_hex} is a stack address")

        # Source function nullable only when explicitly unresolved
        src_func = row.get("source_function")
        if src_func is None and row.get("reference_type") not in ("null", None, "UNRESOLVED"):
            fail(f"requested state {norm_hex} null source_function without unresolved reference")

        # Raw bytes availability explicit
        if "raw_bytes_available" not in row:
            fail(f"requested state {norm_hex} missing raw_bytes_available")

    missing = [a for a in EXPECTED_ADDRESSES if a not in found]
    if missing:
        fail(f"missing requested states: {missing}")
    extra = [s for s in sorted(found) if s not in set(EXPECTED_ADDRESSES)]
    if extra:
        fail(f"unexpected requested states present: {extra}")
    if len(states) != len(EXPECTED_ADDRESSES):
        fail(f"requested state count {len(states)} != expected {len(EXPECTED_ADDRESSES)}")

    # Deterministic sorting
    addrs = []
    for row in states:
        try:
            addrs.append(normalize_address(row.get("normalized_address")))
        except ValueError:
            pass
    if addrs != sorted(addrs):
        fail("requested states not sorted deterministically by address")


def validate_access_records(records: List[Dict[str, Any]]) -> None:
    if not isinstance(records, list):
        fail("access_records is not a list")
        return
    for row in records:
        if not isinstance(row, dict):
            fail("access_records entry is not an object")
            continue
        require_keys(row, ACCESS_RECORD_FIELDS, "access_record row")
        validate_direction(row.get("access_direction"), "access record")
        width = row.get("access_width_evidence")
        if width is not None and width != "UNKNOWN" and not isinstance(width, str):
            fail(f"access record has invalid access_width_evidence: {width!r}")


def validate_callback_pointer_load_to_call(doc: Dict[str, Any]) -> None:
    chains = doc.get("callback_chains", [])
    if not isinstance(chains, list):
        return
    for chain in chains:
        if not isinstance(chain, dict):
            continue
        dest = chain.get("callback_destination", {})
        if not isinstance(dest, dict):
            continue
        classification = dest.get("classification")
        if classification == "CONFIRMED_CALLBACK_CHAIN":
            has_func = dest.get("destination_has_recovered_function") is True
            valid_ins = dest.get("destination_has_valid_instruction") is True
            if not (has_func and valid_ins):
                fail("callback chain marked CONFIRMED_CALLBACK_CHAIN without "
                     "recovered function and valid instruction (load-to-call evidence missing)")


def validate_no_display_specific_without_evidence(doc: Dict[str, Any]) -> None:
    states = doc.get("requested_states", [])
    if not isinstance(states, list):
        return
    for row in states:
        classification = row.get("evidence_backed_state_classification")
        evidence = row.get("exact_supporting_evidence", [])
        if classification in ("CALLBACK_POINTER", "BUFFER_POINTER", "DATA_POINTER",
                              "LENGTH_VALUE", "MODE_OR_STATE", "COMMAND_VALUE",
                              "QUEUE_OR_INDEX"):
            if not isinstance(evidence, list) or len(evidence) == 0:
                fail(f"state {row.get('requested_address')} classified as "
                     f"{classification} without address-level evidence")


def validate_shared_function_matrix(matrix: Dict[str, Any]) -> None:
    if not isinstance(matrix, dict):
        fail("shared_function_matrix is not an object")
        return
    funcs = matrix.get("primary_functions", [])
    if not isinstance(funcs, list) or len(funcs) < 3:
        fail("shared_function_matrix must include all three relevant functions")


def validate_initializer_explicit(doc: Dict[str, Any]) -> None:
    states = doc.get("requested_states", [])
    if not isinstance(states, list):
        return
    for row in states:
        candidates = row.get("write_or_initializer_candidates", [])
        if not isinstance(candidates, list):
            fail(f"state {row.get('requested_address')} missing write_or_initializer_candidates")


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

    require_keys(doc, TOP_LEVEL_FIELDS, "top-level")

    validate_program_identity(doc.get("program_identity", {}))
    validate_memory_range(doc.get("memory_range", {}))
    validate_requested_states(doc.get("requested_states", []))
    validate_access_records(doc.get("access_records", []))
    validate_callback_pointer_load_to_call(doc)
    validate_no_display_specific_without_evidence(doc)
    validate_shared_function_matrix(doc.get("shared_function_matrix", {}))
    validate_initializer_explicit(doc)

    return len(VALIDATION_ERRORS) == 0


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_shared_state.py <collected_json>")
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
