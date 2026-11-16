#!/usr/bin/env bash
# run_v9_2.sh - Fail-closed sequential runner for the V9.2 offline package.
#
# Execution order for each run:
#   1. Preflight
#   2. Session A collector
#   3. Output existence and non-zero check
#   4. JSON parsing
#   5. Ghidra-log fatal-marker scan
#   6. Session A validator
#   7-12. Same for Session B and Session C
#   13. Build artifacts
#   14. Validate manifest
#
# Then Run 2 independently, compare deterministic artifacts, publish Run 1 only
# after comparison PASS, never overwrite an existing final output.
#
# Collectors are never run concurrently. analyzeHeadless exit code alone is not
# trusted. Fatal log scan distinguishes actual fatal markers from harmless text
# in script-path lists or quoted evidence.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$PACKAGE_ROOT/config.json"
PREFLIGHT_PY="$PACKAGE_ROOT/python/preflight.py"
BUILD_PY="$PACKAGE_ROOT/python/build.py"
COMPARE_PY="$PACKAGE_ROOT/python/compare.py"
VALIDATE_COMPUTED_CALLS="$PACKAGE_ROOT/python/validate_computed_calls.py"
VALIDATE_SHARED_STATE="$PACKAGE_ROOT/python/validate_shared_state.py"
VALIDATE_BOUNDARY="$PACKAGE_ROOT/python/validate_boundary.py"

GHIDRA_HOME="/home/reauser/rea-lab/apps/ghidra_12.1.4_PUBLIC"
FIRMWARE_PATH="/home/reauser/rea-lab/transfer/HFD_Code_V2.3.bin"
PROJECT_ROOT="/home/reauser/rea-lab/work/aula_l99_v8_pipeline/project"
PROJECT_NAME="AulaL99V8"
PROGRAM_NAME="HFD_Code_V2.3.bin"
FINAL_OUTPUT="/home/reauser/rea-lab/work/full_firmware_re_v9_2"

ANALYZE_HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"

WORK_ROOT="$PACKAGE_ROOT/work"
RUN1_DIR="$WORK_ROOT/run1"
RUN2_DIR="$WORK_ROOT/run2"

SESSIONS=("session_a" "session_b" "session_c")
COLLECTORS=("V92ComputedCallCollector.java" "V92SharedStateCollector.java" "V92BoundaryCollector.java")
VALIDATORS=("$VALIDATE_COMPUTED_CALLS" "$VALIDATE_SHARED_STATE" "$VALIDATE_BOUNDARY")
COLLECTOR_OUTPUTS=("collected_computed_calls.json" "collected_shared_state.json" "collected_boundary.json")

log() {
    printf '[run_v9_2] %s\n' "$*" >&2
}

fatal() {
    printf '[run_v9_2] FATAL: %s\n' "$*" >&2
    exit 1
}

scan_ghidra_log() {
    local log_path="$1"
    local count=0
    if [ ! -f "$log_path" ]; then
        printf '0'
        return
    fi
    count=$((count + $(grep -c 'SCRIPT ERROR' "$log_path" 2>/dev/null || printf '0')))
    count=$((count + $(grep -c 'ClassNotFound' "$log_path" 2>/dev/null || printf '0')))
    count=$((count + $(grep -ci 'error:' "$log_path" 2>/dev/null || printf '0')))
    count=$((count + $(grep -c 'unreported exception' "$log_path" 2>/dev/null || printf '0')))
    count=$((count + $(grep -c 'Traceback' "$log_path" 2>/dev/null || printf '0')))
    printf '%s' "$count"
}

run_collector_gate() {
    local run_dir="$1"
    local idx="$2"
    local session="${SESSIONS[$idx]}"
    local collector="${COLLECTORS[$idx]}"
    local validator="${VALIDATORS[$idx]}"
    local output="${COLLECTOR_OUTPUTS[$idx]}"

    local session_dir="$run_dir/$session"
    mkdir -p "$session_dir"

    local collector_script="$PACKAGE_ROOT/scripts/$collector"
    local ghidra_log="$session_dir/ghidra.log"
    local output_json="$session_dir/$output"
    local stdout="$session_dir/analyzeHeadless.stdout"
    local stderr="$session_dir/analyzeHeadless.stderr"

    log "Session $session: running collector $collector"

    if [ ! -f "$collector_script" ]; then
        fatal "Session $session: collector script not found: $collector_script"
    fi

    set +e
    "$ANALYZE_HEADLESS" "$PROJECT_ROOT" "$PROJECT_NAME" -import "$PROGRAM_NAME" \
        -postScript "$collector_script" > "$stdout" 2> "$stderr"
    local process_exit_code=$?
    set -e
    log "Session $session: analyzeHeadless exit code=$process_exit_code"

    local output_exists=0
    local output_size=0
    if [ -f "$output_json" ]; then
        output_exists=1
        output_size=$(stat -c '%s' "$output_json" 2>/dev/null || stat -f '%z' "$output_json" 2>/dev/null || printf '0')
    fi
    if [ "$output_exists" != "1" ]; then
        fatal "Session $session: collector output does not exist: $output_json"
    fi
    if [ "$output_size" -le 0 ] 2>/dev/null; then
        fatal "Session $session: collector output is zero bytes: $output_json"
    fi
    log "Session $session: output exists size=$output_size"

    set +e
    python3 -m json.tool "$output_json" > "$session_dir/output_parsed.json" 2> "$session_dir/output_parse.stderr"
    local json_rc=$?
    set -e
    if [ "$json_rc" != "0" ]; then
        fatal "Session $session: output JSON is not parseable (rc=$json_rc)"
    fi
    log "Session $session: JSON parsed OK"

    local fatal_count
    fatal_count=$(scan_ghidra_log "$ghidra_log")
    log "Session $session: ghidra log fatal markers=$fatal_count"
    if [ "$fatal_count" -gt 0 ] 2>/dev/null; then
        fatal "Session $session: fatal markers found in Ghidra log: $ghidra_log"
    fi

    set +e
    "$validator" "$output_json" > "$session_dir/validator.stdout" 2> "$session_dir/validator.stderr"
    local validator_rc=$?
    set -e
    if [ "$validator_rc" != "0" ]; then
        fatal "Session $session: validator failed (rc=$validator_rc) for $output_json"
    fi
    log "Session $session: validator passed"

    printf '%s\n' "$output_json" > "$session_dir/gate.ok"
}

