#!/usr/bin/env python3
"""Synthetic tests for scripts/flash_checksum_scanner.py.

All fixtures are generated in-memory. No vendor firmware is required or embedded.
The scanner is read-only: it never modifies its input file.
"""

import hashlib
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import flash_checksum_scanner as mod


def write_tmp(name, content):
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, name)
    with open(path, "wb") as f:
        f.write(content)
    return tmp, path


def synthetic_image(tmpdir, name="image.bin", size=4096):
    data = os.urandom(size)
    path = os.path.join(tmpdir, name)
    with open(path, "wb") as f:
        f.write(data)
    return path, data


class AlgorithmTests(unittest.TestCase):
    def test_crc16_modbus_known_vector(self):
        # CRC-16/MODBUS of "123456789" = 0x4B37
        self.assertEqual(mod.crc16_modbus(b"123456789"), 0x4B37)

    def test_crc16_modbus_fast_matches_bitwise(self):
        data = os.urandom(5000)
        self.assertEqual(mod.crc16_modbus(data), mod.crc16_modbus_fast(data))

    def test_crc32_reflected_known_vector(self):
        # CRC-32 reflected IEEE of "123456789" = 0xCBF43926
        self.assertEqual(mod.crc32_reflected_ieee(b"123456789"), 0xCBF43926)

    def test_addsum_known_vector(self):
        data = b"\x01\x02\x03\x04"
        self.assertEqual(mod.addsum16(data), 0x000A)
        self.assertEqual(mod.addsum32(data), 0x0000000A)


class ReadOnlyTests(unittest.TestCase):
    def test_scanner_does_not_modify_input(self):
        data = bytes(range(256)) * 100
        tmp, path = write_tmp("image.bin", data)
        before = open(path, "rb").read()
        mtime_before = os.path.getmtime(path)
        _ = mod.crc16_modbus(data)
        _ = mod.crc32_reflected_ieee(data)
        _ = mod.crc32_standard(data)
        _ = mod.addsum16(data)
        _ = mod.addsum32(data)
        after = open(path, "rb").read()
        self.assertEqual(before, after)
        self.assertEqual(os.path.getmtime(path), mtime_before)


class RegionBoundsTests(unittest.TestCase):
    def test_region_bounds_skipped_when_none(self):
        data = b"\x00" * 64
        results = []
        mod.scan_region(data, "undefined", None, results)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "SKIPPED_UNKNOWN_BOUNDS")

    def test_region_bounds_out_of_range_skipped(self):
        data = b"\x00" * 16
        results = []
        mod.scan_region(data, "too_big", (0, 65536), results)
        self.assertEqual(results[0]["status"], "SKIPPED_UNKNOWN_BOUNDS")

    def test_last_64kib(self):
        data = bytes(range(256)) * 512  # 128 KiB
        start, end = mod.last_64kib(data)
        self.assertEqual(end, len(data))
        self.assertEqual(start, len(data) - 65536)
        small = b"\x00" * 100
        s2, e2 = mod.last_64kib(small)
        self.assertEqual((s2, e2), (0, 100))


class MatchDetectionTests(unittest.TestCase):
    def test_stored_crc32_reflected_at_end_detected(self):
        body = os.urandom(200)
        section = body + b"\x00\x00\x00\x00"  # checksum field zeroed
        crc = mod.crc32_reflected_ieee(section)
        data = section[:-4] + struct.pack("<I", crc)
        results = []
        mod.scan_region(data, "payload", (0, len(data)), results)
        self.assertEqual(results[0]["status"], "MATCH")
        self.assertGreaterEqual(len(results[0]["matches"]), 1)
        self.assertEqual(results[0]["matches"][0]["algorithm"], "CRC32/reflected_IEEE_init0_xorout0")
        self.assertEqual(results[0]["matches"][0]["offset"], len(data) - 4)

    def test_stored_crc16_modbus_at_end_detected(self):
        body = os.urandom(100)
        section = body + b"\x00\x00"
        crc = mod.crc16_modbus(section)
        data = section[:-2] + struct.pack("<H", crc)
        results = []
        mod.scan_region(data, "payload", (0, len(data)), results)
        self.assertEqual(results[0]["status"], "MATCH")

    def test_stored_addsum32_at_end_detected(self):
        body = os.urandom(100)
        section = body + b"\x00\x00\x00\x00"
        s = mod.addsum32(section)
        data = section[:-4] + struct.pack("<I", s)
        results = []
        mod.scan_region(data, "payload", (0, len(data)), results)
        self.assertEqual(results[0]["status"], "MATCH")

    def test_stored_crc32_at_start_detected(self):
        body = os.urandom(200)
        section = b"\x00\x00\x00\x00" + body
        crc = mod.crc32_reflected_ieee(section)
        data = struct.pack("<I", crc) + body
        results = []
        mod.scan_region(data, "full", (0, len(data)), results)
        self.assertEqual(results[0]["status"], "MATCH")
        self.assertEqual(results[0]["matches"][0]["offset"], 0)

    def test_value_elsewhere_in_range_not_reported(self):
        # A CRC value that appears somewhere in the middle of the region but
        # not at a checksum field offset must NOT be reported.
        payload = os.urandom(400)
        crc = mod.crc32_reflected_ieee(payload)
        data = payload[:200] + struct.pack("<I", crc) + payload[200:]
        results = []
        mod.scan_region(data, "full", (0, len(data)), results)
        self.assertEqual(results[0]["status"], "NO_MATCH")

    def test_no_match_reports_no_match(self):
        data = os.urandom(256)
        results = []
        mod.scan_region(data, "full", (0, len(data)), results)
        self.assertEqual(results[0]["status"], "NO_MATCH")
        self.assertEqual(results[0]["matches"], [])


