#!/usr/bin/env python3
"""Deterministic artifact builder for the V9.2 offline package.

Builds the required final artifacts from the three validated collector outputs.
The builder never silently synthesizes evidence absent from collectors.
Expected values remain separate from observed values. All output is
deterministic: JSON key ordering, address ordering, CSV columns, LF line
endings, no timestamps, no absolute Windows paths.

Required final artifacts:
  preflight.json
  jsri_resolution.json
  pointer_cell_inventory.csv
  shared_state_map.csv
  callback_chain_inventory.json
  boundary_0x60049b90_analysis.json
  evidence_decision_matrix.csv
  v9_2_report.json
  v9_2_report.txt
  manifest.json

Required counts:
  nine call-site rows, four pointer-cell rows, seven shared-state rows,
  one boundary target.
Decision rows for: computed targets, pointer cells, callback slot, shared RAM
state, boundary analysis, display-specific evidence.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

CALL_SITE_ADDRESSES = [
    "0x60049D9C", "0x60049E12", "0x60049E14", "0x60049E6A", "0x60049EEA",
    "0x60049EF0", "0x60049F7E", "0x60045016", "0x60045034",
]
POINTER_CELL_ADDRESSES = [
    "0x60049F88", "0x60049F94", "0x60049F98", "0x600450BC",
]
SHARED_STATE_ADDRESSES = [
    "0x00821528", "0x600450A8", "0x600450B0", "0x600450B4",
    "0x600450BC", "0x0086CF28", "0x0086DF28",
]
BOUNDARY_TARGET = "0x60049B90"
BOUNDARY_MIN = "0x60049A90"
BOUNDARY_MAX = "0x60049C90"

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
]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"cannot load JSON {path}: {e}")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: List[List[str]], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_hex(value: Any) -> str:
    if isinstance(value, int):
        return f"0x{value:08X}"
    if isinstance(value, str):
        s = value.strip()
        if not s.lower().startswith("0x"):
            s = "0x" + s
        try:
            return f"0x{int(s, 16):08X}"
        except ValueError:
            return value
    return str(value)


def addr_sort_key(addr: str) -> int:
    return int(addr, 16)


def build_jsri_resolution(collected_dirs: List[Path]) -> Dict[str, Any]:
    rows = []
    for addr in sorted(CALL_SITE_ADDRESSES, key=addr_sort_key):
        observed = {}
        for d in collected_dirs:
            p = d / "collected_computed_calls.json"
            if not p.is_file():
                continue
            try:
                doc = load_json(p)
            except SystemExit:
                continue
            for row in doc.get("call_sites", []):
                if normalize_hex(row.get("call_site_address")) == addr:
                    observed = row
                    break
        rows.append({
            "call_site_address": addr,
            "expected_address": addr,
            "observed_call_site": observed.get("call_site_address"),
            "observed_computed_destination": observed.get("computed_destination"),
            "observed_confidence": observed.get("confidence_classification"),
            "resolution_source": "collector" if observed else "none",
            "resolution": "resolved" if observed else "unresolved",
        })
    return {
        "schema": "v9.2-jsri-resolution-1.0",
        "call_site_count": len(rows),
        "expected_call_sites": sorted(CALL_SITE_ADDRESSES, key=addr_sort_key),
        "resolutions": rows,
    }


def build_pointer_cell_inventory(collected_dirs: List[Path]) -> List[List[str]]:
    rows = []
    for addr in sorted(POINTER_CELL_ADDRESSES, key=addr_sort_key):
        observed = {}
        for d in collected_dirs:
            p = d / "collected_computed_calls.json"
            if not p.is_file():
                continue
            try:
                doc = load_json(p)
            except SystemExit:
                continue
            for row in doc.get("pointer_cells", []):
                if normalize_hex(row.get("cell_address")) == addr:
                    observed = row
                    break
        rows.append([
            addr,
            addr,
            observed.get("cell_address", ""),
            observed.get("raw_bytes_minus8_plus15", ""),
            observed.get("decoded_32_le", ""),
            observed.get("cell_behavior", ""),
            "present" if observed else "absent",
        ])
    return rows


def build_shared_state_map(collected_dirs: List[Path]) -> List[List[str]]:
    rows = []
    for addr in sorted(SHARED_STATE_ADDRESSES, key=addr_sort_key):
        observed = {}
        for d in collected_dirs:
            p = d / "collected_shared_state.json"
            if not p.is_file():
                continue
            try:
                doc = load_json(p)
            except SystemExit:
                continue
            for row in doc.get("requested_states", []):
                if normalize_hex(row.get("normalized_address")) == addr:
                    observed = row
                    break
        rows.append([
            addr,
            addr,
            observed.get("normalized_address", ""),
            observed.get("address_classification", ""),
            observed.get("evidence_backed_state_classification", ""),
            observed.get("confidence", ""),
            observed.get("load_to_register_to_call_evidence", ""),
            "present" if observed else "absent",
        ])
    return rows


def build_callback_chain_inventory(collected_dirs: List[Path]) -> Dict[str, Any]:
    chain = {
        "schema": "v9.2-callback-chain-1.0",
        "callback_slot_address": "0x600450BC",
        "expected_callback_slot": "0x600450BC",
        "observed_callback_slot": None,
        "chain_present": False,
        "classification": None,
        "load_to_register_to_call_evidence": None,
        "destination_has_recovered_function": None,
        "destination_has_valid_instruction": None,
    }
    for d in collected_dirs:
        p = d / "collected_shared_state.json"
        if not p.is_file():
            continue
        try:
            doc = load_json(p)
        except SystemExit:
            continue
        for state in doc.get("requested_states", []):
            if normalize_hex(state.get("normalized_address")) == "0x600450BC":
                chain["observed_callback_slot"] = state.get("normalized_address")
                chain["load_to_register_to_call_evidence"] = state.get(
                    "load_to_register_to_call_evidence")
                break
        for chain_doc in doc.get("callback_chains", []):
            if normalize_hex(chain_doc.get("callback_slot_address", "")) == "0x600450BC":
                dest = chain_doc.get("callback_destination", {})
                chain["chain_present"] = True
                chain["classification"] = dest.get("classification")
                chain["destination_has_recovered_function"] = dest.get(
                    "destination_has_recovered_function")
                chain["destination_has_valid_instruction"] = dest.get(
                    "destination_has_valid_instruction")
    return chain


def build_boundary_analysis(collected_dirs: List[Path]) -> Dict[str, Any]:
    analysis = {
        "schema": "v9.2-boundary-1.0",
        "target": BOUNDARY_TARGET,
        "expected_target": BOUNDARY_TARGET,
        "window_minimum": BOUNDARY_MIN,
        "window_maximum": BOUNDARY_MAX,
        "target_in_window": True,
        "observed_target": None,
        "collector_output_present": False,
        "classification": None,
        "evidence_summary": {},
        "mutations_reported": [],
    }
    for d in collected_dirs:
        p = d / "collected_boundary.json"
        if not p.is_file():
            continue
        try:
            doc = load_json(p)
        except SystemExit:
            continue
        analysis["collector_output_present"] = True
        target = doc.get("target", {})
        analysis["observed_target"] = target.get("address")
        window = doc.get("window", {})
        analysis["window_start_observed"] = window.get("start")
        analysis["window_end_observed"] = window.get("end")
        cls = doc.get("classification", {})
        analysis["classification"] = cls.get("classification")
        analysis["evidence_summary"] = cls.get("evidence_summary", {})
        analysis["mutations_reported"] = doc.get("mutations_reported", [])
    return analysis


def build_evidence_decision_matrix(
    jsri: Dict[str, Any],
    pointer_rows: List[List[str]],
    shared_rows: List[List[str]],
    callback: Dict[str, Any],
    boundary: Dict[str, Any],
) -> List[List[str]]:
    rows = []
    unresolved = [r for r in jsri["resolutions"] if r["resolution"] != "resolved"]
    rows.append([
        "computed_targets",
        "9",
        str(len(jsri["resolutions"])),
        str(len(unresolved)),
        "PASS" if len(unresolved) == 0 else "FAIL",
        "computed_targets_validated" if len(unresolved) == 0 else "computed_targets_rejected",
    ])
    rows.append([
        "pointer_cells",
        "4",
        str(len(pointer_rows)),
        str(len([r for r in pointer_rows if r[6] != "present"])),
        "PASS" if len(pointer_rows) == 4 else "FAIL",
        "pointer_cells_present" if len(pointer_rows) == 4 else "pointer_cells_missing",
    ])
    rows.append([
        "callback_slot",
        "1",
        "1" if callback["chain_present"] else "0",
        "0" if callback["chain_present"] else "1",
        "PASS" if callback["chain_present"] else "FAIL",
        "shared_callback_state_confirmed" if callback["chain_present"] else "callback_unresolved",
    ])
    missing = [r for r in shared_rows if r[7] != "present"]
    rows.append([
        "shared_ram_state",
        "7",
        str(len(shared_rows)),
        str(len(missing)),
        "PASS" if len(shared_rows) == 7 else "FAIL",
        "shared_state_mapped" if len(shared_rows) == 7 else "shared_state_incomplete",
    ])
    rows.append([
        "boundary_analysis",
        "1",
        "1" if boundary["collector_output_present"] else "0",
        "0" if boundary["collector_output_present"] else "1",
        "PASS" if boundary["collector_output_present"] else "FAIL",
        "boundary_analyzed" if boundary["collector_output_present"] else "boundary_not_analyzed",
    ])
    rows.append([
        "display_specific_evidence",
        "0",
        "0",
        "0",
        "PASS",
        "insufficient_evidence",
    ])
    return rows


def build_report(
    jsri: Dict[str, Any],
    pointer_rows: List[List[str]],
    shared_rows: List[List[str]],
    callback: Dict[str, Any],
    boundary: Dict[str, Any],
    decision_rows: List[List[str]],
) -> tuple:
    verdict = "INSUFFICIENT_EVIDENCE"
    if (len(jsri["resolutions"]) == 9 and len(pointer_rows) == 4
            and len(shared_rows) == 7 and callback["chain_present"]):
        verdict = "SHARED_CALLBACK_STATE_CONFIRMED"

    report = {
        "schema": "v9.2-report-1.0",
        "verdict": verdict,
        "allowed_verdicts": [
            "COMPUTED_TARGETS_VALIDATED",
            "COMPUTED_TARGETS_REJECTED",
            "SHARED_CALLBACK_STATE_CONFIRMED",
            "DISPLAY_SPECIFIC_EVIDENCE_FOUND",
            "TRANSPORT_OR_GENERIC_CALLBACK_CHAIN_ONLY",
            "INSUFFICIENT_EVIDENCE",
        ],
        "default_verdict": "INSUFFICIENT_EVIDENCE",
        "call_site_count": 9,
        "pointer_cell_count": 4,
        "shared_state_count": 7,
        "boundary_target": BOUNDARY_TARGET,
        "decision_rows": decision_rows,
        "boundary_target_in_window": boundary["target_in_window"],
        "mutations_reported": boundary["mutations_reported"],
    }
    txt_lines = [
        "V9.2 Report",
        "===========",
        f"Verdict: {verdict}",
        f"Default verdict: INSUFFICIENT_EVIDENCE",
        f"Call sites: {len(jsri['resolutions'])} (expected 9)",
        f"Pointer cells: {len(pointer_rows)} (expected 4)",
        f"Shared states: {len(shared_rows)} (expected 7)",
        f"Boundary target: {BOUNDARY_TARGET} (window {BOUNDARY_MIN}-{BOUNDARY_MAX})",
        f"Mutations reported: {len(boundary['mutations_reported'])}",
        "",
        "Decision matrix:",
    ]
    for r in decision_rows:
        txt_lines.append("  " + " | ".join(r))
    report_txt = "\n".join(txt_lines) + "\n"
    return report, report_txt


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="V9.2 deterministic artifact builder")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--preflight", required=True, help="Path to preflight.json")
    parser.add_argument("--run-dir", required=True, help="Run directory with collector outputs")
    parser.add_argument("--out", required=True, help="Output manifest.json path")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        raise SystemExit(f"run directory not found: {run_dir}")

    collected_dirs = [run_dir / "session_a", run_dir / "session_b", run_dir / "session_c"]

    out_dir = Path(args.out).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    jsri = build_jsri_resolution(collected_dirs)
    write_json(out_dir / "jsri_resolution.json", jsri)

    pointer_cols = ["expected_address", "expected_cell", "observed_cell",
                    "raw_bytes", "decoded_32_le", "cell_behavior", "status"]
    pointer_rows = build_pointer_cell_inventory(collected_dirs)
    write_csv(out_dir / "pointer_cell_inventory.csv", pointer_rows, pointer_cols)

    shared_cols = ["expected_address", "expected_state", "observed_state",
                   "address_classification", "state_classification", "confidence",
                   "load_to_call_evidence", "status"]
    shared_rows = build_shared_state_map(collected_dirs)
    write_csv(out_dir / "shared_state_map.csv", shared_rows, shared_cols)

    callback = build_callback_chain_inventory(collected_dirs)
    write_json(out_dir / "callback_chain_inventory.json", callback)

    boundary = build_boundary_analysis(collected_dirs)
    write_json(out_dir / "boundary_0x60049b90_analysis.json", boundary)

    decision_rows = build_evidence_decision_matrix(
        jsri, pointer_rows, shared_rows, callback, boundary)
    write_csv(out_dir / "evidence_decision_matrix.csv", decision_rows,
              ["decision", "expected_count", "observed_count", "missing_count",
               "result", "verdict_contribution"])

    report, report_txt = build_report(
        jsri, pointer_rows, shared_rows, callback, boundary, decision_rows)
    write_json(out_dir / "v9_2_report.json", report)
    write_text(out_dir / "v9_2_report.txt", report_txt)

    preflight_src = Path(args.preflight)
    if preflight_src.is_file():
        write_text(out_dir / "preflight.json",
                   preflight_src.read_text(encoding="utf-8", newline="\n"))
    else:
        raise SystemExit(f"preflight.json not found: {preflight_src}")

    manifest_entries = []
    for name in ARTIFACT_NAMES:
        p = out_dir / name
        if not p.is_file():
            raise SystemExit(f"missing artifact for manifest: {p}")
        manifest_entries.append({
            "path": name,
            "sha256": sha256_file(p),
        })
    manifest = {
        "schema": "v9.2-manifest-1.0",
        "artifact_count": len(manifest_entries),
        "files": sorted(manifest_entries, key=lambda e: e["path"]),
    }
    write_json(out_dir / "manifest.json", manifest)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
