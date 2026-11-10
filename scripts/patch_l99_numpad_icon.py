#!/usr/bin/env python3
"""Offline-only ARGB4444 encoder and working-copy patcher for AULA L99 Page 21 NumPad 1 icons.

Encodes two 67x67 RGBA PNGs (--normal, --pressed) as the verified ARGB4444 record
format and patches them into a separate working-copy image at the verified descriptor
341 / 342 encoded ranges. Never modifies the factory image. Never opens USB, COM,
HID, or any updater.

Verified targets (descriptor 341 = NumPad 1 unpressed, descriptor 342 = pressed):
  - descriptor 341: offset 0x0077C446, format 2 (ARGB4444), 67x67, 8978 bytes
  - descriptor 342: offset 0x0077E758, format 2 (ARGB4444), 67x67, 8978 bytes
  - patch range 1: 0x0077C446 .. 0x0077E757 (inclusive)
  - patch range 2: 0x0077E758 .. 0x00780A69 (inclusive)

Outputs (all written to --output-dir, never to the source image):
  patched image, patch_report.json, diff_ranges.json,
  normal_encoded.bin, pressed_encoded.bin,
  normal_roundtrip.png, pressed_roundtrip.png
"""

import argparse
import hashlib
import io
import json
import os
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

# --- Factory image identity (read-only reference; never modified). ---
FACTORY_SIZE = 127599044
FACTORY_SHA256 = "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4"

# --- Verified Page 21 NumPad 1 asset targets ---
DESC_341_OFFSET = 0x0077C446
DESC_342_OFFSET = 0x0077E758
DESC_341_END = 0x0077E758          # exclusive
DESC_342_END = 0x00780A6A          # exclusive
RECORD_SIZE = 8978
ICON_WIDTH = 67
ICON_HEIGHT = 67
ARGB4444_FORMAT = 2

# Patched inclusive ranges (end - 1).
PATCH_RANGE_1 = (DESC_341_OFFSET, DESC_341_END - 1)
PATCH_RANGE_2 = (DESC_342_OFFSET, DESC_342_END - 1)


class PatchError(Exception):
    """Fatal validation / patch error."""


def die(message):
    raise PatchError(message)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_bounds(data, offset, length, what):
    if offset < 0 or length < 0:
        die(f"negative offset/length for {what}: offset={offset} length={length}")
    end = offset + length
    if end > len(data):
        die(
            f"{what} out of image bounds: offset={offset} (0x{offset:08X}) "
            f"length={length} end={end} (0x{end:08X}) image_size={len(data)}"
        )
    return data[offset:end]


def argb4444_encode(rgba_pixels, width, height):
    """Encode RGBA pixels (list of (r,g,b,a) 0-255) to ARGB4444 LE u16 bytes."""
    if width * height != len(rgba_pixels):
        die(f"pixel count mismatch: {width * height} expected, {len(rgba_pixels)} given")
    out = bytearray()
    for (r, g, b, a) in rgba_pixels:
        v = ((a >> 4) << 12) | ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)
        out += struct.pack("<H", v)
    return bytes(out)


def argb4444_decode(data, width, height):
    """Decode ARGB4444 LE u16 bytes to RGBA pixels (list of (r,g,b,a) 0-255)."""
    expected = width * height * 2
    if len(data) != expected:
        die(f"ARGB4444 payload length {len(data)} != {expected} for {width}x{height}")
    pixels = []
    for i in range(width * height):
        v = struct.unpack_from("<H", data, i * 2)[0]
        a_nib = (v >> 12) & 0xF
        r_nib = (v >> 8) & 0xF
        g_nib = (v >> 4) & 0xF
        b_nib = v & 0xF
        # Replicate nibble to full byte so re-encode is bit-exact. Order: (r,g,b,a).
        pixels.append(((r_nib << 4) | r_nib, (g_nib << 4) | g_nib,
                       (b_nib << 4) | b_nib, (a_nib << 4) | a_nib))
    return pixels


def load_rgba_png(path, width, height):
    """Load a PNG as RGBA and validate dimensions."""
    if not os.path.isfile(path):
        die(f"input PNG not found or not a regular file: {path}")
    try:
        im = Image.open(path).convert("RGBA")
    except Exception as exc:
        die(f"malformed PNG {path}: {exc}")
    if im.size != (width, height):
        die(
            f"PNG {path} has dimensions {im.size[0]}x{im.size[1]}, "
            f"expected {width}x{height}"
        )
    px = im.load()
    return [px[x, y] for y in range(height) for x in range(width)]


