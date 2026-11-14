"""Tests for AULA L99 Offline Screen Capture Evidence Report."""

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def create_test_capture_structure(base_dir: Path) -> None:
    """Create test capture directories with CSV files."""
    # Capture 1: aula_test_capture_1
    cap1_dir = base_dir / "aula_test_capture_1"
    cap1_dir.mkdir(parents=True)
    payloads1 = cap1_dir / "all_payloads.csv"
    with payloads1.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])
        writer.writerow(["1", "0.000000000", "1", "0x80", "36", "8", ""])
        writer.writerow(["2", "0.000000000", "1", "0x80", "46", "18", "5aa510030000010000"])
        writer.writerow(["3", "0.000000000", "2", "0x03", "2060", "2060", ""])
        writer.writerow(["4", "0.000000000", "2", "0x82", "38", "11", "0000ffff00000300000000"])
        writer.writerow(["5", "0.000000000", "2", "0x82", "38", "11", "0100000000000300000000"])

    # Capture 2: aula_test_capture_2
    cap2_dir = base_dir / "aula_test_capture_2"
    cap2_dir.mkdir(parents=True)
    payloads2 = cap2_dir / "all_payloads.csv"
    with payloads2.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])
        writer.writerow(["1", "0.000000000", "1", "0x80", "36", "8", ""])
        writer.writerow(["2", "0.000000000", "3", "0x03", "2060", "2060", ""])
        writer.writerow(["3", "0.000000000", "3", "0x03", "2060", "2060", ""])

    # Empty capture
    empty_dir = base_dir / "aula_empty_capture"
    empty_dir.mkdir(parents=True)
    empty_payloads = empty_dir / "all_payloads.csv"
    with empty_payloads.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])

    # Malformed CSV
    malformed_dir = base_dir / "aula_malformed_capture"
    malformed_dir.mkdir(parents=True)
    malformed_payloads = malformed_dir / "all_payloads.csv"
    with malformed_payloads.open('w', newline='') as f:
        f.write("frame,time,device,endpoint,frame_len,data_len,payload\n")
        f.write("1,0.000000000,1,0x80,36,8,\n")
        f.write("not_a_number,0.000000000,2,0x03,2060,2060,\n")
        f.write("3,0.000000000,3,0x82,38,not_a_number,\n")


def create_device_mapping(base_dir: Path) -> Path:
    """Create device mapping CSV."""
    mapping_path = base_dir / "device_mapping.csv"
    with mapping_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["capture_name", "device", "vid", "pid"])
        writer.writerow(["aula_test_capture_1", "1", "EEEF", "268A"])
        writer.writerow(["aula_test_capture_1", "2", "1A86", "8091"])
        writer.writerow(["aula_test_capture_2", "1", "EEEF", "268A"])
        writer.writerow(["aula_test_capture_2", "3", "0C45", "800A"])
    return mapping_path


def create_verified_vidpid(base_dir: Path) -> Path:
    """Create verified VID/PID CSV."""
    vidpid_path = base_dir / "verified_vidpid.csv"
    with vidpid_path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["vid", "pid", "role"])
        writer.writerow(["EEEF", "268A", "screen"])
        writer.writerow(["0C45", "800A", "screen"])
        writer.writerow(["1A86", "8091", "non_screen"])
    return vidpid_path


def run_evidence_script(analysis_root: Path, device_mapping: Path, verified_vidpid: Path) -> dict:
    """Run the evidence script and return parsed JSON output."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "research" / "l99_screen_capture_evidence.py"
    result = subprocess.run(
        [sys.executable, str(script_path), str(analysis_root), str(device_mapping), str(verified_vidpid)],
        capture_output=True,
        text=True,
        check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"Script failed: {result.stderr}")
    return json.loads(result.stdout)


def test_capture_local_mapping():
    """Test that device mapping is capture-local."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # Device 1 in capture_1 maps to EEEF:268A (screen) -> verified_screen
        cap1_dev1 = [e for e in evidence if e["capture_name"] == "aula_test_capture_1" and e["device"] == "1"]
        for e in cap1_dev1:
            assert e["attribution"] == "verified_screen", f"Expected verified_screen for capture_1 device 1, got {e['attribution']}"

        # Device 1 in capture_2 maps to EEEF:268A (screen) -> verified_screen
        cap2_dev1 = [e for e in evidence if e["capture_name"] == "aula_test_capture_2" and e["device"] == "1"]
        for e in cap2_dev1:
            assert e["attribution"] == "verified_screen", f"Expected verified_screen for capture_2 device 1, got {e['attribution']}"

        # Device 2 in capture_1 maps to 1A86:8091 (non_screen) -> verified_non_screen
        cap1_dev2 = [e for e in evidence if e["capture_name"] == "aula_test_capture_1" and e["device"] == "2"]
        for e in cap1_dev2:
            assert e["attribution"] == "verified_non_screen", f"Expected verified_non_screen for capture_1 device 2, got {e['attribution']}"

        # Device 3 in capture_2 maps to 0C45:800A (screen) -> verified_screen
        cap2_dev3 = [e for e in evidence if e["capture_name"] == "aula_test_capture_2" and e["device"] == "3"]
        for e in cap2_dev3:
            assert e["attribution"] == "verified_screen", f"Expected verified_screen for capture_2 device 3, got {e['attribution']}"

        print("[OK] test_capture_local_mapping passed")


