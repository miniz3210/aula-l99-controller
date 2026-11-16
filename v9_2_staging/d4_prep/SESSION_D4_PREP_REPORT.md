# Session D4 Prep Report

## 1. Exact files created

All under `C:\temp\aula-l99-controller\v9_2_staging\d4_prep\`:

- `run_single_smoke.sh`
- `run_all_smokes.sh`
- `check_smokes.sh`
- `collect_failure_evidence.sh`
- `SMOKE_RUNBOOK.md`
- `SESSION_D4_PREP_REPORT.md` (this file)

No other files were created or modified.

## 2. Shell interfaces

### run_single_smoke.sh
Positional or named arguments:
- `--ghidra-home`, `--project-dir`, `--project-name`, `--program-name`, `--script-path`, `--collector-script`, `--collector-args`, `--output-json`, `--validator`, `--ghidra-log`, `--result-dir`
Positional fallback order: ghidra_home project_dir project_name program_name script_path collector_script collector_args output_json validator ghidra_log result_dir.

### run_all_smokes.sh
Options: `--continue-on-failure`, `--config <path>` (default `./smoke_commands.conf`). Requires D3-generated `smoke_commands.conf` with `SMOKE_1_*`, `SMOKE_2_*`, `SMOKE_3_*` shell variables. No final collector arguments hardcoded.

### check_smokes.sh
Option: `--result-dir <path>` (default `./`). Prints STATUS, CURRENT_COLLECTOR, COMPLETED_COUNT, FAILED_COUNT, LAST_MESSAGE. Always exits zero.

### collect_failure_evidence.sh
Options: `--result-dir <path>`, `--package <tar path>`. Prints status files, smoke_result.json files, Ghidra log tails, output sizes/hashes, validator stdout/stderr, package checksum status. No firmware or accepted artifacts included.

## 3. Gate behavior (run_single_smoke.sh)

1. Run exactly one analyzeHeadless process.
2. Capture process exit code.
3. Do not trust exit code alone.
4. Require output file exists.
5. Require output file size > 0.
6. Parse output with `python3 -m json.tool`.
7. Run the supplied validator; capture its exit code.
8. Scan Ghidra log for: ERROR, SCRIPT ERROR, ClassNotFound, compilation error, uncaught exception.
9. Write deterministic `smoke_result.json` with: collector, process_exit_code, output_exists, output_size, output_sha256, json_valid, validator_exit_code, forbidden_log_markers, final_status.
10. No timestamps in smoke_result.json.
11. Return non-zero unless every gate passes.
12. Never modify/delete the Ghidra project; never run two collectors concurrently; never delete failed output or logs.

## 4. Failure behavior

- `run_single_smoke.sh` exits 1 if any gate fails; writes smoke_result.json with final_status=FAIL.
- `run_all_smokes.sh` stops after the first failed smoke by default (exit 1). With `--continue-on-failure`, continues to collect later failures but overall status remains FAIL (never marks acceptance).
- `check_smokes.sh` always exits 0 after printing status.
- `collect_failure_evidence.sh` always exits 0.

## 5. Sequential-execution guarantees

`run_all_smokes.sh` invokes `run_single_smoke.sh` sequentially (SMOKE_1 then SMOKE_2 then SMOKE_3), waiting for each to complete before starting the next. No two analyzeHeadless processes run concurrently.

## 6. bash -n result

Bash is not available on this Windows host (`bash` command not found). `bash -n` syntax validation must be performed in the existing Linux/WSL/container environment on all four shell scripts before D4-Run. Scripts were written with POSIX-compatible constructs and `set -euo pipefail`.

## 7. Remaining values D3 must supply

D3 must generate `smoke_commands.conf` (not created here) with `SMOKE_1_*`, `SMOKE_2_*`, `SMOKE_3_*` variable sets:
- SMOKE_N_GHIDRA_HOME, SMOKE_N_PROJECT_DIR, SMOKE_N_PROJECT_NAME, SMOKE_N_PROGRAM_NAME, SMOKE_N_SCRIPT_PATH, SMOKE_N_COLLECTOR_SCRIPT, SMOKE_N_COLLECTOR_ARGS, SMOKE_N_OUTPUT_JSON, SMOKE_N_VALIDATOR, SMOKE_N_GHIDRA_LOG, SMOKE_N_RESULT_DIR.

Final collector script names, arguments, output paths, validator commands, and result directories are not yet known and must come from D3.

## 8. Confirmation: no collector was copied or modified

No Session A, B, or C collectors were copied or modified. Only the generic harness was created in d4_prep. The D2 integration-copy collectors were not inspected or modified.

## 9. Confirmation: no REA connection occurred

No connection to REA (10.1.0.107) was made. No hardware access, no network access beyond future operator-initiated REA execution.

## 10. Confirmation: no accepted artifact, project, hardware, or Git state was modified

No accepted artifact, Ghidra project, hardware, or Git state was modified. No commits, pushes, tags, resets, restores, clean, checkout, or stash performed. No `rm -rf` against project or accepted-artifact paths. No createFunction/disassembly commands. No firmware included in evidence.

## Final verdict

D4_PREP_READY_FOR_D3
