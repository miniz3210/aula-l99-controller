"""Unit tests for Companion opt-in configuration loader.

Uses temporary local files only. No network access, no Companion connection,
no hardware access.
"""

import json
import math
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.companion_optin_config import (
    CompanionOptInConfig,
    CompanionOptInConfigError,
    load,
)


def _write_tmp(content: str) -> str:
    """Write content to a temporary JSON file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".json", prefix="companion_optin_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TestCompanionOptInConfig(unittest.TestCase):
    """Tests for CompanionOptInConfig loading and validation."""

    def _load(self, content: str) -> CompanionOptInConfig:
        path = _write_tmp(content)
        self.addCleanup(os.remove, path)
        return load(path)

    # ----- Missing / default config -----

    def test_missing_config(self):
        """Missing config path returns disabled default config."""
        config = load(None)
        self.assertFalse(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)
        self.assertIsNone(config.mapping_file)

    def test_nonexistent_file(self):
        """Nonexistent file returns disabled default config."""
        config = load(os.path.join(tempfile.gettempdir(), "nonexistent_companion_xyz.json"))
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    def test_empty_object(self):
        """Empty JSON object returns disabled default config."""
        config = self._load(json.dumps({}))
        self.assertFalse(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)
        self.assertIsNone(config.mapping_file)

    def test_disabled_config(self):
        """Explicit disabled config is accepted."""
        config = self._load(
            json.dumps({"version": 1, "companion": {"enabled": False}})
        )
        self.assertFalse(config.enabled)

    # ----- Explicit enabled config -----

    def test_explicit_enabled_config(self):
        """Valid enabled config with mapping file is accepted."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config = self._load(
            json.dumps(
                {
                    "version": 1,
                    "companion": {
                        "enabled": True,
                        "host": "127.0.0.1",
                        "port": 8000,
                        "timeout": 5.0,
                        "mapping_file": mapping_path,
                    },
                }
            )
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)
        self.assertEqual(config.mapping_file, mapping_path)

    # ----- Default values -----

    def test_default_values_from_explicit_fields(self):
        """Only enabled is set; other fields use defaults."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config = self._load(
            json.dumps(
                {"version": 1, "companion": {"enabled": True, "mapping_file": mapping_path}}
            )
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.timeout, 5.0)
        self.assertEqual(config.mapping_file, mapping_path)

    # ----- Invalid host -----

    def test_invalid_host_rejected(self):
        """Non-numeric host is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "host": "not-an-ip",
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("Invalid host address", str(ctx.exception))

    def test_non_loopback_host_rejected(self):
        """Non-loopback host is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "host": "192.168.1.1",
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("Non-loopback host rejected", str(ctx.exception))

    def test_localhost_rejected(self):
        """localhost hostname is rejected (not a numeric loopback IP)."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "host": "localhost",
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("Invalid host address", str(ctx.exception))

    # ----- Invalid port -----

    def test_invalid_port_zero(self):
        """Port 0 is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "port": 0,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be 1-65535", str(ctx.exception))

    def test_invalid_port_negative(self):
        """Negative port is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "port": -1,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be 1-65535", str(ctx.exception))

    def test_invalid_port_too_large(self):
        """Port > 65535 is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "port": 65536,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be 1-65535", str(ctx.exception))

    def test_boolean_port_rejected(self):
        """Boolean port is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "port": True,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be an integer", str(ctx.exception))

    # ----- Invalid timeout -----

    def test_invalid_timeout_zero(self):
        """Zero timeout is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "timeout": 0,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be positive", str(ctx.exception))

    def test_invalid_timeout_negative(self):
        """Negative timeout is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "timeout": -1.0,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be positive", str(ctx.exception))

    def test_invalid_timeout_infinite(self):
        """Infinite timeout is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "timeout": math.inf,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be finite", str(ctx.exception))

    def test_boolean_timeout_rejected(self):
        """Boolean timeout is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "timeout": True,
                            "mapping_file": "mapping.json",
                        },
                    }
                )
            )
        self.assertIn("must be a number", str(ctx.exception))

    # ----- Missing mapping file -----

    def test_missing_mapping_file_when_enabled(self):
        """Enabled config without mapping_file is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {"enabled": True},
                    }
                )
            )
        self.assertIn("mapping_file", str(ctx.exception))

    def test_mapping_file_none_when_enabled(self):
        """Explicit null mapping_file when enabled is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {"enabled": True, "mapping_file": None},
                    }
                )
            )
        self.assertIn("mapping_file", str(ctx.exception))

    # ----- Invalid mapping path -----

    def test_empty_mapping_path_rejected(self):
        """Empty mapping_file string is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "mapping_file": "",
                        },
                    }
                )
            )
        self.assertIn("mapping_file must not be empty", str(ctx.exception))

    def test_null_bytes_in_mapping_path_rejected(self):
        """Null bytes in mapping_file are rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "mapping_file": "mapping\x00.json",
                        },
                    }
                )
            )
        self.assertIn("null bytes", str(ctx.exception))

    # ----- Unknown fields -----

    def test_unknown_top_level_field(self):
        """Unknown top-level field is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "unknown_field": "value",
                    }
                )
            )
        self.assertIn("Unknown top-level fields", str(ctx.exception))

    def test_unknown_companion_field(self):
        """Unknown companion field is rejected."""
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            self._load(
                json.dumps(
                    {
                        "version": 1,
                        "companion": {
                            "enabled": True,
                            "mapping_file": "mapping.json",
                            "unknown_field": "value",
                        },
                    }
                )
            )
        self.assertIn("Unknown companion fields", str(ctx.exception))

    # ----- Unsupported version -----

    def test_unsupported_version(self):
        """Unsupported version is rejected."""
        for version in (0, 2, "1"):
            with self.subTest(version=version):
                with self.assertRaises(CompanionOptInConfigError) as ctx:
                    self._load(
                        json.dumps(
                            {
                                "version": version,
                                "companion": {
                                    "enabled": True,
                                    "mapping_file": "mapping.json",
                                },
                            }
                        )
                    )
                msg = str(ctx.exception)
                if isinstance(version, str):
                    self.assertIn("must be an integer", msg)
                else:
                    self.assertIn("Unsupported version", msg)

    # ----- Duplicate JSON keys -----

    def test_duplicate_json_keys(self):
        """Duplicate JSON keys are rejected."""
        path = _write_tmp(
            '{"version": 1, "version": 1, "companion": {"enabled": true, "mapping_file": "mapping.json"}}'
        )
        self.addCleanup(os.remove, path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            load(path)
        self.assertIn("Duplicate JSON key", str(ctx.exception))

    # ----- Malformed JSON -----

    def test_malformed_json(self):
        """Malformed JSON is rejected."""
        path = _write_tmp("{not valid json")
        self.addCleanup(os.remove, path)
        with self.assertRaises(CompanionOptInConfigError) as ctx:
            load(path)
        self.assertIn("Malformed JSON", str(ctx.exception))

    # ----- Immutability -----

    def test_immutability(self):
        """Config instance is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError

        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config = self._load(
            json.dumps(
                {
                    "version": 1,
                    "companion": {
                        "enabled": True,
                        "mapping_file": mapping_path,
                    },
                }
            )
        )
        with self.assertRaises(FrozenInstanceError):
            config.enabled = False  # type: ignore[assignment]
        with self.assertRaises(FrozenInstanceError):
            config.port = 8080  # type: ignore[assignment]

    # ----- No network access / no automatic activation -----

    def test_no_network_access(self):
        """Loading config performs no network operations (pure file I/O)."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config = self._load(
            json.dumps(
                {
                    "version": 1,
                    "companion": {
                        "enabled": True,
                        "host": "127.0.0.1",
                        "port": 8000,
                        "timeout": 5.0,
                        "mapping_file": mapping_path,
                    },
                }
            )
        )
        self.assertTrue(config.enabled)

    def test_no_automatic_activation(self):
        """Missing companion section means disabled, not activated."""
        config = self._load(json.dumps({"version": 1}))
        self.assertFalse(config.enabled)
        self.assertIsNone(config.mapping_file)

    def test_disabled_with_mapping_file(self):
        """Disabled config may include mapping_file without activating."""
        mapping_path = _write_tmp("{}")
        self.addCleanup(os.remove, mapping_path)
        config = self._load(
            json.dumps(
                {
                    "version": 1,
                    "companion": {
                        "enabled": False,
                        "mapping_file": mapping_path,
                    },
                }
            )
        )
        self.assertFalse(config.enabled)
        self.assertEqual(config.mapping_file, mapping_path)


if __name__ == "__main__":
    unittest.main()
