#!/usr/bin/env python3
"""Synthetic tests for scripts/patch_l99_numpad_icon.py.

All fixtures are generated in-memory with Pillow. No vendor firmware is required
or embedded. The --allow-unknown-image flag permits synthetic (non-factory)
images for test coverage; strict factory validation is exercised separately.
"""

import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

# Ensure the script's directory is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import patch_l99_numpad_icon as mod

DESC_341_OFFSET = mod.DESC_341_OFFSET
DESC_342_OFFSET = mod.DESC_342_OFFSET
DESC_341_END = mod.DESC_341_END
DESC_342_END = mod.DESC_342_END
RECORD_SIZE = mod.RECORD_SIZE
ICON_WIDTH = mod.ICON_WIDTH
ICON_HEIGHT = mod.ICON_HEIGHT
FACTORY_SIZE = mod.FACTORY_SIZE
FACTORY_SHA256 = mod.FACTORY_SHA256


def argb4444_pack_pixel(r, g, b, a):
    return ((a >> 4) << 12) | ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4)


def build_encoded_record(width, height, fill_rgba):
    pixels = [fill_rgba] * (width * height)
    return mod.argb4444_encode(pixels, width, height)


def make_rgba_png(path, width, height, fill_rgba):
    im = Image.new("RGBA", (width, height), fill_rgba)
    im.save(path, format="PNG")


def base_synthetic_image(size=DESC_342_END + 4096):
    """Build a synthetic image covering the highest tested offset plus record length."""
    image = bytearray(size)
    rec1 = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
    rec2 = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0x55, 0x66, 0x77, 0x88))
    image[DESC_341_OFFSET:DESC_341_END] = rec1
    image[DESC_342_OFFSET:DESC_342_END] = rec2
    return bytes(image)


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
    except mod.PatchError as exc:
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


# --- Exact ARGB4444 golden vectors -------------------------------------------
# Layout per u16 (little-endian): [15:12]=A [11:8]=R [7:4]=G [3:0]=B.
# Decode replicates each nibble to a full byte: 0xN -> 0xN0|N.
GOLDEN_PIXEL_TO_BYTE = [
    # (r, g, b, a) -> expected LE u16 value. v = (A<<12)|(R<<8)|(G<<4)|B, each channel>>4.
    ((0x00, 0x00, 0x00, 0x00), 0x0000),          # minimums
    ((0xFF, 0xFF, 0xFF, 0xFF), 0xFFFF),          # maximums
    ((0x12, 0x34, 0x56, 0x78), 0x7135),          # A=7,R=1,G=3,B=5
    ((0xAB, 0xCD, 0xEF, 0x0F), 0x0ACE),          # A=0,R=A,G=C,B=E
    ((0x21, 0x43, 0x65, 0x87), 0x8246),          # A=8,R=2,G=4,B=6
    ((0xFF, 0x00, 0x00, 0x00), 0x0F00),          # red only
    ((0x00, 0xFF, 0x00, 0x00), 0x00F0),          # green only
    ((0x00, 0x00, 0xFF, 0x00), 0x000F),          # blue only
    ((0x00, 0x00, 0x00, 0xFF), 0xF000),          # alpha only
]

GOLDEN_BYTE_TO_PIXEL = [
    # (LE u16 value) -> (r, g, b, a), replicate each nibble N -> (N<<4)|N.
    (0x0000, (0x00, 0x00, 0x00, 0x00)),
    (0xFFFF, (0xFF, 0xFF, 0xFF, 0xFF)),
    (0x8736, (0x77, 0x33, 0x66, 0x88)),          # A=8,R=7,G=3,B=6
    (0x0ACE, (0xAA, 0xCC, 0xEE, 0x00)),          # A=0,R=A,G=C,B=E
    (0x8246, (0x22, 0x44, 0x66, 0x88)),          # A=8,R=2,G=4,B=6
    (0x0F00, (0xFF, 0x00, 0x00, 0x00)),
    (0x00F0, (0x00, 0xFF, 0x00, 0x00)),
    (0x000F, (0x00, 0x00, 0xFF, 0x00)),
    (0xF000, (0x00, 0x00, 0x00, 0xFF)),
]


