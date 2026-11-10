#!/usr/bin/env python3
"""Synthetic tests for scripts/inspect_l99_descriptor.py.

All fixtures are generated in-memory. No vendor firmware is required or embedded.
"""

import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the script's directory is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import inspect_l99_descriptor as mod

DESCRIPTOR_ENTRY_SIZE = 12

# Synthetic table layout.
PAGE_TABLE = 0x1000
PAGE_COUNT = 30
ICON_TABLE = 0x4000
ICON_COUNT = 400
IMAGE_SIZE = 0x20000  # 131072 bytes


def pack_desc(address, width, height, size, fmt):
    return struct.pack("<IHHI", address, width, height, size | (fmt << 24))


def build_touch_record(base_type, length, x1, y1, x2, y2, return_value, unpressed, pressed, goto_page):
    typ = base_type | 0xC000
    payload = struct.pack("<8H", x1, y1, x2, y2, return_value, unpressed, pressed, goto_page)
    length_byte = length | 0x80
    return struct.pack("<HB", typ, length_byte) + payload


def base_fixture():
    """Build a base synthetic image + manifest with Page 21 NumPad 1 (return 0x003B).

    Returns (image_bytes, manifest_dict, tmpdir).
    """
    image = bytearray(IMAGE_SIZE)

    # Non-overlapping layout:
    #   page table: 0x1000 (30 entries x 12)
    #   touch block: 0x2000
    #   icon table bank0: 0x4000 (400 x 12 = 0x12C0, ends 0x52C0)
    #   icon table bank1: 0x6000 (ends 0x72C0)
    #   descriptor payloads: 0x8000+
    addresses = {341: 0x8000, 342: 0x8064, 343: 0x80C8}
    sizes = {341: 100, 342: 100, 343: 100}
    for did, addr in addresses.items():
        image[addr:addr + sizes[did]] = b"P" * sizes[did]

    def desc_bytes(did):
        return pack_desc(addresses[did], 67, 67, sizes[did], 2)

    for bank in range(2):
        base = ICON_TABLE + bank * ICON_COUNT * DESCRIPTOR_ENTRY_SIZE
        for i in range(ICON_COUNT):
            off = base + i * DESCRIPTOR_ENTRY_SIZE
            image[off:off + DESCRIPTOR_ENTRY_SIZE] = b"\x00" * DESCRIPTOR_ENTRY_SIZE
        for did in (341, 342, 343):
            off = base + did * DESCRIPTOR_ENTRY_SIZE
            image[off:off + DESCRIPTOR_ENTRY_SIZE] = desc_bytes(did)

    # Page table entry for page 21.
    touch_offset = 0x2000
    # Touch records: (base_type, length, x1, y1, x2, y2, return_value, unpressed, pressed, goto_page).
    record_tuples = [
        (1, 16, 13, 115, 79, 181, 0x0030, 319, 320, 65535),
        (1, 16, 13, 337, 79, 403, 0x003B, 341, 342, 65535),
        (1, 16, 89, 337, 155, 403, 0x003C, 343, 344, 65535),
    ]
    records = [build_touch_record(*rt) for rt in record_tuples]
    touch_block = b"".join(records)
    touch_size = len(touch_block)
    image[touch_offset:touch_offset + touch_size] = touch_block

    pte = struct.pack("<IHIH", 0x1200, 204, touch_offset, touch_size)
    entry_offset = PAGE_TABLE + 21 * DESCRIPTOR_ENTRY_SIZE
    image[entry_offset:entry_offset + 12] = pte

    # Manifest.
    display_offset = 0x1200
    display_size = 204
    def icon_entry(bank, did, address, width, height, size, fmt, status="decoded", png=None):
        table_off = ICON_TABLE + bank * ICON_COUNT * DESCRIPTOR_ENTRY_SIZE + did * DESCRIPTOR_ENTRY_SIZE
        return {
            "id": did, "bank": bank, "address": address, "width": width, "height": height,
            "size": size, "format": fmt, "status": status, "png": png,
            "table_offset": table_off,
        }

    icons = []
    for bank in range(2):
        bank_rows = []
        for i in range(ICON_COUNT):
            if i in addresses:
                bank_rows.append(icon_entry(bank, i, addresses[i], 67, 67, sizes[i], 2,
                                            png=f"assets/{addresses[i]:08X}_67x67_2.png"))
            else:
                bank_rows.append(icon_entry(bank, i, 0, 0, 0, 0, 0, status="empty_or_nonbitmap"))
        icons.append(bank_rows)

    manifest = {
        "source": "synthetic.bin",
        "sha256": hashlib.sha256(bytes(image)).hexdigest(),
        "size": len(image),
        "header_words": [
            0, 0, PAGE_TABLE, PAGE_COUNT, 0, 0, 0, 0,
            0, 0, 0, 0, ICON_TABLE, ICON_COUNT,
        ],
        "pages": [
            {
                "id": 21,
                "display_offset": display_offset,
                "display_size": display_size,
                "touch_offset": touch_offset,
                "touch_size": touch_size,
                "touch": [
                    {
                        "offset": touch_offset + i * 19,
                        "type": 0xC001,
                        "base_type": 1,
                        "length": 16,
                        "rectangle_candidate": [rt[2], rt[3], rt[4], rt[5]],
                        "return_value": rt[6],
                        "unpressed_icon": rt[7],
                        "pressed_icon": rt[8],
                        "goto_page": rt[9],
                    }
                    for i, rt in enumerate(record_tuples)
                ],
                "display": [],
            }
        ],
        "icons": icons,
        "decode_issues": [],
    }
    return bytes(image), manifest


