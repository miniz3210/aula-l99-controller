#!/usr/bin/env python3
"""
Standalone read-only post-processor for JMPI literal-pool evidence.

Processes the 52 manifest sites from the accepted 12288/1536 CFG artifacts:
- 49 JMPI literal-pool sites (resolved via mcore_literal_pool.py)
- 3 register-indirect sites (preserved as unresolved)

Produces deterministic JSON evidence records with canonical membership classification.
"""

import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# Add research scripts to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcore_literal_pool import resolve_literal_pool_target, is_valid_jmpi_jsri_instruction

# Constants
FIRMWARE_PATH = Path(r"tools/softce-aula-l99-research/extracted/HFD_Code_V2.3.bin")
MANIFEST_PATH = Path("local_analysis/cfg_experiments/unresolved_indirect_sites_12288_1536.json")

# Accepted CFG artifact paths (from 12288/1536 experiment run1)
CFG_ARTIFACTS = {
    "cfg_summary": Path("local_analysis/cfg_experiments/single_root_12288_blocks_1536_run1/cfg_summary.json"),
    "cfg_nodes": Path("local_analysis/cfg_experiments/single_root_12288_blocks_1536_run1/cfg_nodes.json"),
    "cfg_edges": Path("local_analysis/cfg_experiments/single_root_12288_blocks_1536_run1/cfg_edges.json"),
    "cfg_ranges": Path("local_analysis/cfg_experiments/single_root_12288_blocks_1536_run1/cfg_ranges.json"),
}

# Expected SHA256 hashes (from handover doc and experiment outputs)
EXPECTED_FIRMWARE_SHA256 = "A76806ADA9648D2672BBEBEAD8A9BB396C0BC6F3A0A071E22E99001AC3359D03"
EXPECTED_MANIFEST_SHA256 = "804753EAB6AF92D034A2BFCD15374B7D1164D0E6E4DF5D64C24581E159A286BF"
EXPECTED_CFG_SUMMARY_SHA256 = "9BBE30E2F10A2FB49A77C76D79E30DB75C872909B1EE637DCA07027CB26AF592"
EXPECTED_CFG_NODES_SHA256 = "43D82BED3FFDEF1DDDD56D3E210953D325E00B7320197CA0D268F7B78AE5A4BE"
EXPECTED_CFG_EDGES_SHA256 = "B8667EE401281634C1F01C7C20CEE5CD13AB2677CBCFA52FCF8A5C8CFAE81838"
EXPECTED_CFG_RANGES_SHA256 = "82B4AC31817B7F899652EC0DF661E315D844BB9F8599C129B5602E30F2236144"

IMAGE_BASE = 0x60010000
FIRMWARE_SIZE = 313652
PROHIBITED_START = 0x60031198
PROHIBITED_END = 0x600315D0

OUTPUT_DIR = Path("local_analysis/cfg_experiments/jmpi_evidence_postprocess")
OUTPUT_PATH = OUTPUT_DIR / "jmpi_literal_pool_evidence.json"


def compute_sha256(path: Path) -> str:
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_json(path: Path) -> Any:
    """Load JSON from file."""
    with open(path, "r") as f:
        return json.load(f)


def validate_inputs() -> None:
    """Validate all input files exist and have correct hashes."""
    # Firmware
    if not FIRMWARE_PATH.exists():
        raise FileNotFoundError(f"Firmware not found: {FIRMWARE_PATH}")
    fw_hash = compute_sha256(FIRMWARE_PATH)
    if fw_hash != EXPECTED_FIRMWARE_SHA256:
        raise ValueError(f"Firmware SHA256 mismatch: expected {EXPECTED_FIRMWARE_SHA256}, got {fw_hash}")

    # Manifest
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST_PATH}")
    manifest_hash = compute_sha256(MANIFEST_PATH)
    if manifest_hash != EXPECTED_MANIFEST_SHA256:
        raise ValueError(f"Manifest SHA256 mismatch: expected {EXPECTED_MANIFEST_SHA256}, got {manifest_hash}")

    # CFG artifacts
    expected_hashes = {
        "cfg_summary": EXPECTED_CFG_SUMMARY_SHA256,
        "cfg_nodes": EXPECTED_CFG_NODES_SHA256,
        "cfg_edges": EXPECTED_CFG_EDGES_SHA256,
        "cfg_ranges": EXPECTED_CFG_RANGES_SHA256,
    }
    for name, expected in expected_hashes.items():
        path = CFG_ARTIFACTS[name]
        if not path.exists():
            raise FileNotFoundError(f"CFG artifact not found: {path}")
        actual = compute_sha256(path)
        if actual != expected:
            raise ValueError(f"CFG artifact {name} SHA256 mismatch: expected {expected}, got {actual}")