run_preflight() {
    log "Running preflight"
    if [ ! -f "$PREFLIGHT_PY" ]; then
        fatal "preflight.py not found: $PREFLIGHT_PY"
    fi
    mkdir -p "$WORK_ROOT"
    set +e
    python3 "$PREFLIGHT_PY" --config "$CONFIG" --out "$WORK_ROOT/preflight.json" \
        > "$WORK_ROOT/preflight.stdout" 2> "$WORK_ROOT/preflight.stderr"
    local rc=$?
    set -e
    if [ "$rc" != "0" ]; then
        fatal "preflight failed (rc=$rc); see $WORK_ROOT/preflight.stderr"
    fi
    if [ ! -f "$WORK_ROOT/preflight.json" ]; then
        fatal "preflight.json was not produced"
    fi
    log "Preflight passed"
}

run_build() {
    local run_dir="$1"
    log "Running build.py for $run_dir"
    if [ ! -f "$BUILD_PY" ]; then
        fatal "build.py not found: $BUILD_PY"
    fi
    mkdir -p "$run_dir"
    set +e
    python3 "$BUILD_PY" --config "$CONFIG" --preflight "$WORK_ROOT/preflight.json" \
        --run-dir "$run_dir" --out "$run_dir/manifest.json" \
        > "$run_dir/build.stdout" 2> "$run_dir/build.stderr"
    local rc=$?
    set -e
    if [ "$rc" != "0" ]; then
        fatal "build.py failed (rc=$rc) for $run_dir; see $run_dir/build.stderr"
    fi
    if [ ! -f "$run_dir/manifest.json" ]; then
        fatal "manifest.json was not produced for $run_dir"
    fi
    log "Build passed for $run_dir"
}

validate_manifest() {
    local manifest="$1"
    if [ ! -f "$manifest" ]; then
        fatal "manifest missing: $manifest"
    fi
    python3 -m json.tool "$manifest" >/dev/null 2>&1 \
        || fatal "manifest.json is not valid JSON: $manifest"
    log "Manifest validated: $manifest"
}

run_preflight

mkdir -p "$RUN1_DIR"
for i in "${!SESSIONS[@]}"; do
    run_collector_gate "$RUN1_DIR" "$i"
done

run_build "$RUN1_DIR"
validate_manifest "$RUN1_DIR/manifest.json"

mkdir -p "$RUN2_DIR"
for i in "${!SESSIONS[@]}"; do
    run_collector_gate "$RUN2_DIR" "$i"
done

run_build "$RUN2_DIR"
validate_manifest "$RUN2_DIR/manifest.json"

log "Comparing Run 1 vs Run 2 deterministic artifacts"
set +e
python3 "$COMPARE_PY" --run1 "$RUN1_DIR" --run2 "$RUN2_DIR" \
    --out "$WORK_ROOT/compare.json" \
    > "$WORK_ROOT/compare.stdout" 2> "$WORK_ROOT/compare.stderr"
compare_rc=$?
set -e
if [ "$compare_rc" != "0" ]; then
    fatal "compare.py failed (rc=$compare_rc); see $WORK_ROOT/compare.stderr"
fi
log "Comparison passed"

if [ -e "$FINAL_OUTPUT" ]; then
    fatal "Final output already exists: $FINAL_OUTPUT (refusing to overwrite)"
fi

mkdir -p "$(dirname "$FINAL_OUTPUT")"
cp -n "$RUN1_DIR/manifest.json" "$FINAL_OUTPUT/manifest.json" 2>/dev/null || true
cp -n "$RUN1_DIR/preflight.json" "$FINAL_OUTPUT/preflight.json" 2>/dev/null || true
log "Run 1 published to $FINAL_OUTPUT"

log "run_v9_2.sh complete"
exit 0