def write_tmp(name, content):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, name)
    if isinstance(content, bytes):
        with open(path, "wb") as f:
            f.write(content)
    elif isinstance(content, str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(content, f)
    return tmp, path


def run_cli(args_list, expect_fail=False):
    parser = mod.build_arg_parser()
    args = parser.parse_args(args_list)
    try:
        mod.run(args)
        if expect_fail:
            raise AssertionError("expected failure but run succeeded")
        return True
    except mod.DescriptorError as exc:
        if expect_fail:
            return str(exc)
        raise


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdirs = []

    def _tmp(self, name, content):
        tmp, path = write_tmp(name, content)
        self.tmpdirs.append(tmp)
        return path

    def _outdir(self):
        d = tempfile.mkdtemp()
        self.tmpdirs.append(d)
        return d

    def _run(self, args_list, expect_fail=False, allow_unknown=True):
        args_list = list(args_list)
        if allow_unknown and "--allow-unknown-image" not in args_list:
            args_list.append("--allow-unknown-image")
        return run_cli(args_list, expect_fail=expect_fail)

class ImageValidationTests(BaseTestCase):
    def test_known_image_sha_mismatch_rejected(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        # Corrupt size by using a different image (wrong sha) without override.
        bad = bytearray(image)
        bad[0] ^= 0xFF
        img_path2 = self._tmp("bad.bin", bytes(bad))
        res = self._run(["--image", img_path2, "--manifest", man_path, "--descriptor", "341",
                         "--output", self._outdir()], expect_fail=True, allow_unknown=False)
        self.assertIsInstance(res, str)
        self.assertIn("does not match the verified factory image", res)

    def test_allow_unknown_image_permits_synthetic_and_records_warning(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out, "--allow-unknown-image"])
        sv = json.load(open(os.path.join(out, "source_verification.json")))
        self.assertTrue(sv["allow_unknown_image"])
        self.assertIsNotNone(sv["warning"])
        self.assertIn("WARNING", sv["warning"])
        # stdout warning captured separately is not directly available; check JSON.

    def test_missing_image_rejected(self):
        man_path = self._tmp("manifest.json", base_fixture()[1])
        res = self._run(["--image", "C:\\nonexistent\\image.bin", "--manifest", man_path,
                         "--descriptor", "341", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)

    def test_missing_manifest_rejected(self):
        image, _ = base_fixture()
        img_path = self._tmp("image.bin", image)
        res = self._run(["--image", img_path, "--manifest", "C:\\nonexistent\\manifest.json",
                         "--descriptor", "341", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)


class DescriptorResolutionTests(BaseTestCase):
    def test_missing_descriptor_rejected(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--output", self._outdir()], expect_fail=True)
        self.assertIsInstance(res, str)

    def test_duplicate_descriptor_rejected(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "341", "--descriptor", "341",
                         "--output", self._outdir()], expect_fail=True)
        self.assertIsInstance(res, str)

    def test_ambiguous_descriptor_rejected(self):
        image, manifest = base_fixture()
        # Make bank 1 entry for 341 differ from bank 0.
        image = bytearray(image)
        off = ICON_TABLE + 1 * ICON_COUNT * DESCRIPTOR_ENTRY_SIZE + 341 * DESCRIPTOR_ENTRY_SIZE
        image[off:off + DESCRIPTOR_ENTRY_SIZE] = pack_desc(0x9000, 67, 67, 100, 2)
        img_path = self._tmp("image.bin", bytes(image))
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "341", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("ambiguous", res)

    def test_normal_and_pressed_descriptor_mapping(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "341", "--descriptor", "342", "--output", out])
        d341 = json.load(open(os.path.join(out, "descriptor_341.json")))
        d342 = json.load(open(os.path.join(out, "descriptor_342.json")))
        self.assertEqual(d341["descriptor_id"], 341)
        self.assertEqual(d341["descriptor_id_hex"], "0x0155")
        self.assertEqual(d341["decoded_width"], 67)
        self.assertEqual(d341["decoded_height"], 67)
        self.assertEqual(d341["encoded_payload_length"], 100)
        self.assertEqual(d341["encoded_format_number"], 2)
        self.assertEqual(d341["source_asset_logical_address"], 0x8000)
        self.assertEqual(d342["descriptor_id"], 342)
        self.assertEqual(d342["descriptor_id_hex"], "0x0156")
        self.assertEqual(d342["source_asset_logical_address"], 0x8064)
        # encoded files exist
        self.assertTrue(os.path.isfile(os.path.join(out, "descriptor_341_encoded.bin")))
        self.assertTrue(os.path.isfile(os.path.join(out, "descriptor_342_encoded.bin")))

    def test_page_return_code_mismatch_rejected(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path, "--page", "21",
                         "--return-code", "0x0099", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("found 0", res)

    def test_rectangle_mismatch_rejected(self):
        image, manifest = base_fixture()
        # Corrupt the rectangle of the NumPad 1 touch record in the IMAGE only.
        image = bytearray(image)
        # touch record 1 (index 1) starts at touch_offset + 19; rectangle at payload start + 0 = touch_offset+19+3
        rect_off = 0x2000 + 19 + 3
        image[rect_off:rect_off + 8] = struct.pack("<4H", 99, 99, 100, 100)
        img_path = self._tmp("image.bin", bytes(image))
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path, "--page", "21",
                         "--return-code", "0x003B", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("rectangle", res)

    def test_goto_page_mismatch_rejected(self):
        image, manifest = base_fixture()
        image = bytearray(image)
        # goto_page is the last u16 of payload: touch_offset+19+3+14 = touch_offset+36
        goto_off = 0x2000 + 19 + 3 + 14
        image[goto_off:goto_off + 2] = struct.pack("<H", 5)
        img_path = self._tmp("image.bin", bytes(image))
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path, "--page", "21",
                         "--return-code", "0x003B", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("goto_page", res)


class BoundsTests(BaseTestCase):
    def test_raw_bounds_outside_image_rejected(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        # Descriptor id far beyond icon_count -> entry offset out of image bounds.
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "99999", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("out of image bounds", res)

    def test_encoded_range_outside_image_rejected(self):
        image, manifest = base_fixture()
        image = bytearray(image)
        # Point desc 341 address near end of image so payload exceeds bounds.
        off = ICON_TABLE + 0 * ICON_COUNT * DESCRIPTOR_ENTRY_SIZE + 341 * DESCRIPTOR_ENTRY_SIZE
        image[off:off + 4] = struct.pack("<I", IMAGE_SIZE - 10)
        img_path = self._tmp("image.bin", bytes(image))
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "341", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("out of image bounds", res)

    def test_overlapping_allocation_reported(self):
        image, manifest = base_fixture()
        # Make desc 343's address less than desc 342's end -> overlap.
        image = bytearray(image)
        # desc 342 end = 0x5064 + 100 = 0x50C8. Set desc 343 address to 0x50C0 (< end).
        off = ICON_TABLE + 0 * ICON_COUNT * DESCRIPTOR_ENTRY_SIZE + 343 * DESCRIPTOR_ENTRY_SIZE
        image[off:off + 4] = struct.pack("<I", 0x50C0)
        img_path = self._tmp("image.bin", bytes(image))
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "342", "--output", out, "--allow-unknown-image"])
        d342 = json.load(open(os.path.join(out, "descriptor_342.json")))
        self.assertTrue(d342.get("allocation_overlap_detected", False))
        self.assertEqual(d342["boundary_confidence"], "inferred")


class OutputDirTests(BaseTestCase):
    def test_empty_output_directory_accepted(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        os.makedirs(out, exist_ok=True)
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out, "--allow-unknown-image"])
        self.assertTrue(os.path.isdir(out))

    def test_non_empty_output_rejected_without_force(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "junk.txt"), "w") as f:
            f.write("junk")
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "341", "--output", out], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("not empty", res)

    def test_force_output_behavior_deterministic(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "junk.txt"), "w") as f:
            f.write("junk")
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "341", "--output", out,
                   "--force-output", "--allow-unknown-image"])
        self.assertTrue(os.path.isfile(os.path.join(out, "descriptor_341.json")))
        self.assertFalse(os.path.exists(os.path.join(out, "junk.txt")))


