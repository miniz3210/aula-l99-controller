#!/usr/bin/env python3
"""Offline image-level self-checksum scanner for UartTFT-II_Flash.bin.

Read-only: opens the input file only for reading. Never writes or modifies
the input file. All checksum candidates are computed over structurally
justified byte ranges and compared against stored values at specific,
plausible field offsets within those ranges.

A match is only reported when a computed checksum equals a stored u16/u32
LE value at a specific offset inside the region (e.g. the last 4 bytes of
a section, or a header word). Scanning for "the value appears anywhere in
the byte range" is deliberately NOT done, because a 16-bit value over a
64 KiB range is statistically likely to appear somewhere by chance.

Modes:
  --mode quick   Normal validation/release checks. No exploratory whole-image
                 candidate scanning. Target runtime under 30 seconds on the
                 127,599,044-byte factory image.
  --mode deep    Full structural checksum investigation. Cached by input
                 hashes so identical inputs return instantly.

Usage:
  python scripts/flash_checksum_scanner.py <image.bin> [--factory <factory.bin>] [--patched <patched.bin>] [--mode quick|deep] [--max-runtime SECONDS] [--workers N] [--cache-dir DIR]

Classification:
  VERIFIED_PRESENT   - a stored field at a specific offset matches a computed
                        checksum over its structurally justified coverage range.
  VERIFIED_ABSENT_FROM_KNOWN_FORMAT - no stored field matches any tested
                        candidate at any plausible field offset over any
                        structurally justified range, and the factory-vs-patched
                        comparison shows no field that should change (but does not).
  UNKNOWN            - inconclusive; lack of a match is not proof of absence.
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# --- Factory image identity (reference only; never modified) ---
FACTORY_SIZE = 127599044
FACTORY_SHA256 = "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4"

SCANNER_VERSION = "2.0.0"

# Known structural regions from image-format.md (softce research).
# Offsets are file offsets. end=None means bounds not fixed in docs.
REGIONS = {
    "main_header": (0x00000000, 0x00000058),
    "page_table": (0x00021DD0, 0x00021DD0 + 30 * 12),
    "startup_animation": (0x04240000, 0x05B0D07C),
    "first_64kiB": (0x00000000, 0x00010000),
    "last_64kiB": None,  # computed relative to file size
}

DESCRIPTOR_ENTRY_SIZE = 12
HEADER_WORD_COUNT = 23

DEFAULT_MAX_RUNTIME = 1800  # 30 minutes deep-mode guard
QUICK_TARGET_SECONDS = 30

ALGORITHMS = [
    "CRC16/MODBUS",
    "CRC32/reflected_IEEE_init0_xorout0",
    "CRC32/standard",
    "additive_sum16",
    "additive_sum32",
]

# Cache file name (inside --cache-dir).
CACHE_FILENAME = "flash_checksum_scanner_cache.json"


def read_file(path: Path) -> bytes:
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Checksum algorithms (C-backed or lookup-table based)
# ---------------------------------------------------------------------------

_CRC16_TABLE = None


def _crc16_table() -> list:
    global _CRC16_TABLE
    if _CRC16_TABLE is None:
        table = []
        for n in range(256):
            c = n
            for _ in range(8):
                c = ((c >> 1) ^ 0xA001) & 0xFFFF if c & 1 else (c >> 1) & 0xFFFF
            table.append(c)
        _CRC16_TABLE = table
    return _CRC16_TABLE


_crc16_table()


def crc16_modbus(data: bytes) -> int:
    """Bit-by-bit CRC-16/MODBUS: reflected poly 0xA001, init 0xFFFF, xorout 0.

    Kept for backward compatibility; prefer crc16_modbus_fast for large inputs.
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def crc16_modbus_fast(data: bytes) -> int:
    """Table-based CRC-16/MODBUS: reflected poly 0xA001, init 0xFFFF, xorout 0."""
    table = _CRC16_TABLE
    crc = 0xFFFF
    for b in data:
        crc = (crc >> 8) ^ table[(crc ^ b) & 0xFF]
    return crc & 0xFFFF


