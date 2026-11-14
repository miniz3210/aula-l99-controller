"""Unit tests for Companion button mapping configuration loader."""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.action_mapping import NUM_PAD_KEYS
from aula_bridge.companion_button_mapping import (
    ButtonLocation,
    CompanionButtonMappingError,
    load_companion_button_mapping,
)

ALL_KEYS = list(NUM_PAD_KEYS)


def _write_tmp(content: str) -> str:
    """Write content to a temporary JSON file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="mapping_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TestCompanionButtonMapping(unittest.TestCase):
    """Tests for load_companion_button_mapping."""

    def _load(self, content: str):
        path = _write_tmp(content)
        self.addCleanup(os.remove, path)
        return load_companion_button_mapping(path)

    def test_valid_configuration(self):
        """Valid configuration loads into an immutable mapping."""
        mapping = self._load(
            json.dumps(
                {
                    "version": 1,
                    "mappings": {
                        "numpad_1": {"page": 1, "row": 0, "column": 0},
                        "numpad_2": {"page": 1, "row": 0, "column": 1},
                    },
                }
            )
        )
        self.assertEqual(mapping["numpad_1"], ButtonLocation(page=1, row=0, column=0))
        self.assertEqual(mapping["numpad_2"], ButtonLocation(page=1, row=0, column=1))
        self.assertEqual(len(mapping), 2)

    def test_empty_mapping(self):
        """Empty mappings object is valid."""
        mapping = self._load(json.dumps({"version": 1, "mappings": {}}))
        self.assertEqual(len(mapping), 0)
        self.assertEqual(dict(mapping), {})

    def test_partial_mapping(self):
        """Partial mapping leaves unmapped keys absent (no defaults)."""
        mapping = self._load(
            json.dumps({"version": 1, "mappings": {"numpad_1": {"page": 3, "row": 2, "column": 1}}})
        )
        self.assertEqual(len(mapping), 1)
        self.assertIn("numpad_1", mapping)
        self.assertNotIn("numpad_2", mapping)
        self.assertNotIn("numpad_0", mapping)

    def test_all_supported_logical_keys(self):
        """All 17 supported logical keys may be mapped."""
        mappings = {
            key: {"page": 1, "row": i, "column": 0} for i, key in enumerate(ALL_KEYS)
        }
        mapping = self._load(
            json.dumps({"version": 1, "mappings": mappings})
        )
        self.assertEqual(len(mapping), len(ALL_KEYS))
        for key in ALL_KEYS:
            self.assertIn(key, mapping)

    def test_unknown_logical_key(self):
        """Unknown logical key is rejected."""
        with self.assertRaises(CompanionButtonMappingError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "mappings": {"numpad_99": {"page": 1, "row": 0, "column": 0}},
                    }
                )
            )
        self.assertIn("Unknown logical key", str(ctx.exception))

    def test_missing_fields(self):
        """Missing location fields are rejected."""
        for missing_field in ("page", "row", "column"):
            with self.subTest(field=missing_field):
                fields = {"page": 1, "row": 0, "column": 0}
                del fields[missing_field]
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(
                        json.dumps(
                            {
                                "version": 1,
                                "mappings": {"numpad_1": fields},
                            }
                        )
                    )
                self.assertIn("missing fields", str(ctx.exception))

    def test_extra_fields(self):
        """Extra/unknown location fields are rejected."""
        with self.assertRaises(CompanionButtonMappingError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "mappings": {
                            "numpad_1": {"page": 1, "row": 0, "column": 0, "x": 5}
                        },
                    }
                )
            )
        self.assertIn("unknown fields", str(ctx.exception))

    def test_negative_values(self):
        """Negative page/row/column are rejected."""
        cases = [
            ({"page": 0, "row": 0, "column": 0}, "page"),
            ({"page": 1, "row": -1, "column": 0}, "row"),
            ({"page": 1, "row": 0, "column": -1}, "column"),
        ]
        for fields, field_name in cases:
            with self.subTest(field=field_name):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(
                        json.dumps(
                            {"version": 1, "mappings": {"numpad_1": fields}}
                        )
                    )
                self.assertIn("must be >=", str(ctx.exception))

    def test_boolean_values(self):
        """Boolean numeric values are rejected."""
        cases = [
            ({"page": True, "row": 0, "column": 0}, "page"),
            ({"page": 1, "row": False, "column": 0}, "row"),
            ({"page": 1, "row": 0, "column": True}, "column"),
        ]
        for fields, field_name in cases:
            with self.subTest(field=field_name):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(
                        json.dumps(
                            {"version": 1, "mappings": {"numpad_1": fields}}
                        )
                    )
                self.assertIn("must be an integer", str(ctx.exception))

    def test_float_values(self):
        """Float values are rejected."""
        cases = [
            ({"page": 1.0, "row": 0, "column": 0}, "page"),
            ({"page": 1, "row": 0.5, "column": 0}, "row"),
            ({"page": 1, "row": 0, "column": 0.0}, "column"),
        ]
        for fields, field_name in cases:
            with self.subTest(field=field_name):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(
                        json.dumps(
                            {"version": 1, "mappings": {"numpad_1": fields}}
                        )
                    )
                self.assertIn("must be an integer", str(ctx.exception))

    def test_string_numeric_values(self):
        """String numeric values are rejected."""
        cases = [
            ({"page": "1", "row": 0, "column": 0}, "page"),
            ({"page": 1, "row": "0", "column": 0}, "row"),
            ({"page": 1, "row": 0, "column": "0"}, "column"),
        ]
        for fields, field_name in cases:
            with self.subTest(field=field_name):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(
                        json.dumps(
                            {"version": 1, "mappings": {"numpad_1": fields}}
                        )
                    )
                self.assertIn("must be an integer", str(ctx.exception))

    def test_malformed_json(self):
        """Malformed JSON is rejected."""
        path = _write_tmp("{not valid json")
        self.addCleanup(os.remove, path)
        with self.assertRaises(CompanionButtonMappingError) as ctx:
            load_companion_button_mapping(path)
        self.assertIn("Malformed JSON", str(ctx.exception))

    def test_duplicate_json_keys(self):
        """Duplicate JSON keys are rejected."""
        path = _write_tmp(
            '{"version": 1, "mappings": {"numpad_1": {"page": 1, "row": 0, "column": 0}, "numpad_1": {"page": 1, "row": 0, "column": 1}}}'
        )
        self.addCleanup(os.remove, path)
        with self.assertRaises(CompanionButtonMappingError) as ctx:
            load_companion_button_mapping(path)
        self.assertIn("Duplicate JSON key", str(ctx.exception))

    def test_unsupported_version(self):
        """Unsupported version is rejected."""
        for version in (0, 2, "1"):
            with self.subTest(version=version):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(
                        json.dumps(
                            {
                                "version": version,
                                "mappings": {"numpad_1": {"page": 1, "row": 0, "column": 0}},
                            }
                        )
                    )
                msg = str(ctx.exception)
                if isinstance(version, str):
                    self.assertIn("must be an integer", msg)
                else:
                    self.assertIn("Unsupported version", msg)

    def test_immutability(self):
        """Returned mapping is immutable."""
        mapping = self._load(
            json.dumps(
                {
                    "version": 1,
                    "mappings": {"numpad_1": {"page": 1, "row": 0, "column": 0}},
                }
            )
        )
        from types import MappingProxyType

        self.assertIsInstance(mapping, MappingProxyType)
        with self.assertRaises(TypeError):
            mapping["numpad_2"] = ButtonLocation(page=1, row=0, column=0)  # type: ignore[index]
        with self.assertRaises(AttributeError):
            mapping.clear()  # type: ignore[attr-defined]
        # ButtonLocation itself is immutable
        loc = ButtonLocation(page=1, row=0, column=0)
        with self.assertRaises(Exception):
            loc.page = 2  # type: ignore[assignment]

    def test_no_default_actions(self):
        """No automatic default button locations are invented."""
        mapping = self._load(json.dumps({"version": 1, "mappings": {}}))
        self.assertEqual(len(mapping), 0)
        for key in ALL_KEYS:
            self.assertNotIn(key, mapping)

    def test_missing_file(self):
        """Missing file raises a clear error."""
        with self.assertRaises(CompanionButtonMappingError):
            load_companion_button_mapping(os.path.join(tempfile.gettempdir(), "nonexistent_mapping_xyz.json"))

    def test_top_level_not_object(self):
        """Non-object top-level JSON is rejected."""
        for content in ("[1,2,3]", "42", "\"string\"", "true", "null"):
            with self.subTest(content=content):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(content)
                self.assertIn("Top-level JSON must be an object", str(ctx.exception))

    def test_mappings_not_object(self):
        """mappings must be an object."""
        for content in (
            json.dumps({"version": 1, "mappings": [1, 2]}),
            json.dumps({"version": 1, "mappings": "not an object"}),
            json.dumps({"version": 1, "mappings": 42}),
        ):
            with self.subTest(content=content):
                with self.assertRaises(CompanionButtonMappingError) as ctx:
                    self._load(content)
                self.assertIn("mappings must be an object", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