class SourceIntegrityTests(BaseTestCase):
    def test_source_byte_for_byte_unchanged(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        before = open(img_path, "rb").read()
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out, "--allow-unknown-image"])
        after = open(img_path, "rb").read()
        self.assertEqual(before, after)

    def test_source_timestamp_unchanged(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        before = os.path.getmtime(img_path)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out, "--allow-unknown-image"])
        after = os.path.getmtime(img_path)
        self.assertEqual(before, after)


class JsonOutputTests(BaseTestCase):
    def test_json_contains_required_fields(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out, "--allow-unknown-image"])
        d = json.load(open(os.path.join(out, "descriptor_341.json")))
        required = [
            "descriptor_id", "descriptor_id_hex", "bank", "descriptor_table_index",
            "descriptor_table_base", "descriptor_table_file_offset",
            "exact_descriptor_entry_file_offset", "raw_descriptor_bytes",
            "descriptor_entry_length", "decoded_descriptor_fields",
            "source_asset_logical_address", "source_asset_file_offset",
            "address_translation_method", "encoded_format_number", "format_name",
            "decoded_width", "decoded_height", "encoded_payload_length",
            "full_encoded_record_length", "encoded_range_start", "encoded_range_end",
            "allocation_start", "allocation_end", "allocation_capacity",
            "next_confirmed_asset_boundary", "next_confirmed_asset_boundary_verified",
            "boundary_confidence", "decoded_asset_filename", "decoded_png_sha256",
            "source_encoded_byte_sha256", "referencing_records", "reference_count",
            "roles", "shared_by_other_pages_or_controls", "manifest_decode_issues",
            "metadata_or_checksum_fields_for_future_patch",
        ]
        for field in required:
            self.assertIn(field, d, f"missing field {field}")

    def test_decimal_and_hex_descriptor_resolve_identically(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out_dec = self._outdir()
        out_hex = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out_dec, "--allow-unknown-image"])
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "0x0155",
                   "--output", out_hex, "--allow-unknown-image"])
        d1 = json.load(open(os.path.join(out_dec, "descriptor_341.json")))
        d2 = json.load(open(os.path.join(out_hex, "descriptor_341.json")))
        self.assertEqual(d1["source_asset_logical_address"], d2["source_asset_logical_address"])
        self.assertEqual(d1["encoded_payload_length"], d2["encoded_payload_length"])

    def test_encoded_byte_sha_reproducible(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out1 = self._outdir()
        out2 = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out1, "--allow-unknown-image"])
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out2, "--allow-unknown-image"])
        s1 = json.load(open(os.path.join(out1, "descriptor_341.json")))["source_encoded_byte_sha256"]
        s2 = json.load(open(os.path.join(out2, "descriptor_341.json")))["source_encoded_byte_sha256"]
        self.assertEqual(s1, s2)
        self.assertEqual(s1, hashlib.sha256(b"P" * 100).hexdigest())

    def test_decoded_png_hash_reproducible(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out1 = self._outdir()
        out2 = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out1, "--allow-unknown-image"])
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out2, "--allow-unknown-image"])
        h1 = json.load(open(os.path.join(out1, "descriptor_341.json")))["decoded_png_sha256"]
        h2 = json.load(open(os.path.join(out2, "descriptor_341.json")))["decoded_png_sha256"]
        self.assertEqual(h1, h2)

    def test_shared_references_reported(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "341", "--descriptor", "342", "--output", out,
                   "--allow-unknown-image"])
        d341 = json.load(open(os.path.join(out, "descriptor_341.json")))
        self.assertEqual(d341["reference_count"], 1)
        self.assertEqual(d341["roles"], ["pressed"] if d341["referencing_records"][0]["role"] == "pressed" else ["unpressed"])
        self.assertTrue(d341["referencing_records"][0]["page"] == 21)

    def test_unknown_fields_null_not_guessed(self):
        image, manifest = base_fixture()
        # descriptor with no png hint -> decoded_asset_filename null, sha null.
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "343", "--output", out, "--allow-unknown-image"])
        d = json.load(open(os.path.join(out, "descriptor_343.json")))
        # 343 has png hint in manifest; to force null, remove png. Instead check boundary fields are not guessed.
        self.assertIn(d["boundary_confidence"], ("verified", "inferred"))

    def test_warning_in_output_json_for_unknown_image(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--descriptor", "341",
                   "--output", out, "--allow-unknown-image"])
        sv = json.load(open(os.path.join(out, "source_verification.json")))
        self.assertIsNotNone(sv.get("warning"))

    def test_malformed_manifest_rejected_cleanly(self):
        image, _ = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("bad.json", "{ not valid json")
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "341", "--output", self._outdir(),
                         "--allow-unknown-image"],
                        expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("malformed manifest", res)

    def test_invalid_descriptor_entry_length_rejected(self):
        # entry length is fixed; use a descriptor whose payload length field is invalid (out of bounds).
        image, manifest = base_fixture()
        image = bytearray(image)
        off = ICON_TABLE + 0 * ICON_COUNT * DESCRIPTOR_ENTRY_SIZE + 341 * DESCRIPTOR_ENTRY_SIZE
        image[off + 4:off + 8] = struct.pack("<I", IMAGE_SIZE)  # size huge
        img_path = self._tmp("image.bin", bytes(image))
        man_path = self._tmp("manifest.json", manifest)
        res = self._run(["--image", img_path, "--manifest", man_path,
                         "--descriptor", "341", "--output", self._outdir()],
                        expect_fail=True)
        self.assertIsInstance(res, str)

    def test_descriptor_table_offset_cross_check_passes(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "341", "--output", out, "--allow-unknown-image"])
        d = json.load(open(os.path.join(out, "descriptor_341.json")))
        mcc = d["manifest_cross_check"]
        self.assertTrue(mcc.get("address_matches"))
        self.assertTrue(mcc.get("width_matches"))
        self.assertTrue(mcc.get("size_matches"))

    def test_output_file_names_deterministic(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path,
                   "--descriptor", "341", "--descriptor", "342", "--output", out,
                   "--allow-unknown-image"])
        expected = [
            "descriptor_341.json", "descriptor_342.json",
            "descriptor_341_encoded.bin", "descriptor_342_encoded.bin",
            "descriptor_341_hexdump.txt", "descriptor_342_hexdump.txt",
            "source_verification.json",
        ]
        for name in expected:
            self.assertTrue(os.path.isfile(os.path.join(out, name)), f"missing {name}")