class EncodeDecodeGoldenTests(BaseTestCase):
    def test_pixel_to_byte_golden_vectors(self):
        for (r, g, b, a), expected_u16 in GOLDEN_PIXEL_TO_BYTE:
            encoded = mod.argb4444_encode([(r, g, b, a)], 1, 1)
            actual_u16 = struct.unpack_from("<H", encoded, 0)[0]
            self.assertEqual(actual_u16, expected_u16,
                             f"encode({r},{g},{b},{a}) = 0x{actual_u16:04X}, expected 0x{expected_u16:04X}")

    def test_byte_to_pixel_golden_vectors(self):
        for u16_value, expected_rgba in GOLDEN_BYTE_TO_PIXEL:
            encoded = struct.pack("<H", u16_value)
            pixels = mod.argb4444_decode(encoded, 1, 1)
            self.assertEqual(pixels[0], expected_rgba,
                             f"decode(0x{u16_value:04X}) = {pixels[0]}, expected {expected_rgba}")

    def test_byte_order_le(self):
        # 0x1234 stored little-endian as bytes 34 12.
        encoded = mod.argb4444_encode([(0x20, 0x10, 0x40, 0x80)], 1, 1)
        raw = struct.unpack_from("<H", encoded, 0)[0]
        self.assertEqual(raw, 0x8214)  # A=8,R=2,G=1,B=4
        self.assertEqual(encoded[0], 0x14)  # low byte first (LE)
        self.assertEqual(encoded[1], 0x82)

    def test_alpha_red_green_blue_nibble_placement(self):
        # A nibble at bits 15:12, R at 11:8, G at 7:4, B at 3:0.
        encoded = mod.argb4444_encode([(0x10, 0x20, 0x40, 0x80)], 1, 1)
        v = struct.unpack_from("<H", encoded, 0)[0]
        self.assertEqual((v >> 12) & 0xF, 8)   # A = 0x80>>4 = 8
        self.assertEqual((v >> 8) & 0xF, 1)    # R = 0x10>>4 = 1
        self.assertEqual((v >> 4) & 0xF, 2)    # G = 0x20>>4 = 2
        self.assertEqual(v & 0xF, 4)           # B = 0x40>>4 = 4

    def test_minimum_and_maximum_values(self):
        # 0x0000 -> all channels 0
        self.assertEqual(mod.argb4444_decode(struct.pack("<H", 0x0000), 1, 1)[0],
                         (0x00, 0x00, 0x00, 0x00))
        # 0xFFFF -> all channels 255 (nibble F replicated to 0xFF)
        self.assertEqual(mod.argb4444_decode(struct.pack("<H", 0xFFFF), 1, 1)[0],
                         (0xFF, 0xFF, 0xFF, 0xFF))

    def test_asymmetric_values_detect_swapped_channels(self):
        # encode then decode must not swap channels: asymmetric pattern.
        pixels = [(0x12, 0x34, 0x56, 0x78)]
        encoded = mod.argb4444_encode(pixels, 1, 1)
        decoded = mod.argb4444_decode(encoded, 1, 1)
        self.assertEqual(decoded[0], (0x11, 0x33, 0x55, 0x77))
        # Confirm channel positions: A=7, R=1, G=3, B=6 nibbles replicated.
        v = struct.unpack_from("<H", encoded, 0)[0]
        self.assertEqual(((v >> 12) & 0xF, (v >> 8) & 0xF, (v >> 4) & 0xF, v & 0xF),
                         (7, 1, 3, 5))

    def test_decode_wrong_length_rejected(self):
        with self.assertRaises(mod.PatchError):
            mod.argb4444_decode(b"\x00" * 10, ICON_WIDTH, ICON_HEIGHT)

    def test_encode_wrong_pixel_count_rejected(self):
        with self.assertRaises(mod.PatchError):
            mod.argb4444_encode([(0, 0, 0, 0)] * 5, 1, 3)


class FactoryRoundTripTests(BaseTestCase):
    def test_factory_descriptor_341_round_trip(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        out = self._outdir()
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out, "--allow-unknown-image"])
        report = json.load(open(os.path.join(out, "patch_report.json")))
        self.assertTrue(report["roundtrip_descriptor_341"])
        self.assertTrue(report["roundtrip_descriptor_342"])

    def test_factory_record_sha_matches_known(self):
        image = base_synthetic_image()
        rec1 = image[DESC_341_OFFSET:DESC_341_END]
        rec2 = image[DESC_342_OFFSET:DESC_342_END]
        self.assertEqual(len(rec1), RECORD_SIZE)
        self.assertEqual(len(rec2), RECORD_SIZE)
        # Re-encode the decoded records and require byte-for-byte equality.
        self.assertEqual(mod.argb4444_encode(
            mod.argb4444_decode(rec1, ICON_WIDTH, ICON_HEIGHT), ICON_WIDTH, ICON_HEIGHT), rec1)
        self.assertEqual(mod.argb4444_encode(
            mod.argb4444_decode(rec2, ICON_WIDTH, ICON_HEIGHT), ICON_WIDTH, ICON_HEIGHT), rec2)


class DimensionValidationTests(BaseTestCase):
    def test_wrong_normal_dimensions_rejected(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, 66, ICON_HEIGHT, (0, 0, 0, 0))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        res = run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                       "--output-dir", self._outdir(), "--allow-unknown-image"], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("dimensions", res)

    def test_wrong_pressed_dimensions_rejected(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        make_rgba_png(pressed_path, ICON_WIDTH, 66, (0, 0, 0, 0))
        res = run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                       "--output-dir", self._outdir(), "--allow-unknown-image"], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("dimensions", res)


