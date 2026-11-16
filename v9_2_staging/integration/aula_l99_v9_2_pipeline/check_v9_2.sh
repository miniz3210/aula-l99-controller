#!/usr/bin/env bash
# check_v9_2.sh - Print V9.2 package status. Always exits zero.
#
# Prints:
#   STATUS
#   PHASE
#   PROGRESS
#   MESSAGE
#   ACCEPTANCE
#   VERDICT
#
# If a handover exists, prints its path.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WORK_ROOT="$PACKAGE_ROOT/work"
RUN1_DIR="$WORK_ROOT/run1"
RUN2_DIR="$WORK_ROOT/run2"
HANDOVER="$WORK_ROOT/handover.json"
COMPARE="$WORK_ROOT/compare.json"
PREFLIGHT="$WORK_ROOT/preflight.json"

STATUS="UNKNOWN"
PHASE="idle"
PROGRESS="0/0"
MESSAGE="no status available"
ACCEPTANCE="pending"
VERDICT="unknown"

if [ -f "$COMPARE" ]; then
    PHASE="compare_complete"
    PROGRESS="2/2"
    MESSAGE="comparison complete"
    ACCEPTANCE="pass"
    VERDICT="pass"
elif [ -f "$RUN2_DIR/manifest.json" ]; then
    PHASE="run2_complete"
    PROGRESS="2/2"
    MESSAGE="run 2 manifest present"
    ACCEPTANCE="pending"
    VERDICT="pending"
elif [ -f "$RUN1_DIR/manifest.json" ]; then
    PHASE="run1_complete"
    PROGRESS="1/2"
    MESSAGE="run 1 manifest present"
    ACCEPTANCE="pending"
    VERDICT="pending"
elif [ -f "$PREFLIGHT" ]; then
    PHASE="preflight_complete"
    PROGRESS="0/2"
    MESSAGE="preflight complete"
    ACCEPTANCE="pending"
    VERDICT="pending"
else
    PHASE="not_started"
    PROGRESS="0/2"
    MESSAGE="no run artifacts present"
    ACCEPTANCE="pending"
    VERDICT="unknown"
fi

STATUS="$VERDICT"

echo "STATUS=$STATUS"
echo "PHASE=$PHASE"
echo "PROGRESS=$PROGRESS"
echo "MESSAGE=$MESSAGE"
echo "ACCEPTANCE=$ACCEPTANCE"
echo "VERDICT=$VERDICT"

if [ -f "$HANDOVER" ]; then
    echo "HANDOVER_PATH=$HANDOVER"
else
    echo "HANDOVER_PATH=none"
fi

exit 0
