# Smoke Test Runbook - Session D4 Prep (AULA L99 V9.2)

## 1. Expected directory layout

All D4-Prep deliverables live under (write location only):

```
v9_2_staging/d4_prep/
  run_single_smoke.sh
  run_all_smokes.sh
  check_smokes.sh
  collect_failure_evidence.sh
  SMOKE_RUNBOOK.md
  SESSION_D4_PREP_REPORT.md
  smoke_commands.conf        (generated later by D3; NOT created here)
```

The D4-Prep harness is schema-neutral and does not assume final collector field
names. It only assumes:

- collector output is JSON;
- validator is a Python command;
- expected output path is supplied;
- collector script name is supplied.

Ghidra project identity (remote reference, not modified here):

- Host: 10.1.0.107 (hostname: rea, user: reauser)
- Ghidra: /home/reauser/rea-lab/apps/ghidra_12.1.4_PUBLIC
- Validated project: /home/reauser/rea-lab/work/aula_l99_v8_pipeline/project (AulaL99V8)
- Program: HFD_Code_V2.3.bin
- Language: MCORE:LE:32:default
- Firmware: /home/reauser/rea-lab/transfer/HFD_Code_V2.3.bin (313652 bytes, SHA-256 a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03)

## 2. Upload prerequisites

Before D4-Run executes, the operator must upload to the REA host:

- Ghidra 12.1.4 PUBLIC installed at the expected path.
- The AulaL99V8 Ghidra project (program HFD_Code_V2.3.bin, language MCORE:LE:32:default).
- The three collector scripts (Session A, B, C) and their validator commands.
- The generated smoke_commands.conf file (produced by D3).

No firmware, accepted artifact, project file, or Git state is modified by this harness.

## 3. chmod commands

Make all shell scripts executable before running:

```
chmod +x v9_2_staging/d4_prep/run_single_smoke.sh
chmod +x v9_2_staging/d4_prep/run_all_smokes.sh
chmod +x v9_2_staging/d4_prep/check_smokes.sh
chmod +x v9_2_staging/d4_prep/collect_failure_evidence.sh
```

## 4. How D3 supplies smoke_commands.conf

D3 generates `smoke_commands.conf` (not created by D4-Prep) with this shell-variable format:

```
# Session A collector
SMOKE_1_GHIDRA_HOME="/home/reauser/rea-lab/apps/ghidra_12.1.4_PUBLIC"
SMOKE_1_PROJECT_DIR="/home/reauser/rea-lab/work/aula_l99_v8_pipeline/project"
SMOKE_1_PROJECT_NAME="AulaL99V8"
SMOKE_1_PROGRAM_NAME="HFD_Code_V2.3.bin"
SMOKE_1_SCRIPT_PATH="/path/to/session_a_collector.py"
SMOKE_1_COLLECTOR_SCRIPT="session_a_collector"
SMOKE_1_COLLECTOR_ARGS="--arg1 value1"
SMOKE_1_OUTPUT_JSON="/path/to/output_a.json"
SMOKE_1_VALIDATOR="python3 /path/to/validator_a.py"
SMOKE_1_GHIDRA_LOG="/path/to/ghidra_a.log"
SMOKE_1_RESULT_DIR="/path/to/results/a"

# Session B collector
SMOKE_2_*  (same variable set, Session B values)

# Session C collector
SMOKE_3_*  (same variable set, Session C values)
```

No final collector script arguments are hardcoded in the harness; D3 supplies them.

## 5. How to run one collector

```
./run_single_smoke.sh \
  --ghidra-home <path> \
  --project-dir <path> \
  --project-name <name> \
  --program-name <name> \
  --script-path <path> \
  --collector-script <name> \
  --collector-args "<args>" \
  --output-json <path> \
  --validator "<cmd>" \
  --ghidra-log <path> \
  --result-dir <path>
```

Or positional fallback:
```
./run_single_smoke.sh <ghidra_home> <project_dir> <project_name> <program_name> <script_path> <collector_script> <collector_args> <output_json> <validator> <ghidra_log> <result_dir>
```

## 6. How to run all sequentially

```
./run_all_smokes.sh --config ./smoke_commands.conf
```

To continue collecting later failures after a first failure (evidence-only, never marks acceptance):

```
./run_all_smokes.sh --continue-on-failure --config ./smoke_commands.conf
```

## 7. How to inspect failure

```
./check_smokes.sh --result-dir <result_dir>
./collect_failure_evidence.sh --result-dir <result_dir> --package <evidence.tar>
```

Inspect: smoke_result.json, analyzeHeadless stdout/stderr, validator stdout/stderr, Ghidra log tails, output sizes and hashes.

## 8. How to confirm no concurrent analyzeHeadless

run_single_smoke.sh launches exactly one analyzeHeadless process and waits for it to exit before proceeding. run_all_smokes.sh invokes run_single_smoke.sh sequentially, one after the other. Confirm by checking that no two analyzeHeadless processes overlap in process listings during a run.

## 9. How to compare Ghidra project identity before and after

Record program identity (program name, domain file, language, compiler spec) before running the smoke, and again after. The harness never modifies or deletes the Ghidra project; it only reads it. Identity must remain unchanged.

## 10. Why analyzeHeadless exit code alone is insufficient

- A non-zero exit code indicates failure, but a zero exit code does not guarantee the collector produced valid output.
- The harness additionally requires: output file exists, output size > 0, output parses via `python3 -m json.tool`, validator exit code is zero, and the Ghidra log contains none of the forbidden markers (ERROR, SCRIPT ERROR, ClassNotFound, compilation error, uncaught exception).
- A collector may exit zero while writing an empty or invalid JSON file; the additional gates catch this.
