#!/usr/bin/env python3
"""Offline tests for validate_computed_calls.py.

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
import validate_computed_calls as mod

EXPECTED_CALL_SITES = sorted([
    "0x60049D9C", "0x60049E12", "0x60049E14", "0x60049E6A", "0x60049EEA",
    "0x60049EF0", "0x60049F7E", "0x60045016", "0x60045034",
], key=lambda a: int(a, 16))
EXPECTED_POINTER_CELLS = sorted([
    "0x60049F88", "0x60049F94", "0x60049F98", "0x600450BC",
], key=lambda a: int(a, 16))


def base_document():
    return {
        "schema": "V92ComputedCallCollector.v1",
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
        "call_sites": [],
        "pointer_cells": [],
        "computed_destinations": [],
        "validation_summary": {
            "call_site_count": 0,
            "pointer_cell_count": 0,
            "computed_in_loaded_memory": 0,
            "computed_out_of_loaded_memory": 0,
            "ghidra_computed_call_count": 0,
            "all_call_sites_present": False,
            "all_pointer_cells_present": False,
        },
    }


def call_site_row(addr, computed="0x60044FEC", in_range=True, conf="DIRECT_IN_RANGE_CALL",
                  raw="DEADBEEF", text="jsri 0x60044FEC", mnemonic="jsri"):
    return {
        "caller_function_entry": "0x60049D98",
        "caller_function_name": "FUN_60049d98",
        "call_site_address": addr,
        "raw_instruction_bytes": raw,
        "instruction_text": text,
        "mnemonic": mnemonic,
        "operands": [
            {
                "operand_index": 0,
                "display_text": "0x60044FEC",
                "type": "code address",
                "type_code": "CODE_ADDRESS",
                "values": [
                    {
                        "kind": "code address",
                        "address": "0x60044FEC",
                        "unsigned_value": 0x60044FEC,
                        "value": "0x60044FEC",
                        "in_loaded_memory": True,
                        "memory_block": "ram",
                    }
                ],
            }
        ],
        "instruction_flows": [
            {
                "kind": "address",
                "address": "0x60044FEC",
                "in_loaded_memory": True,
            }
        ],
        "references": [
            {
                "reference_type": "COMPUTED_CALL",
                "is_call": True,
                "is_computed_call": True,
                "from_address": addr,
                "to_address": computed,
                "to_in_loaded_memory": in_range,
            }
        ],
        "pointer_cell_loaded_near_call": None,
        "pointer_cell_raw_bytes": None,
        "pointer_cell_decoded_16_le": None,
        "pointer_cell_decoded_16_be": None,
        "pointer_cell_decoded_32_le": None,
        "pointer_cell_decoded_32_be": None,
        "pointer_cell_memory_block": None,
        "computed_destination": computed,
        "computed_destination_in_loaded_memory": in_range,
        "recovered_function_at_destination": "0x60044FEC",
        "recovered_function_name": "FUN_60044fec",
        "valid_instruction_at_destination": True,
        "ghidra_reports_computed_call": True,
        "confidence_classification": conf,
        "derivation_evidence": ["instruction_text:jsri 0x60044FEC"],
    }


def pointer_cell_row(addr, raw="00112233445566778899AABBCCDDEEFF00112233445566778899AABBCCDDEEFF"):
    return {
        "cell_address": addr,
        "loaded_memory_status": True,
        "memory_block_name": "ram",
        "block_start": "0x60000000",
        "block_end": "0x6004C933",
        "raw_bytes_minus8_plus15": raw,
        "aligned_reads": {},
        "decoded_16_le": "0x2211",
        "decoded_16_be": "0x1122",
        "decoded_32_le": "0x44332211",
        "decoded_32_be": "0x11223344",
        "references_to_cell": [],
        "instructions_reading_cell": [],
        "cell_behavior": "literal",
    }


def write_tmp(doc):
    tmp = tempfile.mkdtemp()
    path = Path(os.path.join(tmp, "collected_computed_calls.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


class RequirementTests(unittest.TestCase):
    """Tests mapped to the 13 numbered requirements."""

    def test_1_nine_call_site_rows_required(self):
        doc = base_document()
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertTrue(mod.validate_file(path))

    def test_2_four_pointer_cell_rows_required(self):
        doc = base_document()
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertTrue(mod.validate_file(path))

    def test_3_duplicate_rows_rejected(self):
        doc = base_document()
        rows = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        rows.append(copy.deepcopy(call_site_row("0x60049D9C")))
        doc["call_sites"] = rows
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("duplicate" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_4_missing_rows_rejected(self):
        doc = base_document()
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES[:-1]]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = False
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("missing call sites" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_5_out_of_range_destination_not_confirmed_call(self):
        doc = base_document()
        row = call_site_row("0x60049D9C", computed="0x6004D08C", in_range=False,
                            conf="DIRECT_IN_RANGE_CALL")
        doc["call_sites"] = [row] + [call_site_row(a) for a in EXPECTED_CALL_SITES[1:]]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("out-of-range" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_6_pointer_cell_raw_bytes_required(self):
        doc = base_document()
        cell = pointer_cell_row("0x60049F88")
        cell["raw_bytes_minus8_plus15"] = ""
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [cell] + [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS[1:]]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("raw bytes" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_7_loaded_memory_range_classification(self):
        self.assertTrue(mod.in_loaded_memory(0x60044FEC))
        self.assertFalse(mod.in_loaded_memory(0x6004D08C))
        self.assertFalse(mod.in_loaded_memory(0x6004D140))
        self.assertFalse(mod.in_loaded_memory(0x60053524))
        self.assertTrue(mod.in_loaded_memory(0x60000000))
        self.assertTrue(mod.in_loaded_memory(0x6004C933))
        self.assertFalse(mod.in_loaded_memory(0x6004C934))

    def test_8_deterministic_sorting(self):
        doc = base_document()
        # Unsorted call sites
        addrs = list(reversed(EXPECTED_CALL_SITES))
        doc["call_sites"] = [call_site_row(a) for a in addrs]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("sorted" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_9_address_normalization(self):
        self.assertEqual(mod.normalize_address("0x60044FEC"), 0x60044FEC)
        self.assertEqual(mod.normalize_address(0x60044FEC), 0x60044FEC)
        self.assertEqual(mod.normalize_address("60044FEC"), 0x60044FEC)
        with self.assertRaises((ValueError, TypeError)):
            mod.normalize_address(None)
        with self.assertRaises(ValueError):
            mod.normalize_address("not-hex")
        with self.assertRaises(ValueError):
            mod.normalize_address(True)

    def test_10_empty_evidence_rejected(self):
        doc = base_document()
        dest = {
            "computed_destination": "0x60044FEC",
            "in_loaded_memory": True,
            "recovered_function_entry": None,
            "recovered_function_name": None,
            "valid_instruction": False,
            "memory_block": None,
            "evidence_source_call_sites": [],
        }
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["computed_destinations"] = [dest]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("evidence source" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_11_computed_call_alone_does_not_confirm(self):
        doc = base_document()
        row = call_site_row("0x60049D9C", computed="0x60044FEC", in_range=True,
                            conf="DIRECT_IN_RANGE_CALL")
        # No recovered function and no valid instruction -> COMPUTED_CALL alone insufficient
        row["recovered_function_at_destination"] = None
        row["valid_instruction_at_destination"] = False
        doc["call_sites"] = [row] + [call_site_row(a) for a in EXPECTED_CALL_SITES[1:]]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("COMPUTED_CALL alone" in e for e in mod.VALIDATION_ERRORS))

    def test_12_valid_resolved_target_in_range(self):
        doc = base_document()
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        dest = {
            "computed_destination": "0x60044FEC",
            "in_loaded_memory": True,
            "recovered_function_entry": "0x60044FEC",
            "recovered_function_name": "FUN_60044fec",
            "valid_instruction": True,
            "memory_block": "ram",
            "evidence_source_call_sites": ["0x60049D9C"],
        }
        doc["computed_destinations"] = [dest]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertTrue(mod.validate_file(path))

    def test_13_out_of_range_destinations_marked_outside(self):
        doc = base_document()
        rows = []
        for i, a in enumerate(EXPECTED_CALL_SITES):
            computed = ["0x6004D08C", "0x6004D140", "0x60053524"][i % 3]
            rows.append(call_site_row(a, computed=computed, in_range=False,
                                      conf="OUT_OF_RANGE_COMPUTED_INTERPRETATION"))
        doc["call_sites"] = rows
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertTrue(mod.validate_file(path))

    # Additional structural tests

    def test_malformed_address_rejected(self):
        doc = base_document()
        row = call_site_row("0x60049D9C")
        row["call_site_address"] = "not-hex"
        doc["call_sites"] = [row]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_missing_program_identity_rejected(self):
        doc = base_document()
        doc.pop("program_identity")
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_computed_destination_without_evidence_rejected(self):
        doc = base_document()
        dest = {
            "computed_destination": "0x60044FEC",
            "in_loaded_memory": True,
            "evidence_source_call_sites": [],
        }
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["computed_destinations"] = [dest]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_duplicate_pointer_cells_rejected(self):
        doc = base_document()
        cells = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        cells.append(copy.deepcopy(cells[0]))
        doc["call_sites"] = [call_site_row(a) for a in EXPECTED_CALL_SITES]
        doc["pointer_cells"] = cells
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))
        self.assertTrue(any("duplicate" in e.lower() for e in mod.VALIDATION_ERRORS))

    def test_invalid_confidence_classification_rejected(self):
        doc = base_document()
        row = call_site_row("0x60049D9C", conf="NOT_A_REAL_CLASS")
        doc["call_sites"] = [row] + [call_site_row(a) for a in EXPECTED_CALL_SITES[1:]]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))

    def test_missing_raw_instruction_bytes_rejected(self):
        doc = base_document()
        row = call_site_row("0x60049D9C")
        row["raw_instruction_bytes"] = ""
        doc["call_sites"] = [row] + [call_site_row(a) for a in EXPECTED_CALL_SITES[1:]]
        doc["pointer_cells"] = [pointer_cell_row(a) for a in EXPECTED_POINTER_CELLS]
        doc["validation_summary"]["all_call_sites_present"] = True
        doc["validation_summary"]["all_pointer_cells_present"] = True
        path = write_tmp(doc)
        self.assertFalse(mod.validate_file(path))


if __name__ == "__main__":
    unittest.main()
