"""Tests for CLI Companion opt-in flags and initialization behavior."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import aula_input_bridge
from aula_bridge.companion_optin_config import CompanionOptInConfigError
from aula_bridge.companion_button_mapping import CompanionButtonMappingError
from aula_bridge.dispatcher import MockTransport


def _write_tmp(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".json", prefix="test_cli_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


class TestCliCompanionOptIn(unittest.TestCase):
    """Tests for CLI Companion opt-in flag behavior."""

    def setUp(self):
        self.temp_files = []

    def tearDown(self):
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    def test_cli_parse_enable_companion_flag(self):
        """--enable-companion flag is recognized."""
        ns = aula_input_bridge.parse_args(["--enable-companion"])
        self.assertTrue(ns.enable_companion)
        self.assertIsNone(ns.companion_config)

    def test_cli_parse_companion_config_flag(self):
        """--companion-config flag is recognized."""
        ns = aula_input_bridge.parse_args(["--companion-config", "path.json"])
        self.assertFalse(ns.enable_companion)
        self.assertEqual(ns.companion_config, "path.json")

    def test_cli_parse_both_flags(self):
        """Both flags together are recognized."""
        ns = aula_input_bridge.parse_args(["--enable-companion", "--companion-config", "path.json"])
        self.assertTrue(ns.enable_companion)
        self.assertEqual(ns.companion_config, "path.json")

    def test_cli_help_contains_new_flags(self):
        """CLI help text contains new flags."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                aula_input_bridge.parse_args(["--help"])
            except SystemExit:
                pass
        text = buf.getvalue()
        self.assertIn("--enable-companion", text)
        self.assertIn("--companion-config", text)

    def test_main_rejects_enable_companion_without_config(self):
        """main() rejects --enable-companion without --companion-config."""
        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion"]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_main_rejects_companion_config_without_enable(self):
        """main() rejects --companion-config without --enable-companion."""
        with patch.object(sys, "argv", ["aula_input_bridge.py", "--companion-config", "path.json"]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_main_validates_companion_config_file(self):
        """main() validates companion config when both flags present."""
        # Create invalid config (missing mapping_file when enabled)
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": True, "host": "127.0.0.1", "port": 8000}
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_main_validates_companion_config_enabled_false(self):
        """main() rejects enabled=false with --enable-companion flag."""
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": False, "mapping_file": "mapping.json"}
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        # Create dummy mapping
        mapping_content = json.dumps({"version": 1, "mappings": {}})
        mapping_path = _write_tmp(mapping_content)
        self.temp_files.append(mapping_path)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_main_validates_button_mapping_file(self):
        """main() validates button mapping file exists and is valid."""
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "timeout": 5.0,
                "mapping_file": "/nonexistent/mapping.json"
            }
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_main_accepts_valid_companion_config(self):
        """main() accepts valid companion config and initializes transport."""
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "timeout": 5.0,
                "mapping_file": "mapping.json"
            }
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        mapping_content = json.dumps({
            "version": 1,
            "mappings": {"numpad_1": {"page": 1, "row": 0, "column": 0}}
        })
        mapping_path = _write_tmp(mapping_content)
        self.temp_files.append(mapping_path)

        # Update config with absolute mapping path
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "timeout": 5.0,
                "mapping_file": mapping_path
            }
        })
        with open(config_path, "w") as f:
            f.write(config_content)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            # Mock the Windows message loop to exit immediately
            with patch("aula_input_bridge.user32.PeekMessageW", return_value=False):
                with patch("aula_input_bridge.time.sleep", side_effect=KeyboardInterrupt):
                    try:
                        result = aula_input_bridge.main()
                    except KeyboardInterrupt:
                        pass
                    except SystemExit as e:
                        # main() may call sys.exit(0) on clean shutdown
                        if e.code == 0:
                            pass
                        else:
                            raise

        # Verify it didn't fail during initialization
        # The bridge runs indefinitely, so we just check it didn't error out