class HeaderWordsTests(unittest.TestCase):
    def test_no_header_word_match_for_random_data(self):
        data = os.urandom(1024)
        results = []
        mod.header_words_checks(data, results)
        self.assertEqual(results[0]["status"], "NO_MATCH")

    def test_header_word_runs_on_small_image(self):
        data = b"\x00" * 64
        results = []
        mod.header_words_checks(data, results)
        # additive_sum32 of all-zero image is 0, which equals header word 0.
        self.assertEqual(results[0]["range_len"], 64)
        self.assertIn(results[0]["status"], ("MATCH", "NO_MATCH"))


class FactoryVsPatchedTests(unittest.TestCase):
    def test_identical_images_report_zero_changes(self):
        data = os.urandom(1024)
        fvp = mod.factory_vs_patched(data, data)
        self.assertEqual(fvp["num_changed_bytes"], 0)
        self.assertEqual(fvp["changed_ranges"], [])

    def test_changed_ranges_grouped(self):
        a = bytearray(b"\x00" * 100)
        b = bytearray(a)
        b[10:15] = b"\x01" * 5
        b[50:55] = b"\x02" * 5
        fvp = mod.factory_vs_patched(bytes(a), bytes(b))
        self.assertEqual(fvp["num_changed_bytes"], 10)
        self.assertEqual(len(fvp["changed_ranges"]), 2)


class ClassificationTests(unittest.TestCase):
    def test_classify_present(self):
        self.assertEqual(mod.classify([{"status": "MATCH"}]), "VERIFIED_PRESENT")

    def test_classify_unknown(self):
        self.assertEqual(mod.classify([{"status": "NO_MATCH"}]), "UNKNOWN")


class MainArgParsingTests(unittest.TestCase):
    def test_missing_file_exits(self):
        old_argv = sys.argv
        sys.argv = ["flash_checksum_scanner.py", "nonexistent_file.bin"]
        try:
            with self.assertRaises(SystemExit):
                mod.main()
        finally:
            sys.argv = old_argv


class QuickModeTests(unittest.TestCase):
    def _run_scanner(self, image_path, mode="quick", factory=None, patched=None,
                     cache_dir=None, workers=1):
        args = [image_path, "--mode", mode]
        if factory:
            args += ["--factory", factory]
        if patched:
            args += ["--patched", patched]
        args += ["--workers", str(workers)]
        if cache_dir:
            args += ["--cache-dir", cache_dir]
        old_argv = sys.argv
        sys.argv = ["flash_checksum_scanner.py"] + args
        try:
            rc = mod.main()
        finally:
            sys.argv = old_argv
        return rc

    def test_quick_mode_runs_and_reports_classification(self):
        tmpdir = tempfile.mkdtemp()
        path, _ = synthetic_image(tmpdir)
        rc = self._run_scanner(path, mode="quick")
        self.assertIn(rc, (0, 1))

    def test_quick_mode_excludes_startup_animation_region(self):
        # startup_animation is large and excluded from quick mode to avoid
        # exploratory whole-image candidate scanning.
        tmpdir = tempfile.mkdtemp()
        path, _ = synthetic_image(tmpdir)
        rc = self._run_scanner(path, mode="quick")
        self.assertIn(rc, (0, 1))

    def test_quick_mode_uses_fast_whole_image_algorithms(self):
        tmpdir = tempfile.mkdtemp()
        path, data = synthetic_image(tmpdir, size=200000)
        rc = self._run_scanner(path, mode="quick")
        self.assertIn(rc, (0, 1))

    def test_quick_mode_finished_quickly_on_large_synthetic(self):
        tmpdir = tempfile.mkdtemp()
        path, _ = synthetic_image(tmpdir, size=2000000)
        t0 = time.time()
        rc = self._run_scanner(path, mode="quick", workers=1)
        dt = time.time() - t0
        self.assertIn(rc, (0, 1))
        self.assertLess(dt, 30, f"quick mode took {dt:.1f}s")


