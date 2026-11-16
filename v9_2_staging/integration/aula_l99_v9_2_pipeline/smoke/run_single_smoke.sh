#!/usr/bin/env bash
# run_single_smoke.sh - Run one Ghidra collector smoke test generically.
# Schema-neutral: does not assume final collector field names.
set -euo pipefail

usage() {
    cat <<EOF
Usage: run_single_smoke.sh [positional or named args]
  --ghidra-home <path>   Ghidra home directory
  --project-dir <path>   Ghidra project directory
  --project-name <name>  Ghidra project name
  --program-name <name>  Ghidra program name
  --script-path <path>   Path to analyzeHeadless script
  --collector-script <name>  Collector script name
  --collector-args <args>   Arguments for collector script
  --output-json <path>   Expected output JSON path
  --validator <cmd>      Validator command
  --ghidra-log <path>    Ghidra log path
  --result-dir <path>    Result directory for smoke_result.json

Positional order (fallback):
  ghidra_home project_dir project_name program_name script_path collector_script collector_args output_json validator ghidra_log result_dir
EOF
}

# Parse named arguments with positional fallback.
GHIDRA_HOME=""
PROJECT_DIR=""
PROJECT_NAME=""
PROGRAM_NAME=""
SCRIPT_PATH=""
COLLECTOR_SCRIPT=""
COLLECTOR_ARGS=""
OUTPUT_JSON=""
VALIDATOR=""
GHIDRA_LOG=""
RESULT_DIR=""

POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --ghidra-home) GHIDRA_HOME="$2"; shift 2 ;;
        --project-dir) PROJECT_DIR="$2"; shift 2 ;;
        --project-name) PROJECT_NAME="$2"; shift 2 ;;
        --program-name) PROGRAM_NAME="$2"; shift 2 ;;
        --script-path) SCRIPT_PATH="$2"; shift 2 ;;
        --collector-script) COLLECTOR_SCRIPT="$2"; shift 2 ;;
        --collector-args) COLLECTOR_ARGS="$2"; shift 2 ;;
        --output-json) OUTPUT_JSON="$2"; shift 2 ;;
        --validator) VALIDATOR="$2"; shift 2 ;;
        --ghidra-log) GHIDRA_LOG="$2"; shift 2 ;;
        --result-dir) RESULT_DIR="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *) POSITIONAL+=("$1"); shift ;;
    esac
done

