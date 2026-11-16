#!/usr/bin/env bash
# collect_failure_evidence.sh - Print or package bounded failure evidence.
# No firmware or accepted artifacts are included.
set -uo pipefail

usage() {
    cat <<EOF
Usage: collect_failure_evidence.sh [--result-dir <path>] [--package <tar path>]
  --result-dir <path>   Directory containing smoke results (default: ./)
  --package <tar path>  Optionally create a tar package of bounded evidence.
  --help|-h             Show this help.
EOF
}

RESULT_DIR="./"
PACKAGE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --result-dir) RESULT_DIR="$2"; shift 2 ;;
        --package) PACKAGE="$2"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        --*) echo "Unknown option: $1" >&2; usage; exit 2 ;;
        *) echo "Unexpected argument: $1" >&2; usage; exit 2 ;;
    esac
done

EVIDENCE_DIR="$RESULT_DIR/evidence_bundle_$$"
mkdir -p "$EVIDENCE_DIR"

# Collect smoke_result.json files.
echo "=== smoke_result.json files ==="
FOUND=0
while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    FOUND=1
    echo "--- $f ---"
    cat "$f" 2>/dev/null || echo "(unreadable)"
    echo
    cp -f "$f" "$EVIDENCE_DIR/" 2>/dev/null || true
done < <(find "$RESULT_DIR" -maxdepth 2 -name smoke_result.json -print0 2>/dev/null | sort -z || true)

if [ "$FOUND" = "0" ]; then
    echo "(none found)"
fi

# Collect status files.
echo "=== status files ==="
while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    echo "--- $f ---"
    cat "$f" 2>/dev/null || echo "(unreadable)"
    echo
    cp -f "$f" "$EVIDENCE_DIR/" 2>/dev/null || true
done < <(find "$RESULT_DIR" -maxdepth 2 -name '*.status' -o -name 'status_*' -print0 2>/dev/null | sort -z || true) 2>/dev/null || true

# Collect Ghidra log tails.
echo "=== Ghidra log tails ==="
while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    echo "--- $f (tail) ---"
    tail -n 100 "$f" 2>/dev/null || echo "(unreadable)"
    echo
    cp -f "$f" "$EVIDENCE_DIR/" 2>/dev/null || true
done < <(find "$RESULT_DIR" -maxdepth 2 -name '*.log' -print0 2>/dev/null | sort -z || true) 2>/dev/null || true

# Collect output sizes and hashes.
echo "=== output sizes and hashes ==="
while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    echo "--- $f ---"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$f"
        stat -c '%s %n' "$f"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$f"
        stat -f '%z %N' "$f"
    else
        echo "(no hash tool available)"
    fi
    echo
done < <(find "$RESULT_DIR" -maxdepth 2 -name '*.json' -print0 2>/dev/null | sort -z || true) 2>/dev/null || true

# Collect validator stdout and stderr.
echo "=== validator stdout and stderr ==="
for f in "$RESULT_DIR"/validator.stdout "$RESULT_DIR"/validator.stderr; do
    [ -f "$f" ] || continue
    echo "--- $f ---"
    cat "$f" 2>/dev/null || echo "(unreadable)"
    echo
    cp -f "$f" "$EVIDENCE_DIR/" 2>/dev/null || true
done

# Package checksum status if available.
echo "=== package checksum status ==="
if [ -n "$PACKAGE" ] && [ -f "$PACKAGE" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$PACKAGE"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$PACKAGE"
    else
        echo "(no hash tool available)"
    fi
else
    echo "(no package path provided or package not found)"
fi

# Optionally create a tar package of bounded evidence (no firmware, no accepted artifacts).
if [ -n "$PACKAGE" ]; then
    if command -v tar >/dev/null 2>&1; then
        tar -cf "$PACKAGE" -C "$RESULT_DIR" "$(basename "$EVIDENCE_DIR")" 2>/dev/null || true
        echo "PACKAGE_CREATED=$PACKAGE"
    else
        echo "PACKAGE_CREATE_FAILED=tar not available"
    fi
fi

# Cleanup staging evidence dir unless packaged.
if [ -z "$PACKAGE" ]; then
    rm -rf "$EVIDENCE_DIR" 2>/dev/null || true
fi

exit 0