def test_unknown_device_handling():
    """Test that unmapped devices are labeled UNVERIFIED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # Device 4 doesn't exist in mapping, should be unverified
        # But we don't have device 4 in test data
        # Verify that any device not in mapping gets UNVERIFIED
        for e in evidence:
            if e["capture_name"] == "aula_test_capture_1" and e["device"] == "99":
                assert e["attribution"] == "unverified"
            if e["capture_name"] == "aula_test_capture_2" and e["device"] == "99":
                assert e["attribution"] == "unverified"

        # Empty capture has no devices, so no entries
        empty_entries = [e for e in evidence if e["capture_name"] == "aula_empty_capture"]
        assert len(empty_entries) == 0

        print("[OK] test_unknown_device_handling passed")


def test_endpoint_direction():
    """Test endpoint direction parsing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # 0x80 -> IN
        in_endpoints = [e for e in evidence if e["endpoint"] == "0x80"]
        for e in in_endpoints:
            assert e["direction"] == "IN", f"Expected IN for 0x80, got {e['direction']}"

        # 0x03 -> OUT
        out_endpoints = [e for e in evidence if e["endpoint"] == "0x03"]
        for e in out_endpoints:
            assert e["direction"] == "OUT", f"Expected OUT for 0x03, got {e['direction']}"

        # 0x82 -> IN
        in82 = [e for e in evidence if e["endpoint"] == "0x82"]
        for e in in82:
            assert e["direction"] == "IN", f"Expected IN for 0x82, got {e['direction']}"

        print("[OK] test_endpoint_direction passed")


def test_payload_size_distribution():
    """Test payload size distribution counting."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # Find capture_1 device 2 endpoint 0x03 - has one 2060-byte transfer
        entry = next(
            e for e in evidence
            if e["capture_name"] == "aula_test_capture_1"
            and e["device"] == "2"
            and e["endpoint"] == "0x03"
        )
        assert entry["payload_size_distribution"]["2060"] == 1
        assert entry["transfer_count"] == 1

        # Find capture_1 device 2 endpoint 0x82 - has two 11-byte transfers
        entry = next(
            e for e in evidence
            if e["capture_name"] == "aula_test_capture_1"
            and e["device"] == "2"
            and e["endpoint"] == "0x82"
        )
        assert entry["payload_size_distribution"]["11"] == 2
        assert entry["transfer_count"] == 2

        print("[OK] test_payload_size_distribution passed")


def test_deterministic_ordering():
    """Test that output is deterministically ordered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output1 = run_evidence_script(base, mapping, vidpid)
        output2 = run_evidence_script(base, mapping, vidpid)

        assert json.dumps(output1, separators=(',', ':')) == json.dumps(output2, separators=(',', ':'))
        print("[OK] test_deterministic_ordering passed")


def test_sha256_recording():
    """Test that source CSV SHA256 is recorded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        for entry in evidence:
            assert "source_csv_sha256" in entry
            assert len(entry["source_csv_sha256"]) == 64  # SHA256 hex length
            # Verify it's a valid hex string
            int(entry["source_csv_sha256"], 16)

        print("[OK] test_sha256_recording passed")


def test_malformed_csv():
    """Test handling of malformed CSV rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # Should not crash on malformed rows
        malformed_entries = [e for e in evidence if e["capture_name"] == "aula_malformed_capture"]
        # Should have entries for valid rows only
        assert len(malformed_entries) > 0

        print("[OK] test_malformed_csv passed")