def load_canonical_addresses() -> Dict[str, Set[int]]:
    """Load all canonical addresses from accepted CFG artifacts for membership classification."""
    canonical_addresses = {
        "blocks": set(),
        "instructions": set(),
        "function_entries": set(),
        "edges_sources": set(),
        "edges_targets": set(),
    }

    # From cfg_nodes.json - block start addresses and instruction addresses
    nodes = load_json(CFG_ARTIFACTS["cfg_nodes"])
    for node in nodes:
        start = int(node["start"], 16) if isinstance(node["start"], str) else node["start"]
        canonical_addresses["blocks"].add(start)
        for inst_addr in node.get("instruction_addresses", []):
            addr = int(inst_addr, 16) if isinstance(inst_addr, str) else inst_addr
            canonical_addresses["instructions"].add(addr)

    # From cfg_summary.json - accepted function entries
    summary = load_json(CFG_ARTIFACTS["cfg_summary"])
    for entry in summary.get("accepted_function_entries", []):
        addr = int(entry, 16) if isinstance(entry, str) else entry
        canonical_addresses["function_entries"].add(addr)

    # From cfg_edges.json - edge source and target addresses
    edges = load_json(CFG_ARTIFACTS["cfg_edges"])
    for edge in edges:
        if edge.get("source_address") is not None:
            canonical_addresses["edges_sources"].add(edge["source_address"])
        if edge.get("target_address") is not None:
            canonical_addresses["edges_targets"].add(edge["target_address"])

    return canonical_addresses


def classify_canonical_membership(target_address: int, canonical: Dict[str, Set[int]]) -> str:
    """Classify a literal target address by its canonical membership."""
    if target_address in canonical["function_entries"]:
        return "FUNCTION_ENTRY"
    if target_address in canonical["blocks"]:
        return "BLOCK_START"
    if target_address in canonical["instructions"]:
        return "INSIDE_BLOCK"
    if target_address in canonical["edges_targets"]:
        return "EDGE_TARGET"
    return "NON_CANONICAL"


def process_site(site: Dict[str, Any], firmware: bytes, canonical: Dict[str, Set[int]]) -> Dict[str, Any]:
    """Process a single manifest site and return evidence record."""
    source_site = site["site_address"]
    source_addr = int(source_site, 16)

    # Read instruction word from firmware
    off = source_addr - IMAGE_BASE
    if off < 0 or off + 2 > len(firmware):
        return {
            "source_site": source_site,
            "instruction_word": None,
            "literal_pool_address": None,
            "literal_raw_bytes": None,
            "loaded_target_address": None,
            "validation_status": "FAILED",
            "literal_target_classification": "INVALID_LITERAL_TARGET",
            "canonical_membership_classification": "NON_CANONICAL",
            "failure_reason": "instruction_out_of_image_bounds",
        }

    instruction_word = struct.unpack_from("<H", firmware, off)[0]

    # Check if it's a register-indirect site (not jmpi/jsri)
    if not is_valid_jmpi_jsri_instruction(instruction_word):
        return {
            "source_site": source_site,
            "instruction_word": f"0x{instruction_word:04X}",
            "literal_pool_address": None,
            "literal_raw_bytes": None,
            "loaded_target_address": None,
            "validation_status": "SKIPPED",
            "literal_target_classification": "INSUFFICIENT_EVIDENCE",
            "canonical_membership_classification": "NON_CANONICAL",
            "failure_reason": "register_indirect_not_jmpi_jsri",
        }

    # Resolve via literal pool helper
    result = resolve_literal_pool_target(firmware, IMAGE_BASE, source_addr, instruction_word)

    if result["validation_status"] == "PASSED":
        target_address = int(result["loaded_target_address"], 16)
        canonical_class = classify_canonical_membership(target_address, canonical)

        # Literal validity depends ONLY on literal-pool resolution and safety checks
        # PASSED validation_status means the literal was resolved successfully
        literal_class = "VALIDATED_LITERAL_TARGET"

        return {
            "source_site": source_site,
            "instruction_word": result["instruction_word"],
            "literal_pool_address": result["literal_pool_address"],
            "literal_raw_bytes": result["literal_raw_bytes"],
            "loaded_target_address": result["loaded_target_address"],
            "validation_status": "PASSED",
            "literal_target_classification": literal_class,
            "canonical_membership_classification": canonical_class,
            "failure_reason": None,
        }
    else:
        # Resolution failed
        return {
            "source_site": source_site,
            "instruction_word": f"0x{instruction_word:04X}",
            "literal_pool_address": None,
            "literal_raw_bytes": None,
            "loaded_target_address": None,
            "validation_status": "FAILED",
            "literal_target_classification": "INVALID_LITERAL_TARGET",
            "canonical_membership_classification": "NON_CANONICAL",
            "failure_reason": result["failure_reason"],
        }