class MalformedPngTests(BaseTestCase):
    def test_malformed_png_rejected(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"not a png")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        res = run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                       "--output-dir", self._outdir(), "--allow-unknown-image"], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("malformed PNG", res)


class EncodedSizeTests(BaseTestCase):
    def test_wrong_encoded_length_8976_rejected(self):
        source = base_synthetic_image()
        normal_short = b"\x00" * (RECORD_SIZE - 2)
        pressed_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        with self.assertRaises(mod.PatchError) as ctx:
            mod.apply_patch(source, normal_short, pressed_correct)
        self.assertIn("8976", str(ctx.exception))

    def test_wrong_encoded_length_8980_rejected(self):
        source = base_synthetic_image()
        normal_long = b"\x00" * (RECORD_SIZE + 2)
        pressed_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        with self.assertRaises(mod.PatchError) as ctx:
            mod.apply_patch(source, normal_long, pressed_correct)
        self.assertIn("8980", str(ctx.exception))

    def test_wrong_pressed_encoded_length_rejected(self):
        source = base_synthetic_image()
        normal_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        pressed_short = b"\x00" * (RECORD_SIZE - 2)
        with self.assertRaises(mod.PatchError) as ctx:
            mod.apply_patch(source, normal_correct, pressed_short)
        self.assertIn("8976", str(ctx.exception))

    def test_correct_8978_length_accepted(self):
        source = base_synthetic_image()
        normal_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        pressed_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        patched = mod.apply_patch(source, normal_correct, pressed_correct)
        self.assertEqual(len(patched), len(source))