def crc32_reflected_ieee(data: bytes) -> int:
    """CRC-32 reflected IEEE via zlib (native C-backed): poly 0xEDB88320, init 0, xorout 0."""
    return zlib.crc32(data) & 0xFFFFFFFF


_CRC32_STD_TABLE = None


def _crc32_std_table() -> list:
    global _CRC32_STD_TABLE
    if _CRC32_STD_TABLE is None:
        table = []
        for n in range(256):
            c = n << 24
            for _ in range(8):
                c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if c & 0x80000000 else (c << 1) & 0xFFFFFFFF
            table.append(c)
        _CRC32_STD_TABLE = table
    return _CRC32_STD_TABLE


_crc32_std_table()


def crc32_standard(data: bytes) -> int:
    """Standard CRC-32 (non-reflected), init 0xFFFFFFFF, xorout 0xFFFFFFFF."""
    table = _CRC32_STD_TABLE
    crc = 0xFFFFFFFF
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ table[((crc >> 24) ^ b) & 0xFF]
    return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF


def addsum16(data: bytes) -> int:
    return sum(data) & 0xFFFF


def addsum32(data: bytes) -> int:
    return sum(data) & 0xFFFFFFFF


_ALGO_FUNCS = {
    "CRC16/MODBUS": crc16_modbus_fast,
    "CRC32/reflected_IEEE_init0_xorout0": crc32_reflected_ieee,
    "CRC32/standard": crc32_standard,
    "additive_sum16": addsum16,
    "additive_sum32": addsum32,
}


