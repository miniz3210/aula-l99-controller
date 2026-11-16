#!/usr/bin/env python3
"""Deterministic byte-for-byte comparison of Run 1 and Run 2 artifacts.

Compares all deterministic final artifacts including manifest.json.
Reports each file hash for both runs. Fails if any file is missing or if any
hash differs. Writes deterministic compare.json with no timestamps.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ARTIFACT_NAMES = [
    "preflight.json",
    "jsri_resolution.json",
    "pointer_cell_inventory.csv",
    "shared_state_map.csv",
    "callback_chain_inventory.json",
    "boundary_0x60049b90_analysis.json",
    "evidence_decision_matrix.csv",
    "v9_2_report.json",
    "v9_2_report.txt",
    "manifest.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Compare Run 1 vs Run 2 artifacts")
    parser.add_argument("--run1", required=True, help="Run 1 directory")
    parser.add_argument("--run2", required=True, help="Run 2 directory")
    parser.add_argument("--out", required=True, help="Output compare.json path")
    args = parser.parse_args(argv)

    run1 = Path(args.run1)
    run2 = Path(args.run2)
    out_path = Path(args.out)

    errors: List[str] = []
    file_results: List[Dict[str, Any]] = []

    for name in sorted(ARTIFACT_NAMES):
        p1 = run1 / name
        p2 = run2 / name
        entry: Dict[str, Any] = {"file": name}
        missing = False
        if not p1.is_file():
            errors.append(f"Run 1 missing file: {name}")
            missing = True
            entry["run1_hash"] = None
            entry["run1_present"] = False
        else:
            entry["run1_hash"] = sha256_file(p1)
            entry["run1_present"] = True
        if not p2.is_file():
            errors.append(f"Run 2 missing file: {name}")
            missing = True
            entry["run2_hash"] = None
            entry["run2_present"] = False
        else:
            entry["run2_hash"] = sha256_file(p2)
            entry["run2_present"] = True
        if not missing:
            if entry["run1_hash"] != entry["run2_hash"]:
                errors.append(f"hash differs for {name}")
                entry["match"] = False
            else:
                entry["match"] = True
        entry["missing"] = missing
        file_results.append(entry)

    passed = len(errors) == 0
    report = {
        "schema": "v9.2-compare-1.0",
        "passed": passed,
        "error_count": len(errors),
        "errors": errors,
        "artifact_count": len(ARTIFACT_NAMES),
        "files": file_results,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
                        encoding="utf-8", newline="\n")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
