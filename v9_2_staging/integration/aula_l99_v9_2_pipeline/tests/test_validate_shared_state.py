#!/usr/bin/env python3
"""Offline tests for validate_shared_state.py.

All fixtures are generated in-memory. No vendor firmware, Ghidra project, or
remote environment is required. The validator under test is read-only.
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "python"))
import validate_shared_state as mod

EXPECTED_ADDRESSES = sorted([
    "0x00821528", "0x600450A8", "0x600450B0", "0x600450B4",
    "0x600450BC", "0x0086CF28", "0x0086DF28",
], key=lambda a: int(a, 16))


def base_document():
    return {
        "schema": "V92SharedStateCollector.v1",
        "program_identity": {
            "program": "AulaL99V8",
            "domain": "HFD_Code_V2.3.bin",
            "language": "MCORE:LE:32:default",
            "compiler": "none",
            "image_base": "0x60000000",
            "image_end": "0x6004C933",
            "size_bytes": 313652,
        },
        "memory_range": {
            "loaded_start": "0x60000000",
            "loaded_end": "0x6004C933",
            "size_bytes": 313652,
            "memory_blocks": [],
        },
        "requested_states": [],
        "access_records": [],
        "callback_chains": [],
        "initializer_candidates": [],
        "shared_function_matrix": {
            "primary_functions": [
                {"function_entry": "0x60049D98", "function_name": "FUN_60049d98",
                 "instruction_count": 94, "incoming_reference_count": 15,
                 "references_requested_states": []},
                {"function_entry": "0x60049E5C", "function_name": "FUN_60049e5c",
                 "instruction_count": 148, "incoming_reference_count": 13,
                 "references_requested_states": []},
                {"function_entry": "0x60044FEC", "function_name": "FUN_60044fec",
                 "instruction_count": 38, "incoming_reference_count": 102,
                 "references_requested_states": []},
            ],
            "all_three_present": True,
        },
        "classification_summary": {
            "total_requested_states": 7,
            "classification_counts": {},
            "confidence_counts": {},
        },
        "validation_summary": {
            "requested_state_count": 7,
            "expected_requested_state_count": 7,
            "seven_requested_states_present": True,
            "no_duplicate_requested_address": True,
            "rows_deterministically_sorted": True,
            "program_identity_present": True,
            "memory_range_present": True,
            "stack_references_excluded": True,
            "code_addresses_not_ram_without_classification": True,
            "callback_pointer_requires_load_to_call_evidence": True,
            "no_display_specific_without_address_level_evidence": True,
            "shared_function_matrix_includes_three_functions": True,
            "missing_initializer_evidence_explicit": True,
            "fail_closed_validation_required": True,
        },
    }


def requested_state_row(addr, classification="DATA_POINTER", confidence="UNRESOLVED",
                        direction="READ", width="4", source_func="FUN_60044fec",
                        ref_type="READ", loaded=True, evidence=None):
    if evidence is None:
        evidence = [f"address:{addr}", "loaded:True", f"direction:{direction}"]
    return {
        "requested_address": addr,
        "normalized_address": addr,
        "address_space": "ram",
        "address_classification": "RAM_OR_EXTERNAL_SPACE",
        "memory_block_name": "ram",
        "initialized_status": "initialized",
        "block_readable": True,
        "block_writable": True,
        "block_executable": False,
        "raw_bytes": "00112233445566778899AABBCCDDEEFF",
        "raw_byte_start_address": "0x600450A0",
        "raw_byte_count": 24,
        "raw_bytes_available": True,
        "incoming_references": [],
        "outgoing_references": [],
        "source_instruction": "load 0x600450A8",
        "source_function": source_func,
        "reference_type": ref_type,
        "inferred_access_direction": direction,
        "inferred_access_width": width,
        "preceding_instruction": "null",
        "following_instruction": "null",
        "containing_function": source_func,
        "referenced_by_0x60049D98": False,
        "referenced_by_0x60049E5C": False,
        "referenced_by_0x60044FEC": False,
        "referenced_by_another_function": False,
        "write_or_initializer_candidates": [],
        "initializer_candidate_addresses": [],
        "load_to_register_to_call_evidence": "null",
        "bounded_decompiler_snippet": "null",
        "evidence_backed_state_classification": classification,
        "confidence": confidence,
        "exact_supporting_evidence": evidence,
    }


def write_tmp(doc):
    tmp = tempfile.mkdtemp()
    path = Path(os.path.join(tmp, "collected_shared_state.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


class RequirementTests(unittest.TestCase):
    """Tests mapped to the requirements."""

    def test_1_valid_document_passes(self):
        doc = base_document()
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        path = write_tmp(doc)
        self.assertTrue(mod.validate_file(path))

    def test_2_exactly_seven_requested_addresses_required(self):
        doc = base_document()
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES[:6]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("missing requested states" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_3_missing_address_rejected(self):
        doc = base_document()
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES if a != "0x600450BC"]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("0x600450BC" in e for e in mod.VALIDATION_ERRORS))

    def test_4_duplicate_address_rejected(self):
        doc = base_document()
        rows = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        rows.append(copy.deepcopy(requested_state_row("0x00821528")))
        doc["requested_states"] = rows
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("duplicate" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_5_address_normalization(self):
        self.assertEqual(mod.normalize_address("0x60044FEC"), 0x60044FEC)
        self.assertEqual(mod.normalize_address(0x60044FEC), 0x60044FEC)
        self.assertEqual(mod.normalize_address("60044FEC"), 0x60044FEC)
        with self.assertRaises((ValueError, TypeError)):
            mod.normalize_address(None)
        with self.assertRaises(ValueError):
            mod.normalize_address("not-hex")
        with self.assertRaises(ValueError):
            mod.normalize_address(True)

    def test_6_deterministic_state_row_sorting(self):
        doc = base_document()
        addrs = list(reversed(EXPECTED_ADDRESSES))
        doc["requested_states"] = [requested_state_row(a) for a in addrs]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("sorted" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_7_access_direction_validation(self):
        doc = base_document()
        row = requested_state_row("0x600450BC", direction="INVALID_DIRECTION")
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("access_direction" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_8_access_width_validation(self):
        doc = base_document()
        rec = {
            "requested_state_address": "0x600450BC",
            "source_instruction": "load 0x600450BC",
            "source_function": "FUN_60044fec",
            "reference_type": "READ",
            "access_direction": "READ",
            "access_width_evidence": 123,
        }
        doc["access_records"] = [rec]
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_9_stack_references_excluded(self):
        doc = base_document()
        row = requested_state_row("0x00821528")
        row["requested_address"] = "0x00821530"
        row["normalized_address"] = "0x00821530"
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("stack" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_10_code_address_misuse_rejected(self):
        doc = base_document()
        row = requested_state_row("0x60044FEC")
        row["address_classification"] = "RAM_OR_EXTERNAL_SPACE"
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        # Code address at 0x60044FEC (a function) classified as RAM without mixed/code classification
        self.assertFalse(mod.validate_file(path))

    def test_11_out_of_range_handling(self):
        doc = base_document()
        row = requested_state_row("0xFFFFFFFF")
        row["address_classification"] = "OUTSIDE_LOADED_MEMORY"
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("missing requested states" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_12_callback_classification_requires_load_to_call_evidence(self):
        doc = base_document()
        chain = {
            "callback_slot_address": "0x600450BC",
            "callback_destination": {
                "destination_address": "0x60053524",
                "destination_in_loaded_memory": False,
                "destination_has_recovered_function": False,
                "destination_has_valid_instruction": False,
                "classification": "CONFIRMED_CALLBACK_CHAIN",
            },
        }
        doc["callback_chains"] = [chain]
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("load-to-call" in e.lower() or "CONFIRMED_CALLBACK_CHAIN" in e for e in mod.VALIDATION_ERRORS))

    def test_13_shared_primary_function_matrix_required(self):
        doc = base_document()
        doc["shared_function_matrix"] = {"primary_functions": []}
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("three relevant functions" in e for e in mod.VALIDATION_ERRORS))

    def test_14_missing_initializer_handled_explicitly(self):
        doc = base_document()
        row = requested_state_row("0x600450BC")
        row["write_or_initializer_candidates"] = None
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_15_display_specific_claim_rejected_without_evidence(self):
        doc = base_document()
        row = requested_state_row("0x600450BC", classification="CALLBACK_POINTER", evidence=[])
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("without address-level evidence" in e for e in mod.VALIDATION_ERRORS))

    # Structural / additional tests

    def test_missing_program_identity_rejected(self):
        doc = base_document()
        doc.pop("program_identity")
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_missing_memory_range_rejected(self):
        doc = base_document()
        doc.pop("memory_range")
        doc["requested_states"] = [requested_state_row(a) for a in EXPECTED_ADDRESSES]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_invalid_state_classification_rejected(self):
        doc = base_document()
        row = requested_state_row("0x600450BC", classification="DISPLAY_BUFFER")
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_invalid_confidence_rejected(self):
        doc = base_document()
        row = requested_state_row("0x600450BC", confidence="NOT_A_REAL_CLASS")
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_null_address_rejected(self):
        doc = base_document()
        row = requested_state_row("0x600450BC")
        row["requested_address"] = None
        row["normalized_address"] = None
        doc["requested_states"] = [row] + [requested_state_row(a) for a in EXPECTED_ADDRESSES[1:]]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))


if __name__ == "__main__":
    unittest.main()