def write_atomic(output_path: Path, data: Any) -> None:
    """Write JSON atomically to output path."""
    if output_path.exists():
        raise FileExistsError(f"Output already exists: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp")

    with open(temp_path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    os.replace(temp_path, output_path)


def main() -> int:
    """Main entry point."""
    # Validate all inputs (hashes) first
    validate_inputs()

    # Load manifest
    manifest = load_json(MANIFEST_PATH)
    sites = manifest["sites"]

    # Check for duplicate source sites (fail fast on structural issues)
    seen_sites = set()
    for site in sites:
        source_site = site["site_address"]
        if source_site in seen_sites:
            raise ValueError(f"Duplicate source site in manifest: {source_site}")
        seen_sites.add(source_site)

    # Verify exactly 52 sites
    if len(sites) != 52:
        raise ValueError(f"Expected 52 manifest sites, got {len(sites)}")

    # Load firmware
    with open(FIRMWARE_PATH, "rb") as f:
        firmware = f.read()

    # Load canonical addresses for membership classification
    canonical = load_canonical_addresses()

    # Process all sites
    evidence_records = []
    jmpi_count = 0
    register_indirect_count = 0

    for site in sites:
        record = process_site(site, firmware, canonical)
        evidence_records.append(record)

        if record["validation_status"] == "SKIPPED":
            register_indirect_count += 1
        elif record["instruction_word"] and record["instruction_word"].startswith("0x70"):
            jmpi_count += 1

    # Verify counts
    if jmpi_count != 49:
        raise ValueError(f"Expected 49 JMPI sites, got {jmpi_count}")
    if register_indirect_count != 3:
        raise ValueError(f"Expected 3 register-indirect sites, got {register_indirect_count}")

    # Build output
    output = {
        "schema_version": "jmpi-evidence-1.0",
        "firmware_sha256": EXPECTED_FIRMWARE_SHA256,
        "manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "cfg_artifact_hashes": {
            "cfg_summary": EXPECTED_CFG_SUMMARY_SHA256,
            "cfg_nodes": EXPECTED_CFG_NODES_SHA256,
            "cfg_edges": EXPECTED_CFG_EDGES_SHA256,
            "cfg_ranges": EXPECTED_CFG_RANGES_SHA256,
        },
        "total_sites": 52,
        "jmpi_sites_resolved": jmpi_count,
        "register_indirect_sites_preserved": register_indirect_count,
        "evidence_records": evidence_records,
    }

    # Write atomically
    write_atomic(OUTPUT_PATH, output)

    print(f"Processed {len(evidence_records)} sites")
    print(f"  JMPI resolved: {jmpi_count}")
    print(f"  Register-indirect preserved: {register_indirect_count}")
    print(f"Output written to: {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())