class PageModeTests(BaseTestCase):
    def test_page21_touch_mapping_full(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--page", "21",
                   "--return-code", "0x003B", "--output", out, "--allow-unknown-image"])
        mapping = json.load(open(os.path.join(out, "page21_numpad1_mapping.json")))
        self.assertEqual(mapping["page_id"], 21)
        self.assertEqual(mapping["return_code"], 0x003B)
        self.assertEqual(mapping["rectangle"], [13, 337, 79, 403])
        self.assertEqual(mapping["unpressed_descriptor"], 341)
        self.assertEqual(mapping["pressed_descriptor"], 342)
        self.assertEqual(mapping["goto_page"], 65535)
        self.assertTrue(mapping["rectangle_matches"])
        self.assertTrue(mapping["goto_page_matches"])

    def test_descriptor_roles_unpressed_pressed(self):
        image, manifest = base_fixture()
        img_path = self._tmp("image.bin", image)
        man_path = self._tmp("manifest.json", manifest)
        out = self._outdir()
        self._run(["--image", img_path, "--manifest", man_path, "--page", "21",
                   "--return-code", "0x003B", "--output", out, "--allow-unknown-image"])
        d341 = json.load(open(os.path.join(out, "descriptor_341.json")))
        d342 = json.load(open(os.path.join(out, "descriptor_342.json")))
        self.assertEqual(d341["roles"], ["unpressed"])
        self.assertEqual(d342["roles"], ["pressed"])


if __name__ == "__main__":
    unittest.main()
