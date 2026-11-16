# Aula L99 V9.2 Offline Package

Offline V9.2 package around the audited integration collectors and the
D4-Prep smoke harness. No REA connection, no Ghidra execution, no hardware
access, and no network access is performed by this package.

## Directory layout

```
config.json                  Deterministic package configuration
README.md                    This file
run_v9_2.sh                  Fail-closed sequential runner (Run 1 + Run 2)
check_v9_2.sh                Status printer (always exits zero)
PACKAGE_SHA256SUMS.txt       SHA-256 of every package file except itself
D2_AUDIT_REPORT.md           Session D2 audit report
SESSION_D4_PREP_REPORT.md    Session D4-Prep report
SMOKE_RUNBOOK.md             Smoke runbook
scripts/
    V92ComputedCallCollector.java   Session A collector
    V92SharedStateCollector.java    Session B collector
    V92BoundaryCollector.java       Session C collector
python/
    preflight.py                  Fail-closed preflight checks
    build.py                      Deterministic artifact builder
    compare.py                    Run 1 vs Run 2 byte-for-byte compare
    validate_computed_calls.py    Session A validator
    validate_shared_state.py      Session B validator
    validate_boundary.py          Session C validator
    write_handover.py             Bounded failure-evidence writer
tests/
    test_validate_computed_calls.py
    test_validate_shared_state.py
    test_validate_boundary.py
smoke/
    run_single_smoke.sh           Generic single smoke (D4-Prep harness)
    run_all_smokes.sh             Generic all-smokes (D4-Prep harness)
    check_smokes.sh               Smoke status printer (D4-Prep harness)
    collect_failure_evidence.sh   Bounded failure evidence (D4-Prep harness)
    smoke_commands.conf.example   Template for D4-Run to fill (not runnable)
```

## Configuration

See `config.json` for all fixed values: schema version, Ghidra home,
firmware path/size/SHA-256, V8/V9/V9.1 directories, validated project root,
project/program names, language, loaded memory range, final V9.2 output path,
nine call-site addresses, four pointer-cell addresses, seven shared-state
addresses, boundary target and window, expected row counts, and timeout values.

## Runners

- `run_v9_2.sh` executes, per run: preflight, Session A collector/gates,
  Session B collector/gates, Session C collector/gates, build artifacts,
  validate manifest. Then Run 2 independently, compare deterministic artifacts,
  publish Run 1 only after comparison PASS, never overwrite existing output.
- `check_v9_2.sh` prints STATUS/PHASE/PROGRESS/MESSAGE/ACCEPTANCE/VERDICT and
  always exits zero.

## Smoke harness

The six smoke scripts under `smoke/` are copied verbatim from D4-Prep
(SHA-256 preserved). `smoke/smoke_commands.conf.example` is a documented
template only; D4-Run generates the real `smoke_commands.conf` with exact
collector scripts, arguments, output JSON, validator command, and
output/result directories. Do not execute smoke tests in this session.

## Offline tests

52 tests across the three test suites:

- test_validate_computed_calls.py: 19
- test_validate_shared_state.py: 20
- test_validate_boundary.py: 13

Run: `python tests/test_validate_*.py` from the package root.

## Restrictions

This package must not be used to connect to REA, execute Ghidra, run the real
smoke gates, execute the complete V9.2 pipeline, publish firmware, begin
D4-Run/D5/V9.3/V10, or access any physical device.