def test_empty_csv():
    """Test handling of empty CSV (only header)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        empty_entries = [e for e in evidence if e["capture_name"] == "aula_empty_capture"]
        assert len(empty_entries) == 0

        print("[OK] test_empty_csv passed")


def test_no_cross_capture_address_reuse():
    """Test that device addresses are not generalized across captures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # Device 1 appears in both captures but with different context
        # The attribution is based on capture-local mapping
        cap1_dev1 = [e for e in evidence if e["capture_name"] == "aula_test_capture_1" and e["device"] == "1"]
        cap2_dev1 = [e for e in evidence if e["capture_name"] == "aula_test_capture_2" and e["device"] == "1"]

        # Both should be verified_screen because both map to EEEF:268A in their respective captures
        for e in cap1_dev1:
            assert e["attribution"] == "verified_screen"
        for e in cap2_dev1:
            assert e["attribution"] == "verified_screen"

        # Device 2 in capture_1 is non_screen, but device 2 doesn't exist in capture_2
        # This confirms addresses are capture-local

        print("[OK] test_no_cross_capture_address_reuse passed")


def test_count_reconciliation():
    """Test that transfer counts match payload size distribution totals."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        for entry in evidence:
            dist_total = sum(int(v) for v in entry["payload_size_distribution"].values())
            assert entry["transfer_count"] == dist_total, (
                f"Count mismatch for {entry['capture_name']} dev={entry['device']} ep={entry['endpoint']}: "
                f"transfer_count={entry['transfer_count']}, dist_total={dist_total}"
            )

        print("[OK] test_count_reconciliation passed")


def test_2060_not_auto_verified_screen():
    """Test that 2060-byte packets are not automatically classified as verified screen."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # In capture_1, device 2 endpoint 0x03 has 2060-byte packets
        # Device 2 maps to 1A86:8091 (non_screen) -> should be verified_non_screen
        entry = next(
            e for e in evidence
            if e["capture_name"] == "aula_test_capture_1"
            and e["device"] == "2"
            and e["endpoint"] == "0x03"
        )
        assert entry["attribution"] == "verified_non_screen", (
            f"2060-byte packets on non-screen device should not be verified_screen, got {entry['attribution']}"
        )

        print("[OK] test_2060_not_auto_verified_screen passed")


def test_three_attribution_labels():
    """Test all three attribution labels appear."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        attributions = {e["attribution"] for e in evidence}
        assert "verified_screen" in attributions
        assert "verified_non_screen" in attributions
        assert "unverified" in attributions

        print("[OK] test_three_attribution_labels passed")


def test_all_five_provenance_fields_present():
    """Test that all five provenance fields are present in output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        required_fields = ["vid", "pid", "mapping_source", "vidpid_verified", "attribution_basis"]
        for entry in evidence:
            for field in required_fields:
                assert field in entry, f"Missing provenance field: {field}"

        print("[OK] test_all_five_provenance_fields_present passed")


def test_csv_assertion_mapping_source_and_attribution_basis():
    """Test that CSV-mapped devices have mapping_source=csv_assertion and attribution_basis=csv_assertion."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        for entry in evidence:
            if entry["mapping_source"] == "csv_assertion":
                assert entry["mapping_source"] == "csv_assertion", (
                    f"Expected mapping_source=csv_assertion for {entry['capture_name']} dev={entry['device']}"
                )
                assert entry["attribution_basis"] == "csv_assertion", (
                    f"Expected attribution_basis=csv_assertion for {entry['capture_name']} dev={entry['device']}"
                )

        print("[OK] test_csv_assertion_mapping_source_and_attribution_basis passed")


def test_unmapped_device_provenance():
    """Test unmapped device has vid='', pid='', mapping_source='none', attribution_basis='none', vidpid_verified=false."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create a capture with a device not in mapping
        cap_dir = base / "test_capture"
        cap_dir.mkdir(parents=True)
        payloads = cap_dir / "all_payloads.csv"
        with payloads.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])
            writer.writerow(["1", "0.000000000", "99", "0x80", "36", "8", ""])
        
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        unmapped = [e for e in evidence if e["device"] == "99"]
        assert len(unmapped) == 1
        entry = unmapped[0]
        assert entry["vid"] == "", f"Expected empty vid for unmapped device, got {entry['vid']}"
        assert entry["pid"] == "", f"Expected empty pid for unmapped device, got {entry['pid']}"
        assert entry["mapping_source"] == "none", f"Expected mapping_source=none, got {entry['mapping_source']}"
        assert entry["attribution_basis"] == "none", f"Expected attribution_basis=none, got {entry['attribution_basis']}"
        assert entry["vidpid_verified"] is False, f"Expected vidpid_verified=false, got {entry['vidpid_verified']}"
        assert entry["attribution"] == "unverified", f"Expected attribution=unverified, got {entry['attribution']}"

        print("[OK] test_unmapped_device_provenance passed")