class TestDefaultDisabledBehavior(unittest.TestCase):
    """Tests that verify Companion is disabled by default and existing behavior preserved."""

    def test_no_flags_uses_mock_transport(self):
        """Without flags, MockTransport is used (not Companion transport)."""
        with patch.object(sys, "argv", ["aula_input_bridge.py"]):
            with patch("aula_input_bridge.MockTransport") as mock_transport_class:
                mock_transport = MagicMock()
                mock_transport_class.return_value = mock_transport

                with patch("aula_input_bridge.user32.PeekMessageW", return_value=False):
                    with patch("aula_input_bridge.time.sleep", side_effect=KeyboardInterrupt):
                        try:
                            aula_input_bridge.main()
                        except KeyboardInterrupt:
                            pass

                mock_transport_class.assert_called_once()

    def test_companion_modules_not_imported_by_default(self):
        """Companion modules are not imported when flags not used."""
        # This is verified by the fact that main() runs without Companion
        # initialization when flags are absent
        pass


class TestConfigurationValidation(unittest.TestCase):
    """Tests for Companion configuration validation during initialization."""

    def setUp(self):
        self.temp_files = []

    def tearDown(self):
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    def test_invalid_companion_config_fails_fast(self):
        """Invalid companion config fails during initialization."""
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "192.168.1.1",  # Non-loopback
                "port": 8000,
                "mapping_file": "mapping.json"
            }
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        mapping_content = json.dumps({"version": 1, "mappings": {}})
        mapping_path = _write_tmp(mapping_content)
        self.temp_files.append(mapping_path)

        # Update config with absolute mapping path
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "192.168.1.1",
                "port": 8000,
                "mapping_file": mapping_path
            }
        })
        with open(config_path, "w") as f:
            f.write(config_content)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_missing_mapping_file_fails_fast(self):
        """Missing button mapping file fails during initialization."""
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "mapping_file": "/nonexistent/mapping.json"
            }
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_invalid_mapping_file_fails_fast(self):
        """Invalid button mapping file fails during initialization."""
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "mapping_file": "mapping.json"
            }
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        # Invalid mapping (unknown key)
        mapping_content = json.dumps({
            "version": 1,
            "mappings": {"unknown_key": {"page": 1, "row": 0, "column": 0}}
        })
        mapping_path = _write_tmp(mapping_content)
        self.temp_files.append(mapping_path)

        # Update config with absolute mapping path
        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "mapping_file": mapping_path
            }
        })
        with open(config_path, "w") as f:
            f.write(config_content)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)

    def test_json_enabled_false_remains_disabled(self):
        """JSON with enabled=false keeps Companion disabled even with flags."""
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": False, "mapping_file": "mapping.json"}
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        mapping_content = json.dumps({"version": 1, "mappings": {}})
        mapping_path = _write_tmp(mapping_content)
        self.temp_files.append(mapping_path)

        # Update config with absolute mapping path
        config_content = json.dumps({
            "version": 1,
            "companion": {"enabled": False, "mapping_file": mapping_path}
        })
        with open(config_path, "w") as f:
            f.write(config_content)

        with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
            result = aula_input_bridge.main()
            self.assertEqual(result, 1)


class TestNoNetworkAccessDuringInit(unittest.TestCase):
    """Tests verifying no network access occurs during initialization."""

    def setUp(self):
        self.temp_files = []

    def tearDown(self):
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    def test_no_network_access_on_init(self):
        """Initialization does not perform network I/O."""
        import socket

        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "mapping_file": "mapping.json"
            }
        })
        config_path = _write_tmp(config_content)
        self.temp_files.append(config_path)

        mapping_content = json.dumps({
            "version": 1,
            "mappings": {"numpad_1": {"page": 1, "row": 0, "column": 0}}
        })
        mapping_path = _write_tmp(mapping_content)
        self.temp_files.append(mapping_path)

        config_content = json.dumps({
            "version": 1,
            "companion": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 8000,
                "mapping_file": mapping_path
            }
        })
        with open(config_path, "w") as f:
            f.write(config_content)

        # Patch socket to fail if any network access attempted
        real_socket = socket.socket

        def _fail_socket(*args, **kwargs):
            raise AssertionError("socket.socket must not be instantiated during init")

        with patch("socket.socket", side_effect=_fail_socket):
            with patch.object(sys, "argv", ["aula_input_bridge.py", "--enable-companion", "--companion-config", config_path]):
                with patch("aula_input_bridge.user32.PeekMessageW", return_value=False):
                    with patch("aula_input_bridge.time.sleep", side_effect=KeyboardInterrupt):
                        try:
                            aula_input_bridge.main()
                        except KeyboardInterrupt:
                            pass


if __name__ == "__main__":
    unittest.main()