def u16le(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32le(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def region_bounds(data_len: int, spec) -> tuple | None:
    """Resolve a (start, end) region spec into absolute bounds, or None if unknown."""
    if spec is None:
        return None
    start, end = spec
    if end is None:
        return None
    if start < 0 or end > data_len or start >= end:
        return None
    return (start, end)


def last_64kib(data_len) -> tuple:
    n = data_len if isinstance(data_len, int) else len(data_len)
    start = max(0, n - 65536)
    return (start, n)


def candidate_offsets(start: int, end: int) -> list:
    """Plausible offsets within [start, end) where a checksum field could be stored.

    Only fixed, structural positions: the final u32/u16 of the region, and
    (for header-sized regions) each header word. Offsets are absolute file offsets.
    """
    offs = []
    if end - start >= 4:
        offs.append(end - 4)
    if end - start >= 2:
        offs.append(end - 2)
    if end - start >= 4:
        offs.append(start)
    if end - start >= 2:
        offs.append(start)
    return sorted(set(offs))


def read_stored(data: bytes, off: int, width: int) -> int | None:
    if off < 0 or off + width > len(data):
        return None
    if width == 2:
        return u16le(data, off)
    if width == 4:
        return u32le(data, off)
    return None


def compute_region_checksums(section: bytes, region_len: int, algos: list) -> dict:
    """Compute each algorithm once over the region, with each candidate field zeroed.

    Returns dict mapping algorithm name -> {(rel_off, width): computed_value},
    where rel_off is relative to the region start.
    """
    offsets = candidate_offsets(0, region_len)
    results = {}
    for algo in algos:
        func = _ALGO_FUNCS[algo]
        computed_by_offset = {}
        for off in offsets:
            rel = off  # relative to region start (0)
            # u32 field
            if rel + 4 <= region_len:
                zeroed = bytearray(section)
                zeroed[rel:rel + 4] = b"\x00\x00\x00\x00"
                computed_by_offset[(rel, 4)] = func(bytes(zeroed)) & 0xFFFFFFFF
            # u16 field
            if rel + 2 <= region_len:
                zeroed16 = bytearray(section)
                zeroed16[rel:rel + 2] = b"\x00\x00"
                computed_by_offset[(rel, 2)] = func(bytes(zeroed16)) & 0xFFFF
        results[algo] = computed_by_offset
    return results


def scan_region(data: bytes, region_name: str, spec, results: list, algos: list | None = None) -> None:
    """Backward-compatible in-memory region scan (kept for existing tests).

    Appends a single region result dict to `results`. When `algos` is None the
    default algorithm list is used.
    """
    if algos is None:
        algos = ALGORITHMS
    n = len(data)
    bounds = region_bounds(n, spec)
    if bounds is None:
        results.append({
            "region": region_name,
            "status": "SKIPPED_UNKNOWN_BOUNDS",
            "detail": "region bounds not fixed / cannot resolve from docs alone",
        })
        return
    start, end = bounds
    section = data[start:end]
    region_len = end - start
    precomputed = compute_region_checksums(section, region_len, algos)

    matches = []
    offsets = candidate_offsets(0, region_len)
    for algo in algos:
        computed_by_offset = precomputed[algo]
        for rel in offsets:
            abs_off = start + rel
            if rel + 4 <= region_len:
                stored = read_stored(section, rel, 4)
                if stored is not None and computed_by_offset.get((rel, 4)) == stored:
                    matches.append({
                        "algorithm": algo,
                        "computed": computed_by_offset[(rel, 4)],
                        "stored": stored,
                        "offset": abs_off,
                        "width": 4,
                        "match_kind": "zeroed_field_at_offset",
                    })
            if rel + 2 <= region_len:
                stored = read_stored(section, rel, 2)
                if stored is not None and computed_by_offset.get((rel, 2)) == stored:
                    matches.append({
                        "algorithm": algo,
                        "computed": computed_by_offset[(rel, 2)],
                        "stored": stored,
                        "offset": abs_off,
                        "width": 2,
                        "match_kind": "zeroed_field_at_offset",
                    })
    results.append({
        "region": region_name,
        "range_start": start,
        "range_end": end,
        "range_len": region_len,
        "matches": matches,
        "status": "MATCH" if matches else "NO_MATCH",
    })


def find_region_matches(data_path: str, region_name: str, start: int, end: int, algos: list) -> dict:
    """Scan one structural region for stored-field checksum matches.

    Reads only its own byte range from disk so the full image is never
    pickled across process boundaries.
    """
    with open(data_path, "rb") as f:
        f.seek(start)
        section = f.read(end - start)
    region_len = end - start
    offsets = candidate_offsets(0, region_len)
    precomputed = compute_region_checksums(section, region_len, algos)

    matches = []
    for algo in algos:
        computed_by_offset = precomputed[algo]
        for rel in offsets:
            abs_off = start + rel
            if rel + 4 <= region_len:
                stored = read_stored(section, rel, 4)
                if stored is not None and computed_by_offset.get((rel, 4)) == stored:
                    matches.append({
                        "algorithm": algo,
                        "computed": computed_by_offset[(rel, 4)],
                        "stored": stored,
                        "offset": abs_off,
                        "width": 4,
                        "match_kind": "zeroed_field_at_offset",
                    })
            if rel + 2 <= region_len:
                stored = read_stored(section, rel, 2)
                if stored is not None and computed_by_offset.get((rel, 2)) == stored:
                    matches.append({
                        "algorithm": algo,
                        "computed": computed_by_offset[(rel, 2)],
                        "stored": stored,
                        "offset": abs_off,
                        "width": 2,
                        "match_kind": "zeroed_field_at_offset",
                    })

    return {
        "region": region_name,
        "range_start": start,
        "range_end": end,
        "range_len": region_len,
        "matches": matches,
        "status": "MATCH" if matches else "NO_MATCH",
    }


def header_words_checks(data: bytes, algos_or_results) -> dict:
    """Cross-check header words against whole-image checksums and file length.

    Accepts either an algorithm list (returns a dict) or, for backward
    compatibility with existing tests, a results list to which a single
    region dict is appended.
    """
    # Backward-compatible mode: second arg is a results list (list of dicts).
    if isinstance(algos_or_results, list) and all(isinstance(x, dict) for x in algos_or_results):
        results = algos_or_results
        algos = ALGORITHMS
        res = _header_words_checks_impl(data, algos)
        results.append(res)
        return res
    return _header_words_checks_impl(data, algos_or_results)


def _header_words_checks_impl(data: bytes, algos: list) -> dict:
    """Cross-check header words against whole-image checksums and file length."""
    n = len(data)
    hw_count = min(HEADER_WORD_COUNT, n // 4)

    computed_full = {}
    computed_zeroed = {}
    zeroed_header = bytearray(n)
    zeroed_header[:n] = data[:n]
    for i in range(hw_count):
        zeroed_header[i * 4:i * 4 + 4] = b"\x00" * 4
    zeroed_header_bytes = bytes(zeroed_header)

    full_mask = {}
    for algo in algos:
        full_mask[algo] = 0xFFFFFFFF if (algo.startswith("CRC32") or algo.startswith("additive_sum32")) else 0xFFFF

    for algo in algos:
        func = _ALGO_FUNCS[algo]
        computed_full[algo] = func(data) & full_mask[algo]
        computed_zeroed[algo] = func(zeroed_header_bytes) & full_mask[algo]

    matches = []
    for algo_name in algos:
        computed = computed_full[algo_name]
        for idx in range(hw_count):
            off = idx * 4
            w = u32le(data, off)
            if computed == w:
                matches.append({
                    "algorithm": algo_name,
                    "computed": computed,
                    "stored": w,
                    "offset": off,
                    "width": 4,
                    "match_kind": "full_image_at_header_word",
                })
            if (computed & 0xFFFF) == (w & 0xFFFF):
                matches.append({
                    "algorithm": algo_name,
                    "computed": computed,
                    "stored": w & 0xFFFF,
                    "offset": off,
                    "width": 2,
                    "match_kind": "full_image_low16_at_header_word",
                })
    for algo_name in algos:
        computed = computed_zeroed[algo_name]
        for idx in range(hw_count):
            off = idx * 4
            w = u32le(data, off)
            if computed == w:
                matches.append({
                    "algorithm": algo_name,
                    "computed": computed,
                    "stored": w,
                    "offset": off,
                    "width": 4,
                    "match_kind": "zeroed_header_at_header_word",
                })
            if (computed & 0xFFFF) == (w & 0xFFFF):
                matches.append({
                    "algorithm": algo_name,
                    "computed": computed,
                    "stored": w & 0xFFFF,
                    "offset": off,
                    "width": 2,
                    "match_kind": "zeroed_header_low16_at_header_word",
                })
    # File length stored in any header word.
    for idx in range(hw_count):
        w = u32le(data, idx * 4)
        if n == w:
            matches.append({
                "algorithm": "file_length",
                "computed": n,
                "stored": w,
                "offset": idx * 4,
                "width": 4,
                "match_kind": "exact_at_header_word",
            })

    range_end = min(HEADER_WORD_COUNT * 4, n)
    return {
        "region": "header_words_vs_whole_image",
        "range_start": 0,
        "range_end": range_end,
        "range_len": range_end,
        "matches": matches,
        "status": "MATCH" if matches else "NO_MATCH",
    }


def factory_vs_patched(factory: bytes, patched: bytes) -> dict:
    if len(factory) != len(patched):
        return {
            "check": "factory_vs_patched_size",
            "status": "MISMATCH",
            "detail": f"factory size {len(factory)} != patched size {len(patched)}",
        }
    diffs = [i for i in range(len(factory)) if factory[i] != patched[i]]
    ranges = []
    if diffs:
        s = prev = diffs[0]
        for i in diffs[1:]:
            if i == prev + 1:
                prev = i
            else:
                ranges.append((s, prev))
                s = prev = i
        ranges.append((s, prev))
    return {
        "check": "factory_vs_patched",
        "status": "ANALYZED",
        "num_changed_bytes": len(diffs),
        "changed_ranges": [
            {"start": s, "end": e, "len": e - s + 1} for s, e in ranges
        ],
        "detail": f"{len(diffs)} bytes changed across {len(ranges)} range(s)",
    }


def classify(region_results: list) -> str:
    if any(r["status"] == "MATCH" for r in region_results):
        return "VERIFIED_PRESENT"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Deep-scan worker (runs in a separate process)
# ---------------------------------------------------------------------------

def _scan_region_worker(args):
    data_path, region_name, start, end, algos = args
    return find_region_matches(data_path, region_name, start, end, algos)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def scanner_source_sha256() -> str:
    here = Path(__file__).resolve()
    return sha256_file(here)


def region_map_sha256() -> str:
    payload = json.dumps(REGIONS, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def cache_key(factory_sha: str, patched_sha: str, algos: list) -> str:
    h = hashlib.sha256()
    h.update(factory_sha.encode())
    h.update(b"|")
    h.update(patched_sha.encode())
    h.update(b"|")
    h.update(SCANNER_VERSION.encode())
    h.update(b"|")
    h.update(scanner_source_sha256().encode())
    h.update(b"|")
    h.update(",".join(algos).encode())
    h.update(b"|")
    h.update(region_map_sha256().encode())
    return h.hexdigest()


def cache_load(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / CACHE_FILENAME
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            all_cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    entry = all_cache.get(key)
    if entry is None:
        return None
    return entry


def cache_save(cache_dir: Path, key: str, entry: dict) -> None:
    path = cache_dir / CACHE_FILENAME
    all_cache = {}
    try:
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                all_cache = json.load(f)
    except (json.JSONDecodeError, OSError):
        all_cache = {}
    all_cache[key] = entry
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_cache, f, indent=2, sort_keys=True)
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def phase(msg: str, start: float) -> None:
    elapsed = time.time() - start
    print(f"[PHASE] {msg}  elapsed={elapsed:.3f}s")


def print_results(results, fvp, classification, image_path, n, image_sha,
                  overall_start, full_image_passes, workers, cache_hit):
    print("=" * 72)
    print("OFFLINE IMAGE-LEVEL SELF-CHECKSUM SCANNER")
    print("=" * 72)
    print(f"Image:        {image_path}")
    print(f"Size:         {n} bytes (0x{n:08X})")
    print(f"SHA-256:      {image_sha}")
    print(f"Factory size: {FACTORY_SIZE} (0x{FACTORY_SIZE:08X})")
    print(f"Size matches: {n == FACTORY_SIZE}")
    print()
    print("Regions scanned:")
    for r in results:
        if "range_start" not in r:
            continue
        flag = ">> MATCH" if r["status"] == "MATCH" else "    no match"
        if r["status"] == "SKIPPED_UNKNOWN_BOUNDS":
            flag = "    skipped"
        print(f"  {flag:12s} {r['region']:40s} [{r['range_start']:#010X}..{r['range_end']:#010X}] len={r['range_len']}")
        for m in r.get("matches", []):
            print(
                f"             MATCH: algo={m['algorithm']} "
                f"computed=0x{m['computed']:08X} stored=0x{m['stored']:08X} "
                f"offset=0x{m['offset']:08X} width={m['width']} kind={m['match_kind']}"
            )
    print()
    if fvp and fvp.get("status") == "ANALYZED":
        print("Factory vs patched comparison:")
        print(f"  Status: {fvp['status']}")
        print(f"  Changed bytes: {fvp['num_changed_bytes']}")
        print(f"  Changed ranges: {fvp['changed_ranges']}")
        print()
    print(f"Classification: {classification}")
    print()
    print("Limitations:")
    print("  - Only structurally justified ranges with FIXED bounds are tested.")
    print("  - Regions whose bounds are not fixed in image-format.md (widget records,")
    print("    font table, sound table, animation table, background descriptors,")
    print("    descriptor bank1, UI projects 2-4) are SKIPPED_UNKNOWN_BOUNDS.")
    print("  - A match requires the computed checksum to equal a stored u16/u32 at a")
    print("    specific plausible field offset (first/last u16/u32 of the region, or")
    print("    any header word). Birthday-paradox 'value appears anywhere in the range'")
    print("  matches are NOT reported, since a 16-bit value over 64 KiB is statistically")
    print("    likely to appear somewhere by chance.")
    print("  - Lack of a stored-field match is NOT proof that no image-level")
    print("    self-checksum exists (per project policy).")
    print("  - Per-packet CRC32 (reflected IEEE, init=0, xorout=0) is verified in the")
    print("    ISP tools but is separate from any image-level self-checksum; it is not")
    print("    tested here as a stored BIN field.")
    print()
    print(f"[TIMING] Total elapsed: {time.time() - overall_start:.3f}s  full-image passes: {full_image_passes}  workers: {workers}  cache_hit: {cache_hit}")
    print()
    print("Decision rule: GO requires VERIFIED_PRESENT or explicit confirmation")
    print("that no image-level self-checksum is required. Current decision: NO-GO.")
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline image-level self-checksum scanner for UartTFT-II_Flash.bin"
    )
    parser.add_argument("image", help="Path to UartTFT-II_Flash.bin to scan")
    parser.add_argument("--factory", help="Path to factory image for comparison")
    parser.add_argument("--patched", help="Path to patched image for comparison")
    parser.add_argument("--mode", choices=["quick", "deep"], default="quick",
                        help="quick: targeted structural checks (default); deep: full investigation with cache")
    parser.add_argument("--max-runtime", type=float, default=DEFAULT_MAX_RUNTIME,
                        help="Maximum runtime in seconds before aborting (deep mode guard)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Worker processes (default: min(8, physical CPU cores))")
    parser.add_argument("--cache-dir", default=".checksum_cache",
                        help="Directory for deep-mode cache")
    args = parser.parse_args()

    overall_start = time.time()

    # Determine worker count: min(8, physical cores), never ThreadPoolExecutor for CPU work.
    if args.workers is not None:
        workers = max(1, args.workers)
    else:
        try:
            physical = os.cpu_count() or 1
            workers = min(8, max(1, physical))
        except Exception:
            workers = 1

    image_path = Path(args.image)
    if not image_path.is_file():
        raise SystemExit(f"File not found: {image_path}")

    # Read the image once; keep bytes for whole-image checks.
    data = read_file(image_path)
    n = len(data)
    image_sha = sha256_hex(data)

    print("=" * 72)
    print("OFFLINE IMAGE-LEVEL SELF-CHECKSUM SCANNER")
    print("=" * 72)
    print(f"Image:        {image_path}")
    print(f"Size:         {n} bytes (0x{n:08X})")
    print(f"SHA-256:      {image_sha}")
    print(f"Mode:         {args.mode}")
    print(f"Workers:      {workers}")
    print(f"Factory size: {FACTORY_SIZE} (0x{FACTORY_SIZE:08X})")
    print(f"Size matches: {n == FACTORY_SIZE}")
    print()

    results = []
    fvp = None
    full_image_passes = 0
    cache_hit = False
    cache_dir = Path(args.cache_dir)

    regions = dict(REGIONS)
    regions["last_64kiB"] = last_64kib(n)

    quick_region_list = [
        "main_header",
        "page_table",
        "first_64kiB",
        "last_64kiB",
        "header_words_vs_whole_image",
    ]
    # startup_animation excluded from quick mode (no exploratory whole-image scanning).

    if args.mode == "deep":
        # Cache key includes factory SHA-256, patched SHA-256, scanner version,
        # scanner source SHA-256, algorithm list, region-map SHA-256.
        factory_sha = ""
        patched_sha = ""
        if args.factory and Path(args.factory).is_file():
            factory_sha = sha256_file(Path(args.factory))
        if args.patched and Path(args.patched).is_file():
            patched_sha = sha256_file(Path(args.patched))
        key = cache_key(factory_sha, patched_sha, ALGORITHMS)
        cached = cache_load(cache_dir, key)
        if cached is not None:
            cache_hit = True
            print(f"[CACHE] HIT (key={key[:16]}...)")
            phase("cache load", overall_start)
            results = cached.get("results", [])
            classification = cached.get("classification", "UNKNOWN")
            full_image_passes = cached.get("full_image_passes", 0)
            fvp = cached.get("factory_vs_patched")
            print_results(results, fvp, classification, image_path, n, image_sha,
                          overall_start, full_image_passes, workers, cache_hit)
            return 0 if classification in ("VERIFIED_PRESENT", "VERIFIED_ABSENT_FROM_KNOWN_FORMAT") else 1
        else:
            print(f"[CACHE] MISS (key={key[:16]}...)")
            phase("cache miss", overall_start)

    # Determine which regions to scan.
    if args.mode == "quick":
        scan_specs = {name: regions[name] for name in quick_region_list if name in regions}
        print(f"[QUICK] Scanning {len(scan_specs)} structural regions (no exploratory whole-image scan).")
    else:
        scan_specs = regions
        print(f"[DEEP] Scanning {len(scan_specs)} structural regions (full investigation).")

    phase("setup", overall_start)
    deadline = overall_start + args.max_runtime

    # Build region scan jobs. Each algorithm computed once per region.
    region_jobs = []
    for name, spec in scan_specs.items():
        if name == "header_words_vs_whole_image":
            continue  # handled separately below
        bounds = region_bounds(n, spec)
        if bounds is None:
            results.append({
                "region": name,
                "status": "SKIPPED_UNKNOWN_BOUNDS",
                "detail": "region bounds not fixed / cannot resolve from docs alone",
            })
            continue
        start, end = bounds
        region_jobs.append((str(image_path), name, start, end, ALGORITHMS))

    # Parallelise independent region jobs with ProcessPoolExecutor.
    if region_jobs:
        print(f"[WORKERS] Dispatching {len(region_jobs)} region jobs across {workers} worker process(es).")
        phase("dispatch", overall_start)
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_scan_region_worker, job) for job in region_jobs]
            for fut in as_completed(futures):
                if time.time() > deadline:
                    print(f"[GUARD] Max runtime {args.max_runtime}s reached; stopping scan.")
                    break
                results.append(fut.result())
        phase("region scans", overall_start)

    # Header words vs whole image (computed once over whole image).
    # Quick mode uses only fast/native whole-image algorithms to stay under
    # the 30-second target; deep mode uses the full algorithm set.
    if args.mode == "quick":
        whole_image_algos = ["CRC32/reflected_IEEE_init0_xorout0", "additive_sum16", "additive_sum32"]
    else:
        whole_image_algos = ALGORITHMS
    if time.time() <= deadline:
        hw = header_words_checks(data, whole_image_algos)
        full_image_passes += 1
        results.append(hw)
        phase("header words vs whole image", overall_start)

    # Factory vs patched comparison.
    if args.factory and args.patched:
        fp = Path(args.factory)
        pp = Path(args.patched)
        if fp.is_file() and pp.is_file():
            factory = read_file(fp)
            patched = read_file(pp)
            fvp = factory_vs_patched(factory, patched)
            results.append(fvp)
            phase("factory vs patched", overall_start)

    classification = classify(results)
    elapsed = time.time() - overall_start
    print()
    print(f"[TIMING] Total elapsed: {elapsed:.3f}s  full-image passes: {full_image_passes}  workers: {workers}  cache_hit: {cache_hit}")

    if args.mode == "deep" and not cache_hit:
        entry = {
            "results": results,
            "classification": classification,
            "factory_vs_patched": fvp,
            "full_image_passes": full_image_passes,
            "workers": workers,
            "elapsed": elapsed,
        }
        cache_save(cache_dir, key, entry)
        print(f"[CACHE] Saved deep result to {cache_dir / CACHE_FILENAME}")

    print_results(results, fvp, classification, image_path, n, image_sha,
                  overall_start, full_image_passes, workers, cache_hit)

    return 0 if classification in ("VERIFIED_PRESENT", "VERIFIED_ABSENT_FROM_KNOWN_FORMAT") else 1


if __name__ == "__main__":
    sys.exit(main())