# Positional fallback for any unset fields.
POSITIONAL_ORDER=(GHIDRA_HOME PROJECT_DIR PROJECT_NAME PROGRAM_NAME SCRIPT_PATH COLLECTOR_SCRIPT COLLECTOR_ARGS OUTPUT_JSON VALIDATOR GHIDRA_LOG RESULT_DIR)
i=0
for name in "${POSITIONAL_ORDER[@]}"; do
    if [ $i -lt ${#POSITIONAL[@]} ]; then
        eval "$name=\"\${POSITIONAL[$i]}\""
        i=$((i + 1))
    fi
done

# Validate required inputs.
if [ -z "$GHIDRA_HOME" ] || [ -z "$PROJECT_DIR" ] || [ -z "$PROJECT_NAME" ] || \
   [ -z "$PROGRAM_NAME" ] || [ -z "$SCRIPT_PATH" ] || [ -z "$COLLECTOR_SCRIPT" ] || \
   [ -z "$OUTPUT_JSON" ] || [ -z "$VALIDATOR" ] || [ -z "$GHIDRA_LOG" ] || [ -z "$RESULT_DIR" ]; then
    echo "ERROR: missing required argument" >&2
    usage
    exit 2
fi

if [ ! -d "$GHIDRA_HOME" ]; then
    echo "ERROR: Ghidra home not found: $GHIDRA_HOME" >&2
    exit 2
fi
if [ ! -d "$PROJECT_DIR" ]; then
    echo "ERROR: project directory not found: $PROJECT_DIR" >&2
    exit 2
fi
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: script path not found: $SCRIPT_PATH" >&2
    exit 2
fi
if [ ! -f "$GHIDRA_LOG" ]; then
    echo "ERROR: Ghidra log not found: $GHIDRA_LOG" >&2
    exit 2
fi

ANALYZE_HEADLESS="$GHIDRA_HOME/support/analyzeHeadless"
if [ ! -x "$ANALYZE_HEADLESS" ]; then
    echo "ERROR: analyzeHeadless not executable: $ANALYZE_HEADLESS" >&2
    exit 2
fi

mkdir -p "$RESULT_DIR"

RESULT_FILE="$RESULT_DIR/smoke_result.json"
# Never modify or delete the Ghidra project; only read it.
# Never delete failed output or logs.

# Gate 1: run exactly one analyzeHeadless process (no concurrency).
PROCESS_EXIT_CODE=0
set +e
"$ANALYZE_HEADLESS" "$PROJECT_DIR" "$PROJECT_NAME" -import "$PROGRAM_NAME" -postScript "$SCRIPT_PATH" "$COLLECTOR_ARGS" > "$RESULT_DIR/analyzeHeadless.stdout" 2> "$RESULT_DIR/analyzeHeadless.stderr"
PROCESS_EXIT_CODE=$?
set -e

# Gate 2: output file must exist.
OUTPUT_EXISTS=0
OUTPUT_SIZE=0
OUTPUT_SHA256=""
if [ -f "$OUTPUT_JSON" ]; then
    OUTPUT_EXISTS=1
    OUTPUT_SIZE=$(stat -c '%s' "$OUTPUT_JSON" 2>/dev/null || stat -f '%z' "$OUTPUT_JSON" 2>/dev/null || echo 0)
fi

# Gate 3: output file size must be greater than zero.
OUTPUT_SIZE_GT_ZERO=0
if [ "$OUTPUT_SIZE" -gt 0 ] 2>/dev/null; then
    OUTPUT_SIZE_GT_ZERO=1
fi

# Gate 4: output sha256.
if [ "$OUTPUT_EXISTS" = "1" ] && [ "$OUTPUT_SIZE_GT_ZERO" = "1" ]; then
    OUTPUT_SHA256=$(sha256sum "$OUTPUT_JSON" 2>/dev/null | cut -d ' ' -f 1 || shasum -a 256 "$OUTPUT_JSON" 2>/dev/null | cut -d ' ' -f 1 || echo "")
fi

# Gate 5: parse output with python3 -m json.tool.
JSON_VALID=0
if [ "$OUTPUT_EXISTS" = "1" ] && [ "$OUTPUT_SIZE_GT_ZERO" = "1" ]; then
    set +e
    python3 -m json.tool "$OUTPUT_JSON" > "$RESULT_DIR/output_parsed.json" 2> "$RESULT_DIR/output_parse.stderr"
    JSON_VALID=$?
    set -e
fi

# Gate 6: run the supplied validator.
VALIDATOR_EXIT_CODE=0
VALIDATOR_STDOUT=""
VALIDATOR_STDERR=""
if [ "$JSON_VALID" = "0" ]; then
    set +e
    VALIDATOR_STDOUT=$("$VALIDATOR" "$OUTPUT_JSON" > "$RESULT_DIR/validator.stdout" 2> "$RESULT_DIR/validator.stderr"; echo $?)
    VALIDATOR_EXIT_CODE=$?
    set -e
fi

# Gate 7: scan Ghidra log for forbidden markers.
FORBIDDEN_LOG_MARKERS=""
if [ -f "$GHIDRA_LOG" ]; then
    FORBIDDEN_LOG_MARKERS=$(grep -E 'ERROR|SCRIPT ERROR|ClassNotFound|compilation error|uncaught exception' "$GHIDRA_LOG" 2>/dev/null || true)
fi
FORBIDDEN_COUNT=0
if [ -n "$FORBIDDEN_LOG_MARKERS" ]; then
    FORBIDDEN_COUNT=$(printf '%s\n' "$FORBIDDEN_LOG_MARKERS" | grep -c . || true)
fi

# Final status: all gates must pass.
FINAL_STATUS="FAIL"
if [ "$PROCESS_EXIT_CODE" = "0" ] && \
   [ "$OUTPUT_EXISTS" = "1" ] && \
   [ "$OUTPUT_SIZE_GT_ZERO" = "1" ] && \
   [ "$JSON_VALID" = "0" ] && \
   [ "$VALIDATOR_EXIT_CODE" = "0" ] && \
   [ "$FORBIDDEN_COUNT" = "0" ]; then
    FINAL_STATUS="PASS"
fi

# Deterministic smoke_result.json with no timestamps.
cat > "$RESULT_FILE" <<JSON
{
  "collector": "$COLLECTOR_SCRIPT",
  "process_exit_code": $PROCESS_EXIT_CODE,
  "output_exists": $OUTPUT_EXISTS,
  "output_size": $OUTPUT_SIZE,
  "output_sha256": "$OUTPUT_SHA256",
  "json_valid": $JSON_VALID,
  "validator_exit_code": $VALIDATOR_EXIT_CODE,
  "forbidden_log_markers": $FORBIDDEN_COUNT,
  "final_status": "$FINAL_STATUS"
}
JSON

# Return non-zero unless every gate passes.
if [ "$FINAL_STATUS" = "PASS" ]; then
    exit 0
else
    exit 1
fi