def pixels_to_png_bytes(pixels, width, height):
    """Encode RGBA pixels to PNG bytes (deterministic Pillow save)."""
    im = Image.new("RGBA", (width, height))
    im.putdata(pixels)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def validate_factory(image_path):
    """Read and validate the factory image. Returns its bytes."""
    if not os.path.isfile(image_path):
        die(f"source image not found or not a regular file: {image_path}")
    with open(image_path, "rb") as f:
        data = f.read()
    if len(data) != FACTORY_SIZE:
        die(
            f"source image size {len(data)} != expected factory size {FACTORY_SIZE}"
        )
    sha = sha256_bytes(data)
    if sha != FACTORY_SHA256:
        die(
            f"source image SHA-256 {sha} != expected factory SHA-256 "
            f"{FACTORY_SHA256}"
        )
    return data


def check_no_overlap(ranges):
    """Ensure patch ranges do not overlap and are ordered."""
    sorted_ranges = sorted(ranges, key=lambda r: r[0])
    for i in range(len(sorted_ranges) - 1):
        if sorted_ranges[i][1] >= sorted_ranges[i + 1][0]:
            die(f"overlapping patch ranges: {sorted_ranges[i]} and {sorted_ranges[i+1]}")


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def apply_patch(source_before, normal_encoded, pressed_encoded):
    """Apply the two verified-range patches to a copy of source_before.

    Validates encoded sizes, range bounds, non-overlap, and that no bytes
    outside the two verified ranges change. Returns patched bytes.
    """
    if len(normal_encoded) != RECORD_SIZE:
        die(f"normal encoded output {len(normal_encoded)} bytes != {RECORD_SIZE}")
    if len(pressed_encoded) != RECORD_SIZE:
        die(f"pressed encoded output {len(pressed_encoded)} bytes != {RECORD_SIZE}")

    # Range bounds: destination ranges must fit within the source image.
    for s, e, role in ((DESC_341_OFFSET, DESC_341_END, "descriptor 341"),
                       (DESC_342_OFFSET, DESC_342_END, "descriptor 342")):
        if e > len(source_before):
            die(f"{role} destination range [0x{s:08X}, 0x{e:08X}) exceeds image size {len(source_before)}")

    check_no_overlap([PATCH_RANGE_1, PATCH_RANGE_2])
    patched = bytearray(source_before)

    start1, end1 = PATCH_RANGE_1
    start2, end2 = PATCH_RANGE_2
    patched[start1:end1 + 1] = normal_encoded
    patched[start2:end2 + 1] = pressed_encoded

    # Verify writes landed exactly in range.
    if bytes(patched[start1:end1 + 1]) != normal_encoded:
        die("normal write did not land exactly in range 1")
    if bytes(patched[start2:end2 + 1]) != pressed_encoded:
        die("pressed write did not land exactly in range 2")

    # Preserve all other bytes exactly.
    unchanged_mask = bytearray(b"\x01") * len(source_before)
    for s, e in (PATCH_RANGE_1, PATCH_RANGE_2):
        for i in range(s, e + 1):
            unchanged_mask[i] = 0
    for i, keep in enumerate(unchanged_mask):
        if keep and patched[i] != source_before[i]:
            die(f"unexpected byte change outside patch ranges at offset {i} (0x{i:08X})")

    return bytes(patched)