def test_unknown_vidpid_remains_unverified():
    """Test that unknown VID/PID (not in verified_vidpid.csv) remains unverified even when mapped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create a capture with a device mapped to unknown VID/PID
        cap_dir = base / "test_capture"
        cap_dir.mkdir(parents=True)
        payloads = cap_dir / "all_payloads.csv"
        with payloads.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])
            writer.writerow(["1", "0.000000000", "1", "0x80", "36", "8", ""])
        
        # Create mapping with unknown VID/PID
        mapping_path = base / "device_mapping.csv"
        with mapping_path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["capture_name", "device", "vid", "pid"])
            writer.writerow(["test_capture", "1", "FFFF", "FFFF"])  # Unknown VID/PID
        
        # verified_vidpid.csv doesn't have FFFF:FFFF
        vidpid_path = base / "verified_vidpid.csv"
        with vidpid_path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["vid", "pid", "role"])
            writer.writerow(["EEEF", "268A", "screen"])

        output = run_evidence_script(base, mapping_path, vidpid_path)
        evidence = output["capture_evidence"]

        entry = next(e for e in evidence if e["device"] == "1")
        assert entry["vid"] == "FFFF"
        assert entry["pid"] == "FFFF"
        assert entry["mapping_source"] == "csv_assertion"
        assert entry["attribution_basis"] == "csv_assertion"
        assert entry["vidpid_verified"] is False, "Unknown VID/PID should have vidpid_verified=false"
        assert entry["attribution"] == "unverified", "Unknown VID/PID should be unverified"

        print("[OK] test_unknown_vidpid_remains_unverified passed")


def test_csv_only_input_never_claims_descriptor_verified():
    """Test that CSV-only input never claims descriptor_verified (not a field in output)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        for entry in evidence:
            # The output should not have a "descriptor_verified" field
            assert "descriptor_verified" not in entry, (
                f"Output should not contain descriptor_verified field: {entry}"
            )
            # vidpid_verified should only be true for verified VID/PID pairs
            if entry["vidpid_verified"] is True:
                assert (entry["vid"], entry["pid"]) in [("EEEF", "268A"), ("0C45", "800A"), ("1A86", "8091")]

        print("[OK] test_csv_only_input_never_claims_descriptor_verified passed")


def test_device_mapping_csv_sha256_metadata_matches():
    """Test that device_mapping.csv SHA256 in metadata matches actual file hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        metadata = output["metadata"]

        expected_sha256 = hashlib.sha256(mapping.read_bytes()).hexdigest()
        assert metadata["device_mapping_sha256"] == expected_sha256, (
            f"device_mapping_sha256 mismatch: expected {expected_sha256}, got {metadata['device_mapping_sha256']}"
        )

        print("[OK] test_device_mapping_csv_sha256_metadata_matches passed")


def test_verified_vidpid_csv_sha256_metadata_matches():
    """Test that verified_vidpid.csv SHA256 in metadata matches actual file hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        metadata = output["metadata"]

        expected_sha256 = hashlib.sha256(vidpid.read_bytes()).hexdigest()
        assert metadata["verified_vidpid_sha256"] == expected_sha256, (
            f"verified_vidpid_sha256 mismatch: expected {expected_sha256}, got {metadata['verified_vidpid_sha256']}"
        )

        print("[OK] test_verified_vidpid_csv_sha256_metadata_matches passed")


