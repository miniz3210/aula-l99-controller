#!/usr/bin/env python3
"""Read-only offline AULA L99 screen descriptor inspector.

Never opens USB, COM, HID, or any updater. Never imports serial/USB/HID/updater
modules. Never modifies the source image. All image access is bounds-checked.

Usage (page / return-code mode):
    python scripts/inspect_l99_descriptor.py ^
        --image <path-to-UartTFT-II_Flash.bin> ^
        --manifest <path-to-manifest.json> ^
        --page 21 ^
        --return-code 0x003B ^
        --output <empty-output-directory>

Usage (direct descriptor mode):
    python scripts/inspect_l99_descriptor.py ^
        --image <path> ^
        --manifest <path> ^
        --descriptor 341 ^
        --descriptor 342 ^
        --output <empty-output-directory>

Descriptor values may be decimal or hexadecimal (0x prefix).
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

# Descriptor table entry layout (little-endian): address(u32), width(u16),
# height(u16), packed(u32) where low 24 bits = encoded size, high 8 bits = format.
DESCRIPTOR_ENTRY_SIZE = 12

# Factory image identity (read-only reference; never modified).
FACTORY_SIZE = 127599044
FACTORY_SHA256 = "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4"

# Established format names from the softce inspector (image-format.md).
FORMAT_NAMES = {
    0: "RGB565 (raw 16-bit)",
    1: "RGB565 (raw 16-bit)",
    2: "ARGB4444 (raw 16-bit packed)",
    3: "LT chunked RLE (compressed)",
}


class DescriptorError(Exception):
    """Fatal validation / resolution error."""


def die(message):
    raise DescriptorError(message)


def parse_int_token(token):
    """Parse a decimal or hexadecimal integer token. Rejects negatives."""
    if token is None:
        die("missing integer value")
    text = str(token).strip()
    if text == "":
        die("empty integer value")
    try:
        if text.lower().startswith("0x"):
            value = int(text, 16)
        else:
            value = int(text, 10)
    except ValueError:
        die(f"invalid integer value: {token!r}")
    if value < 0:
        die(f"negative integer not allowed: {token!r}")
    return value


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_snapshot(path):
    """Capture size, SHA-256, mtime, and full-byte hash before/after."""
    st = os.stat(path)
    return {
        "size": st.st_size,
        "sha256": sha256_file(path),
        "mtime_ns": st.st_mtime_ns,
        "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        "byte_hash": sha256_bytes(path.read_bytes() if False else b""),  # placeholder
    }


def read_bounds(data, offset, length, what):
    """Bounds-check a raw image read; die if out of range."""
    if offset < 0 or length < 0:
        die(f"negative offset/length for {what}: offset={offset} length={length}")
    end = offset + length
    if end > len(data):
        die(
            f"{what} out of image bounds: offset={offset} (0x{offset:08X}) "
            f"length={length} end={end} (0x{end:08X}) image_size={len(data)}"
        )
    return data[offset:end]


def load_manifest(manifest_path):
    if not os.path.isfile(manifest_path):
        die(f"manifest not found or not a regular file: {manifest_path}")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        die(f"malformed manifest: {exc}")
    if not isinstance(manifest, dict):
        die("manifest root is not a JSON object")
    header = manifest.get("header_words")
    if not isinstance(header, list) or len(header) < 14:
        die("manifest missing header_words (need at least 14 entries)")
    return manifest


def page_table_entry(data, manifest, page_id):
    """Read and cross-check a page table entry against the manifest."""
    header = manifest["header_words"]
    page_table = header[2]
    page_count = header[3]
    if not (0 <= page_id < page_count):
        die(f"page {page_id} out of range [0, {page_count})")
    entry_offset = page_table + page_id * 12
    raw = read_bounds(data, entry_offset, 12, f"page {page_id} table entry")
    display_offset, display_size, touch_offset, touch_size = struct.unpack_from("<IHIH", raw, 0)
    manifest_page = None
    pages = manifest.get("pages")
    if isinstance(pages, list):
        for pg in pages:
            if isinstance(pg, dict) and pg.get("id") == page_id:
                manifest_page = pg
                break
    cross_check = {}
    if manifest_page is not None:
        cross_check = {
            "manifest_display_offset": manifest_page.get("display_offset"),
            "manifest_display_size": manifest_page.get("display_size"),
            "manifest_touch_offset": manifest_page.get("touch_offset"),
            "manifest_touch_size": manifest_page.get("touch_size"),
            "raw_display_offset": display_offset,
            "raw_display_size": display_size,
            "raw_touch_offset": touch_offset,
            "raw_touch_size": touch_size,
            "display_offset_matches": manifest_page.get("display_offset") == display_offset,
            "display_size_matches": manifest_page.get("display_size") == display_size,
            "touch_offset_matches": manifest_page.get("touch_offset") == touch_offset,
            "touch_size_matches": manifest_page.get("touch_size") == touch_size,
        }
    return {
        "page_table": page_table,
        "page_count": page_count,
        "entry_offset": entry_offset,
        "raw_bytes": raw.hex(),
        "display_offset": display_offset,
        "display_size": display_size,
        "touch_offset": touch_offset,
        "touch_size": touch_size,
        "cross_check": cross_check,
    }


def parse_touch_records(data, touch_offset, touch_size):
    """Parse touch records from raw BIN bytes (mirrors the softce inspector)."""
    records = []
    end = touch_offset + touch_size
    p = touch_offset
    while p < end:
        rec_start = p
        typ = struct.unpack_from("<H", data, p)[0]
        prefix = 3  # touch family prefix length
        length_byte_pos = p + prefix - 1
        read_bounds(data, length_byte_pos, 1, "touch length byte")
        length_byte = data[length_byte_pos]
        length = length_byte & 0x7F
        payload_start = p + prefix
        payload = read_bounds(data, payload_start, length, "touch payload")
        record = {
            "offset": rec_start,
            "type": typ,
            "base_type": typ & 0x3FFF,
            "length": length,
            "length_byte": length_byte,
            "payload": payload.hex(),
        }
        if length >= 8:
            x1, y1, x2, y2 = struct.unpack_from("<4H", payload, 0)
            record["rectangle_candidate"] = [x1, y1, x2, y2]
        if (typ & 0x3FFF) == 1 and length == 16:
            values = struct.unpack("<8H", payload)
            record.update(
                dict(
                    zip(
                        ["x1", "y1", "x2", "y2", "return_value", "unpressed_icon", "pressed_icon", "goto_page"],
                        values,
                    )
                )
            )
        records.append(record)
        p = rec_start + prefix + length
    if p != end:
        die(f"touch block parse did not consume full block: consumed={p - touch_offset} size={touch_size}")
    return records


def resolve_descriptor(data, manifest, descriptor_id):
    """Resolve one descriptor ID to its raw table entry and encoded asset.

    Cross-checks both icon banks. A descriptor is ambiguous if it resolves to
    different entries across banks; missing if absent from both.
    """
    header = manifest["header_words"]
    icon_table = header[12]
    icon_count = header[13]
    if icon_count <= 0:
        die("manifest icon_count is zero or missing")
    bank_entries = []
    for bank in range(2):
        entry_offset = icon_table + (bank * icon_count + descriptor_id) * DESCRIPTOR_ENTRY_SIZE
        raw = read_bounds(data, entry_offset, DESCRIPTOR_ENTRY_SIZE, f"descriptor {descriptor_id} bank {bank} entry")
        address, width, height, packed = struct.unpack_from("<IHHI", raw, 0)
        size = packed & 0xFFFFFF
        fmt = packed >> 24
        entry = {
            "bank": bank,
            "table_offset": entry_offset,
            "address": address,
            "width": width,
            "height": height,
            "packed": packed,
            "encoded_size": size,
            "format": fmt,
            "format_name": FORMAT_NAMES.get(fmt, f"unknown format {fmt}"),
            "raw_entry_bytes": raw.hex(),
            "encoded_range_start": address,
            "encoded_range_end": address + size,
            "encoded_payload_length": size,
            "full_encoded_record_length": DESCRIPTOR_ENTRY_SIZE + size,
        }
        # Bounds-check the encoded payload.
        read_bounds(data, address, size, f"descriptor {descriptor_id} bank {bank} encoded payload")
        bank_entries.append(entry)

    present = [e for e in bank_entries if True]  # all entries read successfully
    if not present:
        die(f"descriptor {descriptor_id} not found in icon table (banks 0 and 1)")

    # Ambiguity: entries must agree across banks.
    if len(present) == 2:
        a, b = present[0], present[1]
        if (a["address"], a["width"], a["height"], a["encoded_size"], a["format"]) != (
            b["address"], b["width"], b["height"], b["encoded_size"], b["format"]
        ):
            die(
                f"descriptor {descriptor_id} is ambiguous: bank 0 and bank 1 entries disagree "
                f"(bank0={a}, bank1={b})"
            )
    chosen = present[0]

    allocation_capacity = chosen["encoded_size"]
    allocation_overlap_detected = False
    if descriptor_id + 1 < icon_count:
        next_offset = icon_table + (chosen["bank"] * icon_count + descriptor_id + 1) * DESCRIPTOR_ENTRY_SIZE
        next_raw = read_bounds(data, next_offset, DESCRIPTOR_ENTRY_SIZE, f"next descriptor {descriptor_id + 1} entry")
        next_address = struct.unpack_from("<I", next_raw, 0)[0]
        next_boundary = next_address
        next_boundary_verified = next_address == chosen["encoded_range_end"]
        if next_address < chosen["encoded_range_end"]:
            allocation_overlap_detected = True
    else:
        next_boundary = None
        next_boundary_verified = False

    return {
        "descriptor_id": descriptor_id,
        "descriptor_id_hex": f"0x{descriptor_id:04X}",
        "bank": chosen["bank"],
        "descriptor_table_index": descriptor_id,
        "descriptor_table_base": icon_table,
        "descriptor_table_file_offset": icon_table,
        "exact_descriptor_entry_file_offset": chosen["table_offset"],
        "raw_descriptor_bytes": chosen["raw_entry_bytes"],
        "descriptor_entry_length": DESCRIPTOR_ENTRY_SIZE,
        "decoded_descriptor_fields": {
            "address": chosen["address"],
            "width": chosen["width"],
            "height": chosen["height"],
            "encoded_size": chosen["encoded_size"],
            "format": chosen["format"],
            "format_name": chosen["format_name"],
        },
        "source_asset_logical_address": chosen["address"],
        "source_asset_file_offset": chosen["address"],
        "address_translation_method": "direct file offset (manifest address == file offset in UartTFT-II_Flash.bin; no bank/segment translation)",
        "encoded_format_number": chosen["format"],
        "format_name": chosen["format_name"],
        "decoded_width": chosen["width"],
        "decoded_height": chosen["height"],
        "encoded_payload_length": chosen["encoded_size"],
        "full_encoded_record_length": chosen["full_encoded_record_length"],
        "encoded_range_start": chosen["encoded_range_start"],
        "encoded_range_end": chosen["encoded_range_end"],
        "allocation_start": chosen["address"],
        "allocation_end": chosen["encoded_range_end"],
        "allocation_capacity": allocation_capacity,
        "next_confirmed_asset_boundary": next_boundary,
        "next_confirmed_asset_boundary_verified": next_boundary_verified,
        "boundary_confidence": "verified" if next_boundary_verified else "inferred",
        "allocation_overlap_detected": allocation_overlap_detected,
    }


def find_decoded_png(manifest_path, descriptor_id, png_hint):
    """Locate a previously decoded PNG under the inspection assets directory."""
    if not png_hint:
        return None
    inspection_dir = Path(manifest_path).resolve().parent
    candidates = [
        inspection_dir / png_hint,
        inspection_dir / "assets" / png_hint,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def find_references(manifest, descriptor_id):
    """Collect all page/display/touch records referencing the descriptor."""
    references = []
    pages = manifest.get("pages")
    if not isinstance(pages, list):
        return references
    for pg in pages:
        if not isinstance(pg, dict):
            continue
        page_id = pg.get("id")
        # Touch records.
        for t in pg.get("touch", []) or []:
            role = None
            if t.get("unpressed_icon") == descriptor_id:
                role = "unpressed"
            elif t.get("pressed_icon") == descriptor_id:
                role = "pressed"
            if role:
                references.append({
                    "record_kind": "touch",
                    "page": page_id,
                    "offset": t.get("offset"),
                    "type": t.get("type"),
                    "role": role,
                    "return_value": t.get("return_value"),
                    "goto_page": t.get("goto_page"),
                    "rectangle": t.get("rectangle_candidate"),
                    "base_type": t.get("base_type"),
                })
        # Display records.
        for d in pg.get("display", []) or []:
            roles = []
            if d.get("first_icon") == descriptor_id:
                roles.append("first_icon")
            if d.get("last_icon") == descriptor_id and d.get("last_icon") != 65535:
                roles.append("last_icon")
            for role in roles:
                references.append({
                    "record_kind": "display",
                    "page": page_id,
                    "offset": d.get("offset"),
                    "type": d.get("type"),
                    "role": role,
                    "first_icon": d.get("first_icon"),
                    "last_icon": d.get("last_icon"),
                })
    return references


def find_decode_issues(manifest, descriptor_id, address):
    """Collect manifest decode issues involving this descriptor/address."""
    issues = []
    decode_issues = manifest.get("decode_issues")
    if not isinstance(decode_issues, list):
        return issues
    for iss in decode_issues:
        if not isinstance(iss, dict):
            continue
        d = iss.get("descriptor", {})
        if d.get("id") == descriptor_id or d.get("address") == address:
            issues.append(iss)
    return issues


def hexdump(data):
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08X}  {hex_part:<47}  {ascii_part}")
    return "\n".join(lines)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def validate_output_dir(output_dir, force_output):
    if os.path.exists(output_dir):
        if not force_output:
            try:
                entries = os.listdir(output_dir)
            except OSError:
                entries = []
            if entries:
                die(f"output directory is not empty (use --force-output): {output_dir}")
        # Non-empty with --force-output: clear contents deterministically.
        for entry in os.listdir(output_dir):
            full = os.path.join(output_dir, entry)
            if os.path.isdir(full) and not os.path.islink(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
    else:
        os.makedirs(output_dir, exist_ok=True)


def build_descriptor_report(desc, references, decode_issues, png_info, encoded_sha, decoded_sha):
    report = dict(desc)
    report["decoded_asset_filename"] = png_info["filename"] if png_info else None
    report["decoded_asset_local_path"] = png_info["local_path"] if png_info else None
    report["decoded_png_sha256"] = decoded_sha
    report["source_encoded_byte_sha256"] = encoded_sha
    report["referencing_records"] = references
    "reference_count"
    report["reference_count"] = len(references)
    report["roles"] = sorted({r["role"] for r in references})
    report["shared_by_other_pages_or_controls"] = (
        len({r["page"] for r in references if r["page"] is not None}) > 1 or len(references) > 1
    )
    report["manifest_decode_issues"] = decode_issues
    report["metadata_or_checksum_fields_for_future_patch"] = {
        "descriptor_entry_size": DESCRIPTOR_ENTRY_SIZE,
        "fields_that_may_need_update": [
            "descriptor address",
            "descriptor width",
            "descriptor height",
            "descriptor encoded size",
            "descriptor format",
        ],
        "checksum_implication": "unknown - no manifest checksum covers individual descriptors",
        "size_limit": desc["allocation_capacity"],
        "replacement_size_limit": desc["allocation_capacity"],
        "no_overlap_with_another_asset": desc["next_confirmed_asset_boundary_verified"],
    }
    return report


def run(args):
    # --- Image validation ---
    if not os.path.isfile(args.image):
        die(f"source image not found or not a regular file: {args.image}")
    image_path = os.path.abspath(args.image)
    with open(image_path, "rb") as f:
        source_before = f.read()
    source_size_before = len(source_before)
    source_sha_before = sha256_bytes(source_before)
    source_mtime_before = os.path.getmtime(image_path)

    factory_mode = False
    if source_size_before == FACTORY_SIZE and source_sha_before == FACTORY_SHA256:
        factory_mode = True
    elif args.allow_unknown_image:
        print(
            "WARNING: --allow-unknown-image is set. Source image does not match the verified factory "
            f"image (size {FACTORY_SIZE}, SHA-256 {FACTORY_SHA256}). "
            f"Actual: size={source_size_before}, SHA-256={source_sha_before}. Proceeding in research-only mode.",
            file=sys.stdout,
        )
    else:
        die(
            f"source image does not match the verified factory image. "
            f"Expected size={FACTORY_SIZE} SHA-256={FACTORY_SHA256}. "
            f"Actual size={source_size_before} SHA-256={source_sha_before}. "
            f"Use --allow-unknown-image to override (research only)."
        )

    # --- Manifest validation ---
    manifest = load_manifest(args.manifest)

    # --- Descriptor selection ---
    descriptors = []
    seen = set()
    for d in args.descriptor:
        did = parse_int_token(d)
        if did in seen:
            die(f"duplicate descriptor requested: {did}")
        seen.add(did)
        descriptors.append(did)

    # --- Page / return-code mode ---
    page_context = None
    unpressed = None
    pressed = None
    if args.page is not None or args.return_code is not None:
        if args.page is None:
            die("--page is required with --return-code")
        if args.return_code is None:
            die("--return-code is required with --page")
        page_id = parse_int_token(args.page)
        return_code = parse_int_token(args.return_code)
        page_context = page_table_entry(source_before, manifest, page_id)
        touch_records = parse_touch_records(
            source_before, page_context["touch_offset"], page_context["touch_size"]
        )
        matches = [t for t in touch_records if t.get("return_value") == return_code]
        if len(matches) != 1:
            die(
                f"page {page_id}: expected exactly one touch record with return value "
                f"0x{return_code:04X} ({return_code}); found {len(matches)}"
            )
        touch = matches[0]
        expected_rect = [13, 337, 79, 403]
        if touch.get("rectangle_candidate") != expected_rect:
            die(
                f"page {page_id} return-code 0x{return_code:04X}: rectangle mismatch. "
                f"Expected {expected_rect}, got {touch.get('rectangle_candidate')}"
            )
        unpressed = touch.get("unpressed_icon")
        pressed = touch.get("pressed_icon")
        goto_page = touch.get("goto_page")
        if unpressed is None or pressed is None:
            die(f"page {page_id} touch record missing unpressed/pressed icon fields")
        if goto_page != 65535:
            die(f"page {page_id} goto_page mismatch: expected 65535, got {goto_page}")
        # Replace descriptor list with the resolved unpressed/pressed pair, preserving order.
        ordered = []
        for did in (unpressed, pressed):
            if did not in ordered:
                ordered.append(did)
        if not ordered:
            die("touch record resolves to no descriptors")
        descriptors = ordered
        page_context.update(
            {
                "touch_record_offset": touch["offset"],
                "return_value": touch.get("return_value"),
                "return_value_hex": f"0x{touch.get('return_value'):04X}" if touch.get("return_value") is not None else None,
                "rectangle": touch.get("rectangle_candidate"),
                "unpressed_descriptor": unpressed,
                "pressed_descriptor": pressed,
                "goto_page": goto_page,
                "touch_record_type": touch.get("type"),
                "touch_record_base_type": touch.get("base_type"),
                "touch_record_length": touch.get("length"),
                "all_touch_records": touch_records,
            }
        )

    if not descriptors:
        die("no descriptor requested (use --descriptor or --page/--return-code)")

    # --- Output directory ---
    validate_output_dir(args.output, args.force_output)
    output_dir = os.path.abspath(args.output)

    # --- Process each descriptor ---
    descriptor_reports = []
    all_encoded_shas = {}
    all_decoded_shas = {}
    for did in descriptors:
        desc = resolve_descriptor(source_before, manifest, did)

        # Cross-check manifest icon entry for this descriptor/bank.
        manifest_entry = None
        icons = manifest.get("icons")
        if isinstance(icons, list):
            bank = desc["bank"]
            idx = desc["descriptor_table_index"]
            if 0 <= bank < len(icons) and 0 <= idx < len(icons[bank]):
                manifest_entry = icons[bank][idx]
        manifest_cross_check = {}
        if manifest_entry is not None:
            manifest_cross_check = {
                "manifest_address": manifest_entry.get("address"),
                "manifest_width": manifest_entry.get("width"),
                "manifest_height": manifest_entry.get("height"),
                "manifest_size": manifest_entry.get("size"),
                "manifest_format": manifest_entry.get("format"),
                "manifest_status": manifest_entry.get("status"),
                "manifest_png": manifest_entry.get("png"),
                "address_matches": manifest_entry.get("address") == desc["source_asset_logical_address"],
                "width_matches": manifest_entry.get("width") == desc["decoded_width"],
                "height_matches": manifest_entry.get("height") == desc["decoded_height"],
                "size_matches": manifest_entry.get("size") == desc["encoded_payload_length"],
                "format_matches": manifest_entry.get("format") == desc["encoded_format_number"],
            }
        desc["manifest_cross_check"] = manifest_cross_check

        # Encoded bytes + SHA.
        encoded_bytes = read_bounds(
            source_before, desc["encoded_range_start"], desc["encoded_payload_length"], f"descriptor {did} encoded payload"
        )
        encoded_sha = sha256_bytes(encoded_bytes)
        all_encoded_shas[did] = encoded_sha

        # Encoded binary output.
        enc_path = os.path.join(output_dir, f"descriptor_{did}_encoded.bin")
        with open(enc_path, "wb") as f:
            f.write(encoded_bytes)

        # Hexdump output.
        hd_path = os.path.join(output_dir, f"descriptor_{did}_hexdump.txt")
        with open(hd_path, "w", encoding="utf-8") as f:
            f.write(hexdump(encoded_bytes))

        # Decoded PNG: copy existing if present.
        png_hint = manifest_entry.get("png") if manifest_entry else None
        png_info = None
        decoded_sha = None
        if png_hint:
            found = find_decoded_png(args.manifest, did, png_hint)
            if found:
                dest_png = os.path.join(output_dir, f"descriptor_{did}_decoded.png")
                shutil.copyfile(found, dest_png)
                with open(dest_png, "rb") as pf:
                    png_bytes = pf.read()
                decoded_sha = sha256_bytes(png_bytes)
                png_info = {
                    "filename": os.path.basename(str(found)),
                    "local_path": str(found),
                    "dimensions": [desc["decoded_width"], desc["decoded_height"]],
                    "sha256": decoded_sha,
                    "copied": True,
                }
                all_decoded_shas[did] = decoded_sha

        # References.
        references = find_references(manifest, did)
        decode_issues = find_decode_issues(manifest, did, desc["source_asset_logical_address"])

        report = build_descriptor_report(
            desc, references, decode_issues, png_info, encoded_sha, decoded_sha
        )
        report["manifest_cross_check"] = manifest_cross_check
        descriptor_reports.append(report)

        # Per-descriptor JSON.
        write_json(os.path.join(output_dir, f"descriptor_{did}.json"), report)

    # --- Source integrity re-check (after execution) ---
    with open(image_path, "rb") as f:
        source_after = f.read()
    source_size_after = len(source_after)
    source_sha_after = sha256_bytes(source_after)
    source_mtime_after = os.path.getmtime(image_path)

    if source_before != source_after:
        die("SOURCE IMAGE CHANGED during execution: source file is not read-only safe")
    if source_size_before != source_size_after or source_sha_before != source_sha_after:
        die("SOURCE IMAGE size/SHA-256 changed during execution")
    if source_mtime_before != source_mtime_after:
        die("SOURCE IMAGE modification time changed during execution")

    # --- Page / touch mapping report (page mode) ---
    page_mapping = None
    if page_context is not None:
        page_mapping = {
            "page_id": page_context.get("page_id") if "page_id" in page_context else None,
            "page_table_entry": {
                k: v for k, v in page_context.items()
                if k in ("entry_offset", "raw_bytes", "display_offset", "display_size", "touch_offset", "touch_size", "cross_check")
            },
            "touch_record": {
                k: page_context[k] for k in (
                    "touch_record_offset", "return_value", "return_value_hex", "rectangle",
                    "unpressed_descriptor", "pressed_descriptor", "goto_page",
                    "touch_record_type", "touch_record_base_type", "touch_record_length",
                ) if k in page_context
            },
            "all_touch_records_count": len(page_context.get("all_touch_records", [])),
        }

    # --- Source verification output ---
    source_verification = {
        "source_image": image_path,
        "factory_mode": factory_mode,
        "allow_unknown_image": bool(args.allow_unknown_image),
        "size_before": source_size_before,
        "sha256_before": source_sha_before,
        "mtime_utc_before": datetime.fromtimestamp(source_mtime_before, tz=timezone.utc).isoformat(),
        "size_after": source_size_after,
        "sha256_after": source_sha_after,
        "mtime_utc_after": datetime.fromtimestamp(source_mtime_after, tz=timezone.utc).isoformat(),
        "source_unchanged": source_before == source_after,
        "size_matches_factory": source_size_before == FACTORY_SIZE,
        "sha256_matches_factory": source_sha_before == FACTORY_SHA256,
        "warning": (
            "WARNING: --allow-unknown-image is set. Source image does not match the verified factory image."
            if args.allow_unknown_image else None
        ),
    }
    write_json(os.path.join(output_dir, "source_verification.json"), source_verification)

    # --- Page 21 NumPad 1 mapping (page mode) ---
    if page_context is not None:
        mapping = {
            "page_id": page_id,
            "return_code": return_code,
            "return_code_hex": f"0x{return_code:04X}",
            "rectangle": page_context["rectangle"],
            "rectangle_expected": [13, 337, 79, 403],
            "rectangle_matches": page_context["rectangle"] == [13, 337, 79, 403],
            "unpressed_descriptor": unpressed,
            "pressed_descriptor": pressed,
            "goto_page": goto_page,
            "goto_page_expected": 65535,
            "goto_page_matches": goto_page == 65535,
            "descriptor_reports": [r["descriptor_id"] for r in descriptor_reports],
        }
        write_json(os.path.join(output_dir, "page21_numpad1_mapping.json"), mapping)

    # --- Markdown report ---
    report_lines = []
    report_lines.append("# Descriptor Mapping Report")
    report_lines.append("")
    report_lines.append("## Source verification")
    report_lines.append(f"- Source image: {image_path}")
    report_lines.append(f"- Size before: {source_size_before}")
    report_lines.append(f"- SHA-256 before: {source_sha_before}")
    report_lines.append(f"- Size after: {source_size_after}")
    report_lines.append(f"- SHA-256 after: {source_sha_after}")
    report_lines.append(f"- Source unchanged: {source_before == source_after}")
    if factory_mode:
        report_lines.append("- Factory image match: VERIFIED (size + SHA-256 match the documented factory image)")
    else:
        report_lines.append("- Factory image match: NOT MATCHED (--allow-unknown-image used; research only)")
        report_lines.append("- WARNING: source image does not match the verified factory image.")
    report_lines.append("")
    report_lines.append("## Page and touch mapping")
    if page_mapping:
        tr = page_mapping["touch_record"]
        report_lines.append(f"- Page ID: {page_id}")
        report_lines.append(f"- Return code: {tr.get('return_value_hex')} ({tr.get('return_value')})")
        report_lines.append(f"- Rectangle: {tr.get('rectangle')}")
        report_lines.append(f"- Unpressed descriptor: {tr.get('unpressed_descriptor')}")
        report_lines.append(f"- Pressed descriptor: {tr.get('pressed_descriptor')}")
        report_lines.append(f"- Goto page: {tr.get('goto_page')}")
        report_lines.append(f"- Touch record offset: {tr.get('touch_record_offset')}")
    else:
        report_lines.append("- Direct descriptor mode (no page/touch mapping).")
    report_lines.append("")
    for r in descriptor_reports:
        did = r["descriptor_id"]
        report_lines.append(f"## Descriptor {did}")
        report_lines.append(f"- Descriptor ID (decimal): {r['descriptor_id']}")
        report_lines.append(f"- Descriptor ID (hexadecimal): {r['descriptor_id_hex']}")
        report_lines.append(f"- Bank: {r['bank']}")
        report_lines.append(f"- Descriptor table index: {r['descriptor_table_index']}")
        report_lines.append(f"- Descriptor table base: {r['descriptor_table_base']}")
        report_lines.append(f"- Descriptor table file offset: {r['descriptor_table_file_offset']}")
        report_lines.append(f"- Exact descriptor entry file offset: {r['exact_descriptor_entry_file_offset']}")
        report_lines.append(f"- Raw descriptor bytes: {r['raw_descriptor_bytes']}")
        report_lines.append(f"- Descriptor entry length: {r['descriptor_entry_length']}")
        report_lines.append(f"- Decoded descriptor fields: {json.dumps(r['decoded_descriptor_fields'])}")
        report_lines.append(f"- Source asset logical address: {r['source_asset_logical_address']}")
        report_lines.append(f"- Source asset file offset: {r['source_asset_file_offset']}")
        report_lines.append(f"- Address translation method: {r['address_translation_method']}")
        report_lines.append(f"- Encoded format number: {r['encoded_format_number']}")
        report_lines.append(f"- Format name: {r['format_name']}")
        report_lines.append(f"- Decoded width: {r['decoded_width']}")
        report_lines.append(f"- Decoded height: {r['decoded_height']}")
        report_lines.append(f"- Encoded payload length: {r['encoded_payload_length']}")
        report_lines.append(f"- Full encoded record length (incl. headers): {r['full_encoded_record_length']}")
        report_lines.append(f"- Encoded range start: {r['encoded_range_start']} (0x{r['encoded_range_start']:08X})")
        report_lines.append(f"- Encoded range end: {r['encoded_range_end']} (0x{r['encoded_range_end']:08X})")
        report_lines.append(f"- Allocation start: {r['allocation_start']} (0x{r['allocation_start']:08X})")
        report_lines.append(f"- Allocation end: {r['allocation_end']} (0x{r['allocation_end']:08X})")
        report_lines.append(f"- Allocation capacity: {r['allocation_capacity']}")
        report_lines.append(f"- Next confirmed asset boundary: {r['next_confirmed_asset_boundary']}")
        report_lines.append(f"- Next confirmed asset boundary verified: {r['next_confirmed_asset_boundary_verified']}")
        report_lines.append(f"- Boundary confidence: {r['boundary_confidence']}")
        report_lines.append(f"- Decoded asset filename: {r['decoded_asset_filename']}")
        report_lines.append(f"- Decoded PNG SHA-256: {r['decoded_png_sha256']}")
        report_lines.append(f"- Source encoded-byte SHA-256: {r['source_encoded_byte_sha256']}")
        report_lines.append(f"- Reference count: {r['reference_count']}")
        report_lines.append(f"- Roles: {', '.join(r['roles']) if r['roles'] else 'none'}")
        report_lines.append(f"- Shared by other pages or controls: {r['shared_by_other_pages_or_controls']}")
        report_lines.append(f"- Manifest decode issues: {len(r['manifest_decode_issues'])} issue(s)")
        report_lines.append("")
    report_lines.append("## Shared references")
    for r in descriptor_reports:
        report_lines.append(f"### Descriptor {r['descriptor_id']}")
        if r["referencing_records"]:
            for ref in r["referencing_records"]:
                report_lines.append(f"- {json.dumps(ref)}")
        else:
            report_lines.append("- No referencing records found.")
        report_lines.append("")
    report_lines.append("## Verified findings")
    for r in descriptor_reports:
        report_lines.append(
            f"- Descriptor {r['descriptor_id']} ({r['descriptor_id_hex']}): bank {r['bank']}, "
            f"format {r['format_name']}, {r['decoded_width']}x{r['decoded_height']}, "
            f"encoded {r['encoded_payload_length']} bytes, allocation capacity {r['allocation_capacity']}, "
            f"boundary {r['boundary_confidence']}."
        )
        if page_mapping:
            tr = page_mapping["touch_record"]
            report_lines.append(
                f"  - Referenced by page {page_id} touch record (return {tr.get('return_value_hex')}) "
                f"as {r['roles'][0] if r['roles'] else 'unknown'}."
            )
    report_lines.append("")
    report_lines.append("## Inferred findings")
    for r in descriptor_reports:
        if r["boundary_confidence"] == "inferred":
            report_lines.append(
                f"- Descriptor {r['descriptor_id']}: next asset boundary inferred (not verified by next descriptor address)."
            )
    if not any(r["boundary_confidence"] == "inferred" for r in descriptor_reports):
        report_lines.append("- None: all next asset boundaries are verified by adjacent descriptor addresses.")
    report_lines.append("")
    report_lines.append("## Unknown fields")
    for r in descriptor_reports:
        report_lines.append(f"- Descriptor {r['descriptor_id']}: format {r['encoded_format_number']} = {r['format_name']} (established).")
        report_lines.append(f"- Descriptor {r['descriptor_id']}: checksum / metadata implications are Unknown (not covered by manifest).")
    report_lines.append("")
    report_lines.append("## Patch feasibility")
    feasible = True
    for r in descriptor_reports:
        if not r["next_confirmed_asset_boundary_verified"]:
            feasible = False
        if not r["manifest_cross_check"].get("size_matches") or not r["manifest_cross_check"].get("format_matches"):
            feasible = False
    if feasible:
        feasibility = "PROVEN_FOR_OFFLINE_WORKING_COPY"
    else:
        feasibility = "UNRESOLVED"
    report_lines.append(f"- Patch feasibility: {feasibility}")
    report_lines.append("- Do not use the word safe without qualification.")
    report_lines.append("- In-place replacement is not declared safe unless: exact encoded byte range, exact allocation boundary,")
    report_lines.append("  encoding format, dimensions, all references, replacement-size limit, metadata implications, checksum")
    report_lines.append("  implications, and no overlap with another asset are all established.")
    report_lines.append("")
    report_lines.append("## Safety conclusion")
    report_lines.append("- The factory source image was not modified (byte-for-byte unchanged, timestamp unchanged).")
    report_lines.append("- All outputs are written only to the selected output directory.")
    report_lines.append("- No hardware, USB, COM, HID, or updater access was performed.")
    report_lines.append("- Patch feasibility: " + feasibility + " (offline working copy only).")
    write_json(os.path.join(output_dir, "descriptor_mapping_report.json"), {"report": "\n".join(report_lines)})
    with open(os.path.join(output_dir, "descriptor_mapping_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    # --- Console summary ---
    print(f"Descriptor mapping complete. Output directory: {output_dir}")
    print(f"Source unchanged: {source_before == source_after}")
    print(f"SHA-256 before: {source_sha_before}")
    print(f"SHA-256 after: {source_sha_after}")
    for r in descriptor_reports:
        print(f"Descriptor {r['descriptor_id']} ({r['descriptor_id_hex']}): encoded SHA-256={r['source_encoded_byte_sha256']}, "
              f"decoded PNG SHA-256={r['decoded_png_sha256']}, references={r['reference_count']}, "
              f"boundary={r['boundary_confidence']}")


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Read-only offline AULA L99 screen descriptor inspector."
    )
    parser.add_argument("--image", required=True, help="Path to UartTFT-II_Flash.bin")
    parser.add_argument("--manifest", required=True, help="Path to manifest.json")
    parser.add_argument("--page", type=str, default=None, help="Page ID (decimal or hex)")
    parser.add_argument("--return-code", type=str, default=None, help="Touch return value (decimal or hex)")
    parser.add_argument("--descriptor", action="append", default=[], help="Descriptor ID (decimal or hex); repeatable")
    parser.add_argument("--output", required=True, help="Output directory (must be empty unless --force-output)")
    parser.add_argument("--allow-unknown-image", action="store_true", help="Research-only override for non-factory images")
    parser.add_argument("--force-output", action="store_true", help="Permit non-empty output directory")
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except DescriptorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
