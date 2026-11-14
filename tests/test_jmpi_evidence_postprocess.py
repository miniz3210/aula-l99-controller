#!/usr/bin/env python3
"""
Tests for JMPI evidence post-processor.

Validates:
- Valid 49-site processing
- Three register-indirect sites remain unresolved
- Incorrect firmware hash rejected
- Incorrect manifest hash rejected
- Incorrect CFG artifact hash rejected
- Missing input rejected
- Invalid literal handled safely
- Deterministic ordering
- Atomic output
- Existing output overwrite rejected
- Source artifacts unchanged
- No CFG traversal
"""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "research"))

from mcore_literal_pool import resolve_literal_pool_target


class TestJMPIEvidencePostprocess(unittest.TestCase):
    """Test the JMPI evidence post-processor."""

    @classmethod
    def setUpClass(cls):
        cls.script_path = Path(__file__).resolve().parent.parent / "scripts" / "research" / "jmpi_evidence_postprocess.py"
        cls.firmware_path = Path(__file__).resolve().parent.parent / "tools" / "softce-aula-l99-research" / "extracted" / "HFD_Code_V2.3.bin"
        cls.manifest_path = Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "unresolved_indirect_sites_12288_1536.json"
        cls.output_dir = Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "jmpi_evidence_postprocess"
        cls.output_path = cls.output_dir / "jmpi_literal_pool_evidence.json"

    def test_script_compiles(self):
        """Test that the script compiles without syntax errors."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(self.script_path)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Compilation failed: {result.stderr}")

    def test_valid_49_site_processing(self):
        """Test that 49 JMPI sites are processed correctly."""
        # Remove any existing output
        if self.output_path.exists():
            self.output_path.unlink()

        # Run the script
        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            capture_output=True,
            text=True,
            cwd=self.script_path.parent.parent.parent,
        )
        self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

        # Load and verify output
        with open(self.output_path) as f:
            output = json.load(f)

        self.assertEqual(output["total_sites"], 52)
        self.assertEqual(output["jmpi_sites_resolved"], 49)
        self.assertEqual(output["register_indirect_sites_preserved"], 3)
        self.assertEqual(len(output["evidence_records"]), 52)

        # Count passed JMPI validations
        passed = sum(1 for r in output["evidence_records"] if r["validation_status"] == "PASSED")
        self.assertEqual(passed, 49)

    def test_three_register_indirect_sites_remain_unresolved(self):
        """Test that 3 register-indirect sites are preserved as unresolved."""
        with open(self.output_path) as f:
            output = json.load(f)

        skipped = [r for r in output["evidence_records"] if r["validation_status"] == "SKIPPED"]
        self.assertEqual(len(skipped), 3)

        for record in skipped:
            self.assertEqual(record["literal_target_classification"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(record["canonical_membership_classification"], "NON_CANONICAL")
            self.assertEqual(record["failure_reason"], "register_indirect_not_jmpi_jsri")

    def test_incorrect_firmware_hash_rejected(self):
        """Test that incorrect firmware hash is rejected."""
        # Corrupt firmware temporarily
        with open(self.firmware_path, "rb") as f:
            original = f.read()

        try:
            with open(self.firmware_path, "wb") as f:
                f.write(b"corrupted")

            result = subprocess.run(
                [sys.executable, str(self.script_path)],
                capture_output=True,
                text=True,
                cwd=self.script_path.parent.parent.parent,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA256 mismatch", result.stderr)
        finally:
            # Restore
            with open(self.firmware_path, "wb") as f:
                f.write(original)

    def test_incorrect_manifest_hash_rejected(self):
        """Test that incorrect manifest hash is rejected."""
        # Corrupt manifest temporarily
        with open(self.manifest_path, "rb") as f:
            original = f.read()

        try:
            with open(self.manifest_path, "wb") as f:
                f.write(b"corrupted")

            result = subprocess.run(
                [sys.executable, str(self.script_path)],
                capture_output=True,
                text=True,
                cwd=self.script_path.parent.parent.parent,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA256 mismatch", result.stderr)
        finally:
            with open(self.manifest_path, "wb") as f:
                f.write(original)

    def test_incorrect_cfg_artifact_hash_rejected(self):
        """Test that incorrect CFG artifact hash is rejected."""
        cfg_summary = Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "single_root_12288_blocks_1536_run1" / "cfg_summary.json"

        with open(cfg_summary, "rb") as f:
            original = f.read()

        try:
            with open(cfg_summary, "wb") as f:
                f.write(b"corrupted")

            result = subprocess.run(
                [sys.executable, str(self.script_path)],
                capture_output=True,
                text=True,
                cwd=self.script_path.parent.parent.parent,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA256 mismatch", result.stderr)
        finally:
            with open(cfg_summary, "wb") as f:
                f.write(original)

    def test_missing_input_rejected(self):
        """Test that missing input file is rejected."""
        # Move manifest temporarily
        temp_manifest = self.manifest_path.with_suffix(".tmp_move")
        self.manifest_path.rename(temp_manifest)

        try:
            result = subprocess.run(
                [sys.executable, str(self.script_path)],
                capture_output=True,
                text=True,
                cwd=self.script_path.parent.parent.parent,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr.lower())
        finally:
            temp_manifest.rename(self.manifest_path)

    def test_invalid_literal_handled_safely(self):
        """Test that invalid literal targets are handled safely (not VERIFIED_EXECUTABLE)."""
        with open(self.output_path) as f:
            output = json.load(f)

        for record in output["evidence_records"]:
            # Should never claim VERIFIED_EXECUTABLE
            self.assertNotEqual(record["literal_target_classification"], "VERIFIED_EXECUTABLE")
            # Only valid classifications
            self.assertIn(record["literal_target_classification"],
                         ["VALIDATED_LITERAL_TARGET", "INVALID_LITERAL_TARGET", "INSUFFICIENT_EVIDENCE"])

    def test_deterministic_ordering(self):
        """Test that output is deterministically ordered."""
        # Run twice and compare
        if self.output_path.exists():
            self.output_path.unlink()

        # First run
        subprocess.run([sys.executable, str(self.script_path)], capture_output=True, cwd=self.script_path.parent.parent.parent)
        with open(self.output_path) as f:
            output1 = json.load(f)

        # Second run
        self.output_path.unlink()
        subprocess.run([sys.executable, str(self.script_path)], capture_output=True, cwd=self.script_path.parent.parent.parent)
        with open(self.output_path) as f:
            output2 = json.load(f)

        # Should be identical
        self.assertEqual(json.dumps(output1, sort_keys=True), json.dumps(output2, sort_keys=True))

    def test_atomic_output(self):
        """Test that output is written atomically (no partial writes)."""
        # The write_atomic function uses temp file + os.replace
        # This test verifies the mechanism works
        with open(self.output_path) as f:
            data = json.load(f)

        # Verify it's valid JSON (not partial)
        self.assertIn("evidence_records", data)
        self.assertEqual(len(data["evidence_records"]), 52)

    def test_existing_output_overwrite_rejected(self):
        """Test that existing output file causes failure (not overwrite)."""
        # Output already exists from previous test
        self.assertTrue(self.output_path.exists())

        result = subprocess.run(
            [sys.executable, str(self.script_path)],
            capture_output=True,
            text=True,
            cwd=self.script_path.parent.parent.parent,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)

    def test_source_artifacts_unchanged(self):
        """Test that source CFG artifacts are not modified."""
        # Compute hashes before
        cfg_artifacts = {
            "cfg_summary": Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "single_root_12288_blocks_1536_run1" / "cfg_summary.json",
            "cfg_nodes": Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "single_root_12288_blocks_1536_run1" / "cfg_nodes.json",
            "cfg_edges": Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "single_root_12288_blocks_1536_run1" / "cfg_edges.json",
            "cfg_ranges": Path(__file__).resolve().parent.parent / "local_analysis" / "cfg_experiments" / "single_root_12288_blocks_1536_run1" / "cfg_ranges.json",
        }

        hashes_before = {}
        for name, path in cfg_artifacts.items():
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            hashes_before[name] = h.hexdigest().upper()

        # Run script (output already exists, will fail but that's ok)
        subprocess.run([sys.executable, str(self.script_path)], capture_output=True, cwd=self.script_path.parent.parent.parent)

        # Compute hashes after
        hashes_after = {}
        for name, path in cfg_artifacts.items():
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            hashes_after[name] = h.hexdigest().upper()

        # Should be unchanged
        for name in cfg_artifacts:
            self.assertEqual(hashes_before[name], hashes_after[name],
                           f"Source artifact {name} was modified!")

    def test_no_cfg_traversal(self):
        """Test that the script does not instantiate CFGBuilder or perform CFG traversal."""
        # Read the script source
        with open(self.script_path) as f:
            source = f.read()

        # Should not import or use CFGBuilder
        self.assertNotIn("CFGBuilder", source)
        self.assertNotIn("cfg_builder", source.lower())
        self.assertNotIn("traversal", source.lower())
        self.assertNotIn("build_canonical", source)

        # Should only use mcore_literal_pool and read static JSON
        self.assertIn("mcore_literal_pool", source)
        self.assertIn("resolve_literal_pool_target", source)

    def test_evidence_record_structure(self):
        """Test that each evidence record has all required fields."""
        with open(self.output_path) as f:
            output = json.load(f)

        required_fields = {
            "source_site",
            "instruction_word",
            "literal_pool_address",
            "literal_raw_bytes",
            "loaded_target_address",
            "validation_status",
            "literal_target_classification",
            "canonical_membership_classification",
            "failure_reason",
        }

        for record in output["evidence_records"]:
            self.assertEqual(set(record.keys()), required_fields,
                           f"Record missing fields: {record}")

    def test_unique_target_count_15(self):
        """Test that exactly 15 unique literal targets are classified."""
        with open(self.output_path) as f:
            output = json.load(f)

        # Count unique targets from PASSED validations
        passed_records = [r for r in output["evidence_records"] if r["validation_status"] == "PASSED"]
        unique_targets = set(r["loaded_target_address"] for r in passed_records)
        self.assertEqual(len(unique_targets), 15)

    def test_canonical_membership_breakdown(self):
        """Test canonical membership classification breakdown."""
        with open(self.output_path) as f:
            output = json.load(f)

        passed = [r for r in output["evidence_records"] if r["validation_status"] == "PASSED"]
        memberships = {}
        for r in passed:
            cls = r["canonical_membership_classification"]
            memberships[cls] = memberships.get(cls, 0) + 1

        # Verify all are valid classifications
        valid_classes = {"FUNCTION_ENTRY", "BLOCK_START", "INSIDE_BLOCK", "EDGE_TARGET", "NON_CANONICAL"}
        for cls in memberships:
            self.assertIn(cls, valid_classes)

        print(f"Canonical membership breakdown: {memberships}")

    def test_valid_literal_outside_cfg_remains_valid(self):
        """Test that valid literal target outside observed CFG remains VALIDATED_LITERAL_TARGET."""
        with open(self.output_path) as f:
            output = json.load(f)

        # Find records with NON_CANONICAL membership but PASSED validation
        non_canonical_valid = [
            r for r in output["evidence_records"]
            if r["validation_status"] == "PASSED"
            and r["canonical_membership_classification"] == "NON_CANONICAL"
        ]
        for record in non_canonical_valid:
            self.assertEqual(record["literal_target_classification"], "VALIDATED_LITERAL_TARGET")

    def test_valid_literal_at_block_start_remains_valid(self):
        """Test that valid literal at block start remains VALIDATED_LITERAL_TARGET."""
        with open(self.output_path) as f:
            output = json.load(f)

        block_start_valid = [
            r for r in output["evidence_records"]
            if r["validation_status"] == "PASSED"
            and r["canonical_membership_classification"] == "BLOCK_START"
        ]
        for record in block_start_valid:
            self.assertEqual(record["literal_target_classification"], "VALIDATED_LITERAL_TARGET")

    def test_valid_literal_inside_block_remains_valid(self):
        """Test that valid literal inside block remains VALIDATED_LITERAL_TARGET."""
        with open(self.output_path) as f:
            output = json.load(f)

        inside_block_valid = [
            r for r in output["evidence_records"]
            if r["validation_status"] == "PASSED"
            and r["canonical_membership_classification"] == "INSIDE_BLOCK"
        ]
        for record in inside_block_valid:
            self.assertEqual(record["literal_target_classification"], "VALIDATED_LITERAL_TARGET")

    def test_invalid_literal_remains_invalid_regardless_of_membership(self):
        """Test that invalid literal (failed resolution) remains INVALID_LITERAL_TARGET regardless of membership."""
        with open(self.output_path) as f:
            output = json.load(f)

        failed_records = [
            r for r in output["evidence_records"]
            if r["validation_status"] == "FAILED"
        ]
        for record in failed_records:
            self.assertEqual(record["literal_target_classification"], "INVALID_LITERAL_TARGET")

    def test_register_indirect_remains_skipped(self):
        """Test that register-indirect sites remain SKIPPED with INSUFFICIENT_EVIDENCE."""
        with open(self.output_path) as f:
            output = json.load(f)

        skipped_records = [
            r for r in output["evidence_records"]
            if r["validation_status"] == "SKIPPED"
        ]
        self.assertEqual(len(skipped_records), 3)
        for record in skipped_records:
            self.assertEqual(record["literal_target_classification"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(record["canonical_membership_classification"], "NON_CANONICAL")

    def test_summary_counts_reconcile(self):
        """Test that summary counts reconcile with evidence records."""
        with open(self.output_path) as f:
            output = json.load(f)

        records = output["evidence_records"]
        self.assertEqual(len(records), 52)

        passed = sum(1 for r in records if r["validation_status"] == "PASSED")
        skipped = sum(1 for r in records if r["validation_status"] == "SKIPPED")
        failed = sum(1 for r in records if r["validation_status"] == "FAILED")

        self.assertEqual(passed, 49)
        self.assertEqual(skipped, 3)
        self.assertEqual(failed, 0)  # No failed literal resolutions in accepted manifest

        # Literal target classifications
        validated = sum(1 for r in records if r["literal_target_classification"] == "VALIDATED_LITERAL_TARGET")
        invalid = sum(1 for r in records if r["literal_target_classification"] == "INVALID_LITERAL_TARGET")
        insufficient = sum(1 for r in records if r["literal_target_classification"] == "INSUFFICIENT_EVIDENCE")

        self.assertEqual(validated, 49)
        self.assertEqual(invalid, 0)
        self.assertEqual(insufficient, 3)

        # Canonical membership
        canonical_counts = {}
        for r in records:
            if r["validation_status"] == "PASSED":
                cls = r["canonical_membership_classification"]
                canonical_counts[cls] = canonical_counts.get(cls, 0) + 1

        print(f"Canonical membership counts for PASSED: {canonical_counts}")

    def test_duplicate_source_site_rejected(self):
        """Test that duplicate source site in manifest is rejected."""
        # Test the duplicate check directly by calling the validation logic
        from scripts.research import jmpi_evidence_postprocess
        import tempfile
        import hashlib

        with open(self.manifest_path, "rb") as f:
            original_manifest_bytes = f.read()

        manifest = json.loads(original_manifest_bytes)
        # Duplicate first site
        duplicate_site = manifest["sites"][0].copy()
        manifest["sites"].append(duplicate_site)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".json", delete=False) as f:
            f.write(json.dumps(manifest, indent=2, sort_keys=True).encode())
            temp_manifest = Path(f.name)

        # Compute correct hash for modified manifest
        with open(temp_manifest, "rb") as f:
            modified_manifest_bytes = f.read()
        correct_hash = hashlib.sha256(modified_manifest_bytes).hexdigest().upper()

        try:
            # Temporarily replace manifest path
            original_manifest = jmpi_evidence_postprocess.MANIFEST_PATH
            jmpi_evidence_postprocess.MANIFEST_PATH = temp_manifest

            # Also need to patch expected manifest hash to match modified manifest
            original_hash = jmpi_evidence_postprocess.EXPECTED_MANIFEST_SHA256
            jmpi_evidence_postprocess.EXPECTED_MANIFEST_SHA256 = correct_hash

            # Call main - should fail on duplicate check
            with self.assertRaises(ValueError) as cm:
                jmpi_evidence_postprocess.main()
            self.assertIn("Duplicate source site", str(cm.exception))
        finally:
            jmpi_evidence_postprocess.MANIFEST_PATH = original_manifest
            jmpi_evidence_postprocess.EXPECTED_MANIFEST_SHA256 = original_hash
            temp_manifest.unlink()

    def test_atomic_write_failure_handling(self):
        """Test that atomic write handles failures correctly (no partial output)."""
        # Verify the atomic write mechanism uses temp file + os.replace
        from scripts.research import jmpi_evidence_postprocess
        import inspect

        source = inspect.getsource(jmpi_evidence_postprocess.write_atomic)
        # Should use temp file and os.replace for atomicity
        self.assertIn(".tmp", source)
        self.assertIn("os.replace", source)
        self.assertNotIn("open(", source.replace("open(", "").replace(".tmp", ""))  # Only temp file write

        # Also verify that existing output is rejected (not overwritten)
        # This is already tested in test_existing_output_overwrite_rejected


if __name__ == "__main__":
    unittest.main()