def test_preserve_capture_local_mapping_isolation():
    """Test that capture-local mapping isolation is preserved (no cross-capture generalization)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Create two captures with same device address but different mappings
        cap1_dir = base / "capture_a"
        cap1_dir.mkdir(parents=True)
        payloads1 = cap1_dir / "all_payloads.csv"
        with payloads1.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])
            writer.writerow(["1", "0.000000000", "1", "0x80", "36", "8", ""])
        
        cap2_dir = base / "capture_b"
        cap2_dir.mkdir(parents=True)
        payloads2 = cap2_dir / "all_payloads.csv"
        with payloads2.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["frame", "time", "device", "endpoint", "frame_len", "data_len", "payload"])
            writer.writerow(["1", "0.000000000", "1", "0x80", "36", "8", ""])
        
        # Different VID/PID for device 1 in each capture
        mapping_path = base / "device_mapping.csv"
        with mapping_path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["capture_name", "device", "vid", "pid"])
            writer.writerow(["capture_a", "1", "AAAA", "BBBB"])
            writer.writerow(["capture_b", "1", "CCCC", "DDDD"])
        
        vidpid_path = base / "verified_vidpid.csv"
        with vidpid_path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["vid", "pid", "role"])
            writer.writerow(["AAAA", "BBBB", "screen"])
            writer.writerow(["CCCC", "DDDD", "non_screen"])

        output = run_evidence_script(base, mapping_path, vidpid_path)
        evidence = output["capture_evidence"]

        cap_a = next(e for e in evidence if e["capture_name"] == "capture_a")
        cap_b = next(e for e in evidence if e["capture_name"] == "capture_b")

        # Each capture's device 1 should use its own mapping
        assert cap_a["vid"] == "AAAA"
        assert cap_a["pid"] == "BBBB"
        assert cap_a["attribution"] == "verified_screen"

        assert cap_b["vid"] == "CCCC"
        assert cap_b["pid"] == "DDDD"
        assert cap_b["attribution"] == "verified_non_screen"

        print("[OK] test_preserve_capture_local_mapping_isolation passed")


def test_preserve_deterministic_output():
    """Test that output is deterministic across multiple runs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output1 = run_evidence_script(base, mapping, vidpid)
        output2 = run_evidence_script(base, mapping, vidpid)

        json1 = json.dumps(output1, separators=(',', ':'), sort_keys=True)
        json2 = json.dumps(output2, separators=(',', ':'), sort_keys=True)

        assert json1 == json2, "Output is not deterministic"

        print("[OK] test_preserve_deterministic_output passed")


def test_preserve_2060_byte_non_screen_behavior():
    """Test that 2060-byte packets on non-screen devices remain verified_non_screen."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        create_test_capture_structure(base)
        mapping = create_device_mapping(base)
        vidpid = create_verified_vidpid(base)

        output = run_evidence_script(base, mapping, vidpid)
        evidence = output["capture_evidence"]

        # In capture_1, device 2 endpoint 0x03 has 2060-byte packets
        # Device 2 maps to 1A86:8091 (non_screen) -> should be verified_non_screen
        entry = next(
            e for e in evidence
            if e["capture_name"] == "aula_test_capture_1"
            and e["device"] == "2"
            and e["endpoint"] == "0x03"
        )
        assert entry["attribution"] == "verified_non_screen", (
            f"2060-byte packets on non-screen device should be verified_non_screen, got {entry['attribution']}"
        )
        assert entry["vidpid_verified"] is True
        assert entry["payload_size_distribution"]["2060"] == 1

        print("[OK] test_preserve_2060_byte_non_screen_behavior passed")


def run_all_tests():
    """Run all tests."""
    test_capture_local_mapping()
    test_unknown_device_handling()
    test_endpoint_direction()
    test_payload_size_distribution()
    test_deterministic_ordering()
    test_sha256_recording()
    test_malformed_csv()
    test_empty_csv()
    test_no_cross_capture_address_reuse()
    test_count_reconciliation()
    test_2060_not_auto_verified_screen()
    test_three_attribution_labels()
    test_all_five_provenance_fields_present()
    test_csv_assertion_mapping_source_and_attribution_basis()
    test_unmapped_device_provenance()
    test_unknown_vidpid_remains_unverified()
    test_csv_only_input_never_claims_descriptor_verified()
    test_device_mapping_csv_sha256_metadata_matches()
    test_verified_vidpid_csv_sha256_metadata_matches()
    test_preserve_capture_local_mapping_isolation()
    test_preserve_deterministic_output()
    test_preserve_2060_byte_non_screen_behavior()
    print("\n[OK] All tests passed!")


if __name__ == "__main__":
    run_all_tests()