#!/usr/bin/env python3
"""Bounded failure-evidence writer for the V9.2 offline package.

Writes a handover document containing:
  - phase
  - exit code
  - failing command
  - completed gates
  - output files present
  - output sizes and SHA-256
  - Ghidra log paths
  - validator status
  - best restart point

Does not include firmware contents, accepted artifacts, private keys,
credentials, or large decompiler bodies.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

LIMITED_FILES = [
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
    parser = argparse.ArgumentParser(description="Write bounded failure evidence")
    parser.add_argument("--run-dir", required=True, help="Run directory")
    parser.add_argument("--phase", required=True, help="Failing phase")
    parser.add_argument("--exit-code", required=True, type=int, help="Exit code")
    parser.add_argument("--failing-command", required=True, help="Failing command")
    parser.add_argument("--completed-gates", required=True,
                        help="Comma-separated completed gates")
    parser.add_argument("--ghidra-log", action="append", default=[],
                        help="Ghidra log path (repeatable)")
    parser.add_argument("--validator-status", default="unknown",
                        help="Validator status")
    parser.add_argument("--restart-point", required=True, help="Best restart point")
    parser.add_argument("--out", required=True, help="Output handover.json path")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    out_path = Path(args.out)

    output_files: List[Dict[str, Any]] = []
    for name in LIMITED_FILES:
        p = run_dir / name
        entry: Dict[str, Any] = {"name": name, "present": p.is_file()}
        if p.is_file():
            entry["size_bytes"] = p.stat().st_size
            entry["sha256"] = sha256_file(p)
        else:
            entry["size_bytes"] = None
            entry["sha256"] = None
        output_files.append(entry)

    ghidra_logs = []
    for lg in args.ghidra_log:
        p = Path(lg)
        entry: Dict[str, Any] = {"path": str(p), "present": p.is_file()}
        if p.is_file():
            entry["size_bytes"] = p.stat().st_size
        ghidra_logs.append(entry)

    completed_gates = [g.strip() for g in args.completed_gates.split(",") if g.strip()]

    handover = {
        "schema": "v9.2-handover-1.0",
        "phase": args.phase,
        "exit_code": args.exit_code,
        "failing_command": args.failing_command,
        "completed_gates": completed_gates,
        "output_files_present": output_files,
        "ghidra_log_paths": ghidra_logs,
        "validator_status": args.validator_status,
        "best_restart_point": args.restart_point,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(handover, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
                        encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
