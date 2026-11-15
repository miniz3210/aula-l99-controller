"""Startup failure injection tests for the Windows Bridge Companion integration.

Verifies that Companion startup failures fail fast, clean up resources, and make
no HTTP requests. Tests only; no production code changes. No real network, no
hardware access, no Windows message loop.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import aula_input_bridge
from aula_bridge.companion_http_transport import CompanionHttpTransportError, HttpResponse
from aula_bridge.dispatcher import MockTransport


class FakeProvider:
    """Stand-in for DryRunProvider that performs no disk I/O."""

    def __init__(self, log_file, log_dir="logs"):
        self.path = os.path.join(log_dir, log_file)
        self.emitted = []

    def emit(self, event):
        self.emitted.append(event)

    def flush(self):
        pass

    def close(self):
        pass


class FakeHttpSender:
    """Deterministic fake HTTP sender. Records calls, no real network."""

    def __init__(self):
        self.calls = []

    def send(self, method, url, timeout):
        self.calls.append((method, url, timeout))
        return HttpResponse(status_code=200, success=True)


class _ExitLoop(Exception):
    """Raised by fake time.sleep to break out of main()'s message loop."""


def _raise_exit(*args, **kwargs):
    raise _ExitLoop()


class _RecordingWorker:
    """Records worker instances and whether close() was called."""

    instances = []

    def __init__(self, transport, **kwargs):
        self.closed = False
        _RecordingWorker.instances.append(self)

    def close(self):
        self.closed = True

    @property
    def is_alive(self):
        return False


