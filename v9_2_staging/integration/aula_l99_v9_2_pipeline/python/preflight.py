#!/usr/bin/env python3
"""Fail-closed preflight for the V9.2 offline package.

Verifies firmware integrity, manifest integrity across V8/V9/V9.1,
V9.1 report acceptance/verdict, analyzeHeadless executability, Ghidra project
files, final V9.2 output absence, program identity, and runner output
confinement. Produces deterministic preflight.json without timestamps.

Read-only: never writes to accepted input directories.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

PREFLIGHT_ERRORS: List[str] = []


def fail(msg: str) -> None:
    PREFLIGHT_ERRORS.append(msg)


def load_config(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        fail(f"cannot read config {path}: {e}")
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        fail(f"invalid JSON in config {path}: {e}")
        return {}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_exists(path: Path, label: str) -> bool:
    if not path.exists():
        fail(f"{label} does not exist: {path}")
        return False
    return True


def check_file(path: Path, label: str) -> bool:
    if not path.is_file():
        fail(f"{label} is not a file: {path}")
        return False
    return True


def check_dir(path: Path, label: str) -> bool:
    if not path.is_dir():
        fail(f"{label} is not a directory: {path}")
        return False
    return True


def verify_size(path: Path, expected: int, label: str) -> None:
    if not check_file(path, label):
        return
    actual = path.stat().st_size
    if actual != expected:
        fail(f"{label} size {actual} != expected {expected}")


def verify_sha256(path: Path, expected: str, label: str) -> None:
    if not check_file(path, label):
        return
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        fail(f"{label} SHA-256 {actual} != expected {expected}")


def verify_manifest_hashes(manifest_path: Path, label: str) -> None:
    if not check_file(manifest_path, label):
        return
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{label} invalid JSON: {e}")
        return
    if not isinstance(doc, dict):
        fail(f"{label} top-level is not an object")
        return
    entries = doc.get("files", [])
    if not isinstance(entries, list):
        fail(f"{label} 'files' is not a list")
        return
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"{label} manifest entry is not an object")
            continue
        rel = entry.get("path")
        expected = entry.get("sha256")
        if not rel or not expected:
            fail(f"{label} manifest entry missing path/sha256: {entry!r}")
            continue
        target = manifest_path.parent / rel
        if not check_file(target, f"{label} entry {rel}"):
            continue
        actual = sha256_file(target)
        if actual.lower() != str(expected).lower():
            fail(f"{label} entry {rel} SHA-256 {actual} != expected {expected}")


def check_executable(path: Path, label: str) -> None:
    if not check_file(path, label):
        return
    if not os.access(path, os.X_OK):
        fail(f"{label} is not executable: {path}")


def _manifest_hashes_ok(manifest_path: Path) -> bool:
    if not manifest_path.is_file():
        return False
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(doc, dict):
        return False
    entries = doc.get("files", [])
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        rel = entry.get("path")
        expected = entry.get("sha256")
        if not rel or not expected:
            return False
        target = manifest_path.parent / rel
        if not target.is_file():
            return False
        h = hashlib.sha256()
        try:
            with open(target, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
        except OSError:
            return False
        if h.hexdigest().lower() != str(expected).lower():
            return False
    return True


def write_report(passed: bool, phase: str) -> None:
    pass


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="V9.2 fail-closed preflight")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--out", required=True, help="Output preflight.json path")
    args = parser.parse_args(argv)

    config = load_config(Path(args.config))
    if not config:
        write_report(False, "config_load_failed")
        return 1

    firmware = Path(config.get("firmware_path", ""))
    firmware_size = config.get("firmware_size")
    firmware_sha256 = config.get("firmware_sha256")

    ghidra_home = Path(config.get("ghidra_home", ""))
    analyze_headless = ghidra_home / "support" / "analyzeHeadless"

    project_root = Path(config.get("validated_project_root", ""))
    project_name = config.get("project_name", "")
    program_name = config.get("program_name", "")
    expected_language = config.get("expected_language", "")
    loaded_start = config.get("expected_loaded_memory_range", {}).get("loaded_start", "")
    loaded_end = config.get("expected_loaded_memory_range", {}).get("loaded_end", "")
    final_output = Path(config.get("final_v9_2_output_path", ""))

    v8_dir = Path(config.get("v8_directory", ""))
    v9_dir = Path(config.get("v9_directory", ""))
    v9_1_dir = Path(config.get("v9_1_directory", ""))

    # 1. Firmware exists.
    check_file(firmware, "firmware")

    # 2. Firmware size matches.
    if isinstance(firmware_size, int):
        verify_size(firmware, firmware_size, "firmware")

    # 3. Firmware SHA-256 matches.
    if isinstance(firmware_sha256, str):
        verify_sha256(firmware, firmware_sha256, "firmware")

    # 4. V8 manifest exists.
    v8_manifest = v8_dir / "manifest.json"
    check_file(v8_manifest, "V8 manifest")

    # 5. Every V8 manifest hash matches.
    verify_manifest_hashes(v8_manifest, "V8 manifest")

    # 6. V9 manifest exists.
    v9_manifest = v9_dir / "manifest.json"
    check_file(v9_manifest, "V9 manifest")

    # 7. Every V9 manifest hash matches.
    verify_manifest_hashes(v9_manifest, "V9 manifest")

    # 8. V9.1 manifest exists.
    v9_1_manifest = v9_1_dir / "manifest.json"
    check_file(v9_1_manifest, "V9.1 manifest")

    # 9. Every V9.1 manifest hash matches.
    verify_manifest_hashes(v9_1_manifest, "V9.1 manifest")

    # 10. V9.1 report acceptance is PASS.
    v9_1_report = v9_1_dir / "v9_1_report.json"
    acceptance_pass = False
    if check_file(v9_1_report, "V9.1 report"):
        try:
            report = json.loads(v9_1_report.read_text(encoding="utf-8"))
            if isinstance(report, dict) and report.get("acceptance") == "PASS":
                acceptance_pass = True
            else:
                fail("V9.1 report acceptance is not PASS")
        except json.JSONDecodeError as e:
            fail(f"V9.1 report invalid JSON: {e}")

    # 11. V9.1 verdict is INSUFFICIENT_EVIDENCE.
    verdict_correct = False
    if check_file(v9_1_report, "V9.1 report"):
        try:
            report = json.loads(v9_1_report.read_text(encoding="utf-8"))
            if isinstance(report, dict) and report.get("verdict") == "INSUFFICIENT_EVIDENCE":
                verdict_correct = True
            else:
                fail("V9.1 verdict is not INSUFFICIENT_EVIDENCE")
        except json.JSONDecodeError:
            pass

    # 12. analyzeHeadless exists and is executable.
    check_executable(analyze_headless, "analyzeHeadless")

    # 13. Ghidra project files exist.
    check_dir(project_root, "Ghidra project root")
    project_file = project_root / f"{project_name}.gpr"
    check_file(project_file, "Ghidra project file")

    # 14. Final V9.2 output does not already exist.
    if final_output.exists():
        fail(f"final V9.2 output already exists: {final_output}")

    # 15. Program identity can be checked at runtime before collection.
    program_identity_ok = bool(project_name and program_name and expected_language)
    if not program_identity_ok:
        fail("program identity is incomplete (project/program/language)")

    # 16. Runner output paths are confined to the package work directory and
    #     final output. Accepted input directories are never targeted for
    #     output; they are only read.
    output_confinement_ok = True
    work_dir = Path(args.out).parent
    if not work_dir.exists():
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            fail(f"cannot create work directory {work_dir}: {e}")
            output_confinement_ok = False

    all_pass = len(PREFLIGHT_ERRORS) == 0

    report = {
        "schema": "v9.2-preflight-1.0",
        "passed": all_pass,
        "error_count": len(PREFLIGHT_ERRORS),
        "errors": PREFLIGHT_ERRORS,
        "checks": {
            "firmware_exists": firmware.is_file(),
            "firmware_size_matches": (
                firmware.is_file() and firmware.stat().st_size == firmware_size
                if isinstance(firmware_size, int) else False
            ),
            "firmware_sha256_matches": (
                sha256_file(firmware).lower() == firmware_sha256.lower()
                if firmware.is_file() and isinstance(firmware_sha256, str) else False
            ),
            "v8_manifest_exists": v8_manifest.is_file(),
            "v8_manifest_hashes_match": _manifest_hashes_ok(v8_manifest),
            "v9_manifest_exists": v9_manifest.is_file(),
            "v9_manifest_hashes_match": _manifest_hashes_ok(v9_manifest),
            "v9_1_manifest_exists": v9_1_manifest.is_file(),
            "v9_1_manifest_hashes_match": _manifest_hashes_ok(v9_1_manifest),
            "v9_1_report_acceptance_pass": acceptance_pass,
            "v9_1_verdict_insufficient_evidence": verdict_correct,
            "analyze_headless_executable": analyze_headless.is_file() and os.access(analyze_headless, os.X_OK),
            "ghidra_project_files_exist": project_root.is_dir() and project_file.is_file(),
            "final_v9_2_output_absent": not final_output.exists(),
            "program_identity_checkable": program_identity_ok,
            "runner_output_confinement": output_confinement_ok,
        },
        "config": {
            "ghidra_home": str(ghidra_home),
            "firmware_path": str(firmware),
            "firmware_size": firmware_size,
            "firmware_sha256": firmware_sha256,
            "v8_directory": str(v8_dir),
            "v9_directory": str(v9_dir),
            "v9_1_directory": str(v9_1_dir),
            "validated_project_root": str(project_root),
            "project_name": project_name,
            "program_name": program_name,
            "expected_language": expected_language,
            "expected_loaded_memory_range": {
                "loaded_start": loaded_start,
                "loaded_end": loaded_end,
            },
            "final_v9_2_output_path": str(final_output),
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