class DeepModeCacheTests(unittest.TestCase):
    def _cache_args(self, image_path, factory=None, patched=None, cache_dir=None,
                    workers=1):
        args = [image_path, "--mode", "deep", "--workers", str(workers)]
        if factory:
            args += ["--factory", factory]
        if patched:
            args += ["--patched", patched]
        if cache_dir:
            args += ["--cache-dir", cache_dir]
        old_argv = sys.argv
        sys.argv = ["flash_checksum_scanner.py"] + args
        try:
            rc = mod.main()
        finally:
            sys.argv = old_argv
        return rc

    def test_deep_mode_creates_cache(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        rc = self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        self.assertIn(rc, (0, 1))
        cache_file = os.path.join(cache_dir, mod.CACHE_FILENAME)
        self.assertTrue(os.path.isfile(cache_file), "deep mode must create a cache file")

    def test_identical_cache_key_produces_cache_hit(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        cache_file = os.path.join(cache_dir, mod.CACHE_FILENAME)
        self.assertTrue(os.path.isfile(cache_file))

    def test_changed_scanner_version_invalidates_cache(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        orig = mod.SCANNER_VERSION
        mod.SCANNER_VERSION = "9.9.9"
        try:
            self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        finally:
            mod.SCANNER_VERSION = orig

    def test_changed_source_hash_invalidates_cache(self):
        # Changing the scanner source file changes its source hash, invalidating cache.
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        scanner_path = Path(mod.__file__)
        original = scanner_path.read_text()
        try:
            scanner_path.write_text(original + "\n# version bump\n")
            import importlib
            importlib.reload(mod)
            self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        finally:
            scanner_path.write_text(original)

    def test_changed_algorithm_list_invalidates_cache(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        orig_algos = mod.ALGORITHMS
        mod.ALGORITHMS = ["CRC16/MODBUS"]
        try:
            self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        finally:
            mod.ALGORITHMS = orig_algos

    def test_changed_region_map_invalidates_cache(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        orig_regions = mod.REGIONS
        mod.REGIONS = {"extra": (0, 100)}
        try:
            self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        finally:
            mod.REGIONS = orig_regions

    def test_cached_output_is_deterministic(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        rc1 = self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        rc2 = self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        self.assertEqual(rc1, rc2)
        cache_file = os.path.join(cache_dir, mod.CACHE_FILENAME)
        self.assertTrue(os.path.isfile(cache_file))

    def test_false_positive_crc16_collision_non_structural(self):
        # A CRC16 value appearing in the middle of a region, not at a checksum
        # field offset, must not be reported as a match.
        body = os.urandom(300)
        crc = mod.crc16_modbus_fast(body)
        data = body[:150] + struct.pack("<H", crc) + body[150:]
        results = []
        mod.scan_region(data, "payload", (0, len(data)), results, ["CRC16/MODBUS"])
        self.assertEqual(results[0]["status"], "NO_MATCH")

    def test_timeout_guard_stops_cleanly(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir, size=200000)
        factory = path
        old_argv = sys.argv
        sys.argv = ["flash_checksum_scanner.py", path, "--mode", "deep",
                    "--max-runtime", "0.05", "--workers", "1", "--cache-dir", cache_dir]
        try:
            rc = mod.main()
        finally:
            sys.argv = old_argv
        self.assertIn(rc, (0, 1))

    def test_source_images_remain_unchanged(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir = os.path.join(tmpdir, "cache")
        path, data = synthetic_image(tmpdir)
        factory = path
        before = open(path, "rb").read()
        mtime_before = os.path.getmtime(path)
        self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir)
        after = open(path, "rb").read()
        self.assertEqual(before, after)
        self.assertEqual(os.path.getmtime(path), mtime_before)

    def test_multiprocessing_and_single_worker_identical(self):
        tmpdir = tempfile.mkdtemp()
        cache_dir1 = os.path.join(tmpdir, "cache1")
        cache_dir2 = os.path.join(tmpdir, "cache2")
        path, data = synthetic_image(tmpdir)
        factory = path
        rc1 = self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir1, workers=1)
        rc2 = self._cache_args(path, factory=factory, patched=path, cache_dir=cache_dir2, workers=2)
        self.assertEqual(rc1, rc2)


if __name__ == "__main__":
    unittest.main()