class TestCompanionStartupFailure(unittest.TestCase):
    """Focused startup failure injection tests."""

    def setUp(self):
        self.temp_files = []
        self.patches = []
        _RecordingWorker.instances = []
        # Avoid hardware access and log-file directory creation during init.
        self.patches.append(patch("aula_input_bridge.find_target_device", return_value=None))
        self.patches.append(patch("aula_input_bridge.DryRunProvider", FakeProvider))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        for path in self.temp_files:
            try:
                os.remove(path)
            except OSError:
                pass

    def _write_tmp(self, content, suffix=".json", prefix="startup_fail_"):
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        self.temp_files.append(path)
        return path

    def _valid_fixtures(self):
        mapping_path = self._write_tmp(
            json.dumps({"version": 1, "mappings": {"numpad_1": {"page": 1, "row": 0, "column": 0}}})
        )
        config_path = self._write_tmp(
            json.dumps({
                "version": 1,
                "companion": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 19876,
                    "timeout": 5.0,
                    "mapping_file": mapping_path,
                },
            })
        )
        return mapping_path, config_path

    def _mock_message_loop(self):
        new_patches = [
            patch("aula_input_bridge.user32.PeekMessageW", return_value=False),
            patch("aula_input_bridge.time.sleep", side_effect=_raise_exit),
        ]
        self.patches.extend(new_patches)
        for p in new_patches:
            p.start()

    # 1. Invalid CLI combination fails fast.
    def test_invalid_cli_combination_fails_fast(self):
        self.assertEqual(aula_input_bridge.main(["--enable-companion"]), 1)
        self.assertEqual(aula_input_bridge.main(["--companion-config", "any.json"]), 1)

    # 2. Missing Companion config fails fast.
    def test_missing_companion_config_fails_fast(self):
        result = aula_input_bridge.main(
            ["--enable-companion", "--companion-config", "/nonexistent/config.json"]
        )
        self.assertEqual(result, 1)

    # 3. Invalid JSON fails fast.
    def test_invalid_json_fails_fast(self):
        path = self._write_tmp("{not valid json")
        result = aula_input_bridge.main(["--enable-companion", "--companion-config", path])
        self.assertEqual(result, 1)

    # 4. Missing mapping fails fast.
    def test_missing_mapping_fails_fast(self):
        config_path = self._write_tmp(
            json.dumps({
                "version": 1,
                "companion": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 8000,
                    "mapping_file": "/nonexistent/mapping.json",
                },
            })
        )
        result = aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
        self.assertEqual(result, 1)

    # 5. Invalid mapping fails fast.
    def test_invalid_mapping_fails_fast(self):
        mapping_path = self._write_tmp(
            json.dumps({"version": 1, "mappings": {"unknown_key": {"page": 1, "row": 0, "column": 0}}})
        )
        config_path = self._write_tmp(
            json.dumps({
                "version": 1,
                "companion": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 8000,
                    "mapping_file": mapping_path,
                },
            })
        )
        result = aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
        self.assertEqual(result, 1)

    # 6. HTTP transport constructor failure.
    def test_http_transport_constructor_failure(self):
        _, config_path = self._valid_fixtures()
        with patch(
            "aula_bridge.companion_http_transport.CompanionHttpTransport",
            side_effect=CompanionHttpTransportError("transport init failed"),
        ):
            result = aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
        self.assertEqual(result, 1)

    # 7. Adapter constructor failure.
    def test_adapter_constructor_failure(self):
        _, config_path = self._valid_fixtures()
        with patch(
            "aula_bridge.companion_dispatch_adapter.CompanionDispatchAdapter",
            side_effect=CompanionHttpTransportError("adapter init failed"),
        ):
            result = aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
        self.assertEqual(result, 1)

    # 8. Worker constructor failure.
    def test_worker_constructor_failure(self):
        _, config_path = self._valid_fixtures()
        with patch(
            "aula_bridge.companion_dispatch_worker.CompanionDispatchWorker",
            side_effect=CompanionHttpTransportError("worker init failed"),
        ):
            result = aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
        self.assertEqual(result, 1)

    # 9. Dispatcher constructor failure.
    def test_dispatcher_constructor_failure(self):
        _, config_path = self._valid_fixtures()
        _RecordingWorker.instances = []
        with patch(
            "aula_bridge.companion_dispatch_worker.CompanionDispatchWorker", _RecordingWorker
        ):
            with patch(
                "aula_input_bridge.ActionDispatcher",
                side_effect=RuntimeError("dispatcher init failed"),
            ):
                with self.assertRaises(RuntimeError):
                    aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])

    # 10. No leaked worker after failed startup.
    def test_no_leaked_worker_after_failed_startup(self):
        _, config_path = self._valid_fixtures()
        _RecordingWorker.instances = []
        with patch(
            "aula_bridge.companion_dispatch_worker.CompanionDispatchWorker", _RecordingWorker
        ):
            with patch(
                "aula_input_bridge.ActionDispatcher",
                side_effect=RuntimeError("dispatcher init failed"),
            ):
                try:
                    aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
                except RuntimeError:
                    pass
        self.assertEqual(len(_RecordingWorker.instances), 1)
        for w in _RecordingWorker.instances:
            self.assertTrue(w.closed, "worker leaked after failed startup")

    # 11. No HTTP request during failed startup.
    def test_no_http_request_during_failed_startup(self):
        _, config_path = self._valid_fixtures()
        sender = FakeHttpSender()
        with patch(
            "aula_bridge.companion_http_sender.CompanionHttpSender", return_value=sender
        ):
            with patch(
                "aula_bridge.companion_http_transport.CompanionHttpTransport",
                side_effect=CompanionHttpTransportError("transport init failed"),
            ):
                result = aula_input_bridge.main(["--enable-companion", "--companion-config", config_path])
        self.assertEqual(result, 1)
        self.assertEqual(len(sender.calls), 0, "HTTP request made during failed startup")

    # 12. Default-disabled startup unchanged.
    def test_default_disabled_startup_unchanged(self):
        self._mock_message_loop()
        with patch("aula_input_bridge.ActionDispatcher") as mock_dispatcher:
            try:
                aula_input_bridge.main([])
            except _ExitLoop:
                pass
        transport_arg = mock_dispatcher.call_args.kwargs.get("transport")
        self.assertIsInstance(transport_arg, MockTransport)


if __name__ == "__main__":
    unittest.main()