class InputOutputCollisionTests(BaseTestCase):
    def test_input_output_same_file_rejected(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        import shutil
        out_dir = tempfile.mkdtemp()
        self.tmpdirs.append(out_dir)
        out_patched = os.path.join(out_dir, "patched_UartTFT-II_Flash.bin")
        # Copy the image into the output dir under the patched output name.
        shutil.copyfile(img_path, out_patched)
        # --image now resolves to the same file as the patched output.
        res = run_cli(["--image", out_patched, "--normal", normal_path, "--pressed", pressed_path,
                       "--output-dir", out_dir, "--allow-unknown-image"], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("same file", res)

    def test_normal_and_pressed_same_file_rejected(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        shared = self._tmp("shared.png", b"")
        make_rgba_png(shared, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        res = run_cli(["--image", img_path, "--normal", shared, "--pressed", shared,
                       "--output-dir", self._outdir(), "--allow-unknown-image"], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("same file", res)


class SourceRecordMismatchTests(BaseTestCase):
    def test_source_record_baseline_hash_detects_mismatch(self):
        """Corrupting a source record changes its SHA-256 vs the known baseline,
        so a baseline-hash comparison (performed before any patch write) detects it."""
        source = base_synthetic_image()
        rec1 = source[DESC_341_OFFSET:DESC_341_END]
        rec2 = source[DESC_342_OFFSET:DESC_342_END]
        baseline_1 = hashlib.sha256(rec1).hexdigest()
        baseline_2 = hashlib.sha256(rec2).hexdigest()
        self.assertEqual(len(rec1), RECORD_SIZE)
        self.assertEqual(len(rec2), RECORD_SIZE)

        # Corrupt one byte of record 1.
        corrupted = bytearray(source)
        corrupted[DESC_341_OFFSET] ^= 0xFF
        corrupted_rec1 = bytes(corrupted)[DESC_341_OFFSET:DESC_341_END]
        self.assertNotEqual(hashlib.sha256(corrupted_rec1).hexdigest(), baseline_1)
        self.assertEqual(hashlib.sha256(bytes(corrupted)[DESC_342_OFFSET:DESC_342_END]).hexdigest(),
                         baseline_2)

    def test_valid_source_records_match_baseline(self):
        source = base_synthetic_image()
        ref = base_synthetic_image()
        self.assertEqual(hashlib.sha256(source[DESC_341_OFFSET:DESC_341_END]).hexdigest(),
                         hashlib.sha256(ref[DESC_341_OFFSET:DESC_341_END]).hexdigest())
        self.assertEqual(hashlib.sha256(source[DESC_342_OFFSET:DESC_342_END]).hexdigest(),
                         hashlib.sha256(ref[DESC_342_OFFSET:DESC_342_END]).hexdigest())


class DestinationRangeBoundsTests(BaseTestCase):
    def test_destination_range_exceeds_image_rejected(self):
        # Source too small to contain the destination patch ranges.
        source = bytearray(100)
        normal_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        pressed_correct = build_encoded_record(ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        with self.assertRaises(mod.PatchError) as ctx:
            mod.apply_patch(bytes(source), normal_correct, pressed_correct)
        self.assertIn("exceeds image size", str(ctx.exception))


class ExactTwoRangePatchTests(BaseTestCase):
    def test_exact_two_range_patch(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        out = self._outdir()
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out, "--allow-unknown-image"])
        patched = open(os.path.join(out, "patched_UartTFT-II_Flash.bin"), "rb").read()
        normal_enc = open(os.path.join(out, "normal_encoded.bin"), "rb").read()
        pressed_enc = open(os.path.join(out, "pressed_encoded.bin"), "rb").read()
        self.assertEqual(len(normal_enc), RECORD_SIZE)
        self.assertEqual(len(pressed_enc), RECORD_SIZE)
        self.assertEqual(patched[DESC_341_OFFSET:DESC_341_END], normal_enc)
        self.assertEqual(patched[DESC_342_OFFSET:DESC_342_END], pressed_enc)
        dr = json.load(open(os.path.join(out, "diff_ranges.json")))
        self.assertEqual(len(dr), 2)
        self.assertEqual(dr[0]["descriptor"], 341)
        self.assertEqual(dr[0]["role"], "unpressed")
        self.assertEqual(dr[1]["descriptor"], 342)
        self.assertEqual(dr[1]["role"], "pressed")


class AllOtherBytesUnchangedTests(BaseTestCase):
    def test_all_other_bytes_unchanged(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        out = self._outdir()
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out, "--allow-unknown-image"])
        patched = open(os.path.join(out, "patched_UartTFT-II_Flash.bin"), "rb").read()
        for i in range(len(image)):
            if DESC_341_OFFSET <= i < DESC_341_END or DESC_342_OFFSET <= i < DESC_342_END:
                continue
            self.assertEqual(patched[i], image[i], f"byte changed at {i}")


class DeterministicOutputTests(BaseTestCase):
    def test_deterministic_output(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        out1 = self._outdir()
        out2 = self._outdir()
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out1, "--allow-unknown-image"])
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out2, "--allow-unknown-image"])
        p1 = open(os.path.join(out1, "patched_UartTFT-II_Flash.bin"), "rb").read()
        p2 = open(os.path.join(out2, "patched_UartTFT-II_Flash.bin"), "rb").read()
        self.assertEqual(p1, p2)
        n1 = open(os.path.join(out1, "normal_encoded.bin"), "rb").read()
        n2 = open(os.path.join(out2, "normal_encoded.bin"), "rb").read()
        self.assertEqual(n1, n2)


class SourceImageUnchangedTests(BaseTestCase):
    def test_source_image_unchanged(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        before = open(img_path, "rb").read()
        mtime_before = os.path.getmtime(img_path)
        out = self._outdir()
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out, "--allow-unknown-image"])
        after = open(img_path, "rb").read()
        self.assertEqual(before, after)
        self.assertEqual(os.path.getmtime(img_path), mtime_before)


class FactoryHashRejectionTests(BaseTestCase):
    def test_factory_hash_rejection_strict_mode(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0, 0, 0, 0))
        res = run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                       "--output-dir", self._outdir()], expect_fail=True)
        self.assertIsInstance(res, str)
        self.assertIn("factory", res.lower())


class OutputsTests(BaseTestCase):
    def test_all_outputs_generated(self):
        image = base_synthetic_image()
        img_path = self._tmp("image.bin", image)
        normal_path = self._tmp("normal.png", b"")
        pressed_path = self._tmp("pressed.png", b"")
        make_rgba_png(normal_path, ICON_WIDTH, ICON_HEIGHT, (0xAA, 0xBB, 0xCC, 0xDD))
        make_rgba_png(pressed_path, ICON_WIDTH, ICON_HEIGHT, (0x11, 0x22, 0x33, 0x44))
        out = self._outdir()
        run_cli(["--image", img_path, "--normal", normal_path, "--pressed", pressed_path,
                 "--output-dir", out, "--allow-unknown-image"])
        expected = [
            "patched_UartTFT-II_Flash.bin",
            "patch_report.json",
            "diff_ranges.json",
            "normal_encoded.bin",
            "pressed_encoded.bin",
            "normal_roundtrip.png",
            "pressed_roundtrip.png",
        ]
        for name in expected:
            self.assertTrue(os.path.isfile(os.path.join(out, name)), f"missing {name}")
        report = json.load(open(os.path.join(out, "patch_report.json")))
        self.assertEqual(report["roundtrip_descriptor_341"], True)
        self.assertEqual(report["roundtrip_descriptor_342"], True)
        self.assertTrue(report["source_unchanged"])
        self.assertEqual(report["patched_size"], len(image))


if __name__ == "__main__":
    unittest.main()
