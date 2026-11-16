#!/usr/bin/env bash
# run_all_smokes.sh - Run three collector smokes sequentially via run_single_smoke.sh.
# Requires a later-generated config file: smoke_commands.conf
set -euo pipefail

usage() {
    cat <<EOF
Usage: run_all_smokes.sh [--continue-on-failure] [--config <path>]
  --continue-on-failure   Evidence-only: continue after a failed smoke to collect later failures.
                          Never marks overall acceptance.
  --config <path>         Path to smoke_commands.conf (default: ./smoke_commands.conf)
  --help|-h               Show this help.
EOF
}

CONTINUE_ON_FAILURE=0
CONFIG="./smoke_commands.conf"

while [ $# -gt 0 ]; do
    case "$1" in
        --continue-on-failure) CONTINUE_ON_FAILURE=1; shift ;;
        --config) CONFIG="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *) echo "Unexpected argument: $1" >&2; usage; exit 2 ;;
    esac
done

if [ ! -f "$CONFIG" ]; then
    echo "ERROR: config file not found: $CONFIG" >&2
    echo "D3 must generate smoke_commands.conf before running this script." >&2
    exit 2
fi

# shellcheck disable=SC1090
# shellcheck disable=SC1091
. "$CONFIG"

# smoke_commands.conf shell-variable format (documented, not created here):
#
#   SMOKE_1_GHIDRA_HOME="..."
#   SMOKE_1_PROJECT_DIR="..."
#   SMOKE_1_PROJECT_NAME="..."
#   SMOKE_1_PROGRAM_NAME="..."
#   SMOKE_1_SCRIPT_PATH="..."
#   SMOKE_1_COLLECTOR_SCRIPT="..."
#   SMOKE_1_COLLECTOR_ARGS="..."
#   SMOKE_1_OUTPUT_JSON="..."
#   SMOKE_1_VALIDATOR="..."
#   SMOKE_1_GHIDRA_LOG="..."
#   SMOKE_1_RESULT_DIR="..."
#
#   SMOKE_2_*  (Session B collector)
#   SMOKE_3_*  (Session C collector)
#
# No final collector script arguments are hardcoded here; they are supplied by D3.

RUN_SINGLE="$(dirname "$0")/run_single_smoke.sh"
if [ ! -x "$RUN_SINGLE" ]; then
    RUN_SINGLE="run_single_smoke.sh"
fi

OVERALL_STATUS="PASS"
FAILED_COUNT=0
COMPLETED_COUNT=0
LAST_MESSAGE=""

run_smoke() {
    local prefix="$1"
    local ghidra_home="${!prefix}_GHIDRA_HOME"
    local project_dir="${!prefix}_PROJECT_DIR"
    local project_name="${!prefix}_PROJECT_NAME"
    local program_name="${!prefix}_PROGRAM_NAME"
    local script_path="${!prefix}_SCRIPT_PATH"
    local collector_script="${!prefix}_COLLECTOR_SCRIPT"
    local collector_args="${!prefix}_COLLECTOR_ARGS"
    local output_json="${!prefix}_OUTPUT_JSON"
    local validator="${!prefix}_VALIDATOR"
    local ghidra_log="${!prefix}_GHIDRA_LOG"
    local result_dir="${!prefix}_RESULT_DIR"

    if [ -z "$ghidra_home" ] || [ -z "$project_dir" ] || [ -z "$project_name" ] || \
       [ -z "$program_name" ] || [ -z "$script_path" ] || [ -z "$collector_script" ] || \
       [ -z "$output_json" ] || [ -z "$validator" ] || [ -z "$ghidra_log" ] || [ -z "$result_dir" ]; then
        echo "ERROR: incomplete smoke config for $prefix" >&2
        OVERALL_STATUS="FAIL"
        FAILED_COUNT=$((FAILED_COUNT + 1))
        LAST_MESSAGE="incomplete config for $prefix"
        return 1
    fi

    echo "=== Running smoke: $prefix ($collector_script) ==="
    set +e
    "$RUN_SINGLE" \
        --ghidra-home "$ghidra_home" \
        --project-dir "$project_dir" \
        --project-name "$project_name" \
        --program-name "$program_name" \
        --script-path "$script_path" \
        --collector-script "$collector_script" \
        --collector-args "$collector_args" \
        --output-json "$output_json" \
        --validator "$validator" \
        --ghidra-log "$ghidra_log" \
        --result-dir "$result_dir"
    RC=$?
    set -e
    COMPLETED_COUNT=$((COMPLETED_COUNT + 1))

    if [ $RC -ne 0 ]; then
        FAILED_COUNT=$((FAILED_COUNT + 1))
        OVERALL_STATUS="FAIL"
        LAST_MESSAGE="FAILED: $prefix ($collector_script) exit=$RC"
        echo "$LAST_MESSAGE"
        if [ "$CONTINUE_ON_FAILURE" = "0" ]; then
            echo "Stopping after first failed smoke." >&2
            exit 1
        fi
    else
        LAST_MESSAGE="PASS: $prefix ($collector_script)"
        echo "$LAST_MESSAGE"
    fi
}

# Session A collector (placeholder)
run_smoke "SMOKE_1"
# Session B collector (placeholder)
run_smoke "SMOKE_2"
# Session C collector (placeholder)
run_smoke "SMOKE_3"

if [ "$OVERALL_STATUS" = "FAIL" ]; then
    echo "OVERALL: FAIL ($FAILED_COUNT failed of $COMPLETED_COUNT completed)" >&2
    exit 1
fi

echo "OVERALL: PASS ($COMPLETED_COUNT completed, $FAILED_COUNT failed)"
exit 0