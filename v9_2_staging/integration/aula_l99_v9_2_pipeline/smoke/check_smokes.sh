#!/usr/bin/env bash
# check_smokes.sh - Print smoke status summary. Always exits zero.
set -uo pipefail

usage() {
    cat <<EOF
Usage: check_smokes.sh [--result-dir <path>]
  --result-dir <path>   Directory containing smoke_result.json files (default: ./)
  --help|-h             Show this help.
EOF
}

RESULT_DIR="./"

while [ $# -gt 0 ]; do
    case "$1" in
        --result-dir) RESULT_DIR="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *) echo "Unexpected argument: $1" >&2; usage; exit 2 ;;
    esac
done

STATUS="NO_SMOKES"
CURRENT_COLLECTOR=""
COMPLETED_COUNT=0
FAILED_COUNT=0
LAST_MESSAGE=""

# Collect smoke_result.json files deterministically (sorted).
RESULTS=()
while IFS= read -r -d '' f; do
    RESULTS+=("$f")
done < <(find "$RESULT_DIR" -maxdepth 2 -name smoke_result.json -print0 2>/dev/null | sort -z || true)

for f in "${RESULTS[@]:-}"; do
    [ -n "$f" ] || continue
    [ -f "$f" ] || continue
    COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
    STATUS_LINE=$(python3 - "$f" <<'PY'
import json, sys
with open(sys.argv[1]) as fh:
    d = json.load(fh)
print(d.get("collector", ""))
print(d.get("final_status", ""))
PY
    ) || STATUS_LINE=$'\n\n'
    COLLECTOR=$(printf '%s' "$STATUS_LINE" | head -n 1)
    FINAL_STATUS=$(printf '%s' "$STATUS_LINE" | sed -n '2p')
    CURRENT_COLLECTOR="$COLLECTOR"
    if [ "$FINAL_STATUS" = "PASS" ]; then
        :
    else
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
    LAST_MESSAGE="$COLLECTOR: final_status=${FINAL_STATUS:-unknown}"
done

if [ "$COMPLETED_COUNT" = "0" ]; then
    STATUS="NO_SMOKES"
elif [ "$FAILED_COUNT" = "0" ]; then
    STATUS="ALL_PASS"
else
    STATUS="PARTIAL_FAIL"
fi

echo "STATUS=$STATUS"
echo "CURRENT_COLLECTOR=$CURRENT_COLLECTOR"
echo "COMPLETED_COUNT=$COMPLETED_COUNT"
echo "FAILED_COUNT=$FAILED_COUNT"
echo "LAST_MESSAGE=$LAST_MESSAGE"

exit 0