def run(args):
    # --- Resolve paths and reject input/output collision ---
    allow_unknown = bool(getattr(args, "allow_unknown_image", False))
    image_path = os.path.abspath(args.image)
    normal_path = os.path.abspath(args.normal)
    pressed_path = os.path.abspath(args.pressed)
    output_dir = os.path.abspath(args.output_dir)

    out_patched = os.path.join(output_dir, "patched_UartTFT-II_Flash.bin")
    for p in (normal_path, pressed_path, image_path):
        if os.path.abspath(p) == os.path.abspath(out_patched):
            die(f"input and output resolve to the same file: {p}")

    if os.path.abspath(normal_path) == os.path.abspath(pressed_path):
        die("--normal and --pressed resolve to the same file")

    # --- Validate factory image ---
    if not os.path.isfile(image_path):
        die(f"source image not found or not a regular file: {image_path}")
    with open(image_path, "rb") as f:
        source_before = f.read()
    if not allow_unknown:
        if len(source_before) != FACTORY_SIZE:
            die(
                f"source image size {len(source_before)} != expected factory size {FACTORY_SIZE}"
            )
        factory_sha_before = sha256_bytes(source_before)
        if factory_sha_before != FACTORY_SHA256:
            die(
                f"source image SHA-256 {factory_sha_before} != expected factory SHA-256 "
                f"{FACTORY_SHA256}"
            )
    else:
        factory_sha_before = sha256_bytes(source_before)
    factory_mtime_before = os.path.getmtime(image_path)

    # --- Round-trip check on existing factory descriptors 341 and 342 ---
    rec_341 = read_bounds(source_before, DESC_341_OFFSET, RECORD_SIZE,
                          "descriptor 341 encoded record")
    rec_342 = read_bounds(source_before, DESC_342_OFFSET, RECORD_SIZE,
                          "descriptor 342 encoded record")

    pixels_341 = argb4444_decode(rec_341, ICON_WIDTH, ICON_HEIGHT)
    re_encoded_341 = argb4444_encode(pixels_341, ICON_WIDTH, ICON_HEIGHT)
    if re_encoded_341 != rec_341:
        die("round-trip mismatch: re-encoded descriptor 341 does not match original record")

    pixels_342 = argb4444_decode(rec_342, ICON_WIDTH, ICON_HEIGHT)
    re_encoded_342 = argb4444_encode(pixels_342, ICON_WIDTH, ICON_HEIGHT)
    if re_encoded_342 != rec_342:
        die("round-trip mismatch: re-encoded descriptor 342 does not match original record")

    roundtrip_341_ok = True
    roundtrip_342_ok = True

    # --- Encode input PNGs ---
    normal_pixels = load_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT)
    pressed_pixels = load_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT)

    normal_encoded = argb4444_encode(normal_pixels, ICON_WIDTH, ICON_HEIGHT)
    pressed_encoded = argb4444_encode(pressed_pixels, ICON_WIDTH, ICON_HEIGHT)

    # --- Apply patch (validates sizes, bounds, overlap, unchanged bytes) ---
    patched_bytes = apply_patch(source_before, normal_encoded, pressed_encoded)
    patched_sha = sha256_bytes(patched_bytes)

    start1, end1 = PATCH_RANGE_1
    start2, end2 = PATCH_RANGE_2

    # --- Source integrity re-check ---
    with open(image_path, "rb") as f:
        source_after = f.read()
    if source_before != source_after:
        die("SOURCE IMAGE CHANGED during execution")
    if os.path.getmtime(image_path) != factory_mtime_before:
        die("SOURCE IMAGE modification time changed during execution")

    # --- Write outputs ---
    os.makedirs(output_dir, exist_ok=True)

    with open(out_patched, "wb") as f:
        f.write(patched_bytes)
    with open(os.path.join(output_dir, "normal_encoded.bin"), "wb") as f:
        f.write(normal_encoded)
    with open(os.path.join(output_dir, "pressed_encoded.bin"), "wb") as f:
        f.write(pressed_encoded)
    # Round-trip PNGs of the encoded inputs (encode -> decode -> PNG).
    normal_roundtrip_pixels = argb4444_decode(normal_encoded, ICON_WIDTH, ICON_HEIGHT)
    pressed_roundtrip_pixels = argb4444_decode(pressed_encoded, ICON_WIDTH, ICON_HEIGHT)
    normal_roundtrip_png = pixels_to_png_bytes(normal_roundtrip_pixels, ICON_WIDTH, ICON_HEIGHT)
    pressed_roundtrip_png = pixels_to_png_bytes(pressed_roundtrip_pixels, ICON_WIDTH, ICON_HEIGHT)
    with open(os.path.join(output_dir, "normal_roundtrip.png"), "wb") as f:
        f.write(normal_roundtrip_png)
    with open(os.path.join(output_dir, "pressed_roundtrip.png"), "wb") as f:
        f.write(pressed_roundtrip_png)

    diff_ranges = [
        {
            "range_index": 1,
            "descriptor": 341,
            "role": "unpressed",
            "start_offset": start1,
            "start_offset_hex": f"0x{start1:08X}",
            "end_offset_exclusive": DESC_341_END,
            "end_offset_exclusive_hex": f"0x{DESC_341_END:08X}",
            "length": RECORD_SIZE,
            "sha256_before": sha256_bytes(rec_341),
            "sha256_after": sha256_bytes(normal_encoded),
        },
        {
            "range_index": 2,
            "descriptor": 342,
            "role": "pressed",
            "start_offset": start2,
            "start_offset_hex": f"0x{start2:08X}",
            "end_offset_exclusive": DESC_342_END,
            "end_offset_exclusive_hex": f"0x{DESC_342_END:08X}",
            "length": RECORD_SIZE,
            "sha256_before": sha256_bytes(rec_342),
            "sha256_after": sha256_bytes(pressed_encoded),
        },
    ]
    write_json(os.path.join(output_dir, "diff_ranges.json"), diff_ranges)

    patch_report = {
        "source_image": image_path,
        "factory_size": FACTORY_SIZE,
        "factory_sha256": FACTORY_SHA256,
        "source_size_before": len(source_before),
        "source_sha256_before": factory_sha_before,
        "source_mtime_utc_before": datetime.fromtimestamp(factory_mtime_before, tz=timezone.utc).isoformat(),
        "source_unchanged": source_before == source_after,
        "size_matches_factory": len(source_before) == FACTORY_SIZE,
        "sha256_matches_factory": factory_sha_before == FACTORY_SHA256,
        "patched_image": out_patched,
        "patched_size": len(patched_bytes),
        "patched_sha256": patched_sha,
        "size_preserved": len(patched_bytes) == FACTORY_SIZE,
        "roundtrip_descriptor_341": roundtrip_341_ok,
        "roundtrip_descriptor_342": roundtrip_342_ok,
        "normal_input": normal_path,
        "pressed_input": pressed_path,
        "normal_encoded_sha256": sha256_bytes(normal_encoded),
        "pressed_encoded_sha256": sha256_bytes(pressed_encoded),
        "patch_ranges": diff_ranges,
        "outputs": {
            "patched_image": out_patched,
            "patch_report": os.path.join(output_dir, "patch_report.json"),
            "diff_ranges": os.path.join(output_dir, "diff_ranges.json"),
            "normal_encoded": os.path.join(output_dir, "normal_encoded.bin"),
            "pressed_encoded": os.path.join(output_dir, "pressed_encoded.bin"),
            "normal_roundtrip_png": os.path.join(output_dir, "normal_roundtrip.png"),
            "pressed_roundtrip_png": os.path.join(output_dir, "pressed_roundtrip.png"),
        },
    }
    write_json(os.path.join(output_dir, "patch_report.json"), patch_report)

    # --- Console summary ---
    print(f"Offline NumPad icon patch complete. Output directory: {output_dir}")
    print(f"Source unchanged: {source_before == source_after}")
    print(f"Factory SHA-256 before: {factory_sha_before}")
    print(f"Patched image SHA-256: {patched_sha}")
    print(f"Patched size: {len(patched_bytes)} (factory {FACTORY_SIZE})")
    print(f"Round-trip descriptor 341: {roundtrip_341_ok}")
    print(f"Round-trip descriptor 342: {roundtrip_342_ok}")
    print(f"Changed ranges: {[r['start_offset_hex'] + ' .. ' + r['end_offset_exclusive_hex'] for r in diff_ranges]}")
    return 0


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Offline-only ARGB4444 encoder and working-copy patcher for AULA L99 Page 21 NumPad 1 icons."
    )
    parser.add_argument("--image", required=True, help="Path to factory UartTFT-II_Flash.bin")
    parser.add_argument("--normal", required=True, help="Path to 67x67 RGBA normal-state PNG")
    parser.add_argument("--pressed", required=True, help="Path to 67x67 RGBA pressed-state PNG")
    parser.add_argument("--output-dir", required=True, help="Output directory for patched image and reports")
    parser.add_argument("--allow-unknown-image", action="store_true",
                        help="Research-only override: skip exact factory size/SHA-256 validation")
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if not args.allow_unknown_image:
            # Strict factory validation happens inside run(); this flag just skips it for research.
            pass
        return run(args)
    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
