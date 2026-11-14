"""Unit tests for CompanionHttpSender.

Uses mocked urllib handlers only. No real network requests. No live Companion
connection.
"""

import os
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.companion_http_sender import (
    CompanionHttpSender,
    _NoRedirectHandler,
)
from aula_bridge.companion_http_transport import HttpResponse


PRESS_URL = "http://127.0.0.1:5000/api/location/1/0/0/press"


class FakeOpener:
    """Fake urllib opener whose open() returns a status or raises."""

    def __init__(self, status=None, exc=None):
        self._status = status
        self._exc = exc
        self.open_calls = 0
        self.captured_timeout = None

    def open(self, request, timeout=None):
        self.open_calls += 1
        self.captured_timeout = timeout
        if self._exc is not None:
            raise self._exc
        return _FakeResponse(self._status)


class _FakeResponse:
    def __init__(self, status):
        self.status = status

    def read(self):
        return b""

    def close(self):
        return None


class TestCompanionHttpSender(unittest.TestCase):
    """Tests for CompanionHttpSender."""

    def setUp(self) -> None:
        self.sender = CompanionHttpSender()

    # ==================== Security: host validation ====================

    def test_loopback_127_0_0_1_allowed(self) -> None:
        """Only 127.0.0.1 loopback is allowed."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(status=200),
        ) as mock_build:
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
        mock_build.assert_called_once()

    def test_loopback_127_0_0_1_port_8080_allowed(self) -> None:
        """Loopback host on alternate port is allowed."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(status=200),
        ):
            response = self.sender.send(
                "POST", "http://127.0.0.1:8080/api/location/1/0/0/press", 5.0
            )
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)

    def test_localhost_rejected(self) -> None:
        """localhost hostname is rejected (not a numeric loopback IP)."""
        response = self.sender.send(
            "POST", "http://localhost:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_HOST")

    def test_remote_ipv4_rejected(self) -> None:
        """Remote IPv4 addresses are rejected."""
        response = self.sender.send(
            "POST", "http://192.168.1.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "NON_LOOPBACK_HOST")

    def test_remote_public_ip_rejected(self) -> None:
        """Remote public IPs are rejected."""
        response = self.sender.send(
            "POST", "http://8.8.8.8:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "NON_LOOPBACK_HOST")

    def test_remote_domain_rejected(self) -> None:
        """Remote domain names are rejected."""
        response = self.sender.send(
            "POST", "http://example.com:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_HOST")

    # ==================== Security: redirects disabled ====================

    def test_redirect_301_rejected(self) -> None:
        """HTTP 301 redirect is rejected as a failed response."""
        opener = FakeOpener(status=301)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(opener.open_calls, 1)

    def test_redirect_302_rejected(self) -> None:
        """HTTP 302 redirect is rejected as a failed response."""
        opener = FakeOpener(status=302)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(opener.open_calls, 1)

    def test_redirect_303_rejected(self) -> None:
        """HTTP 303 redirect is rejected as a failed response."""
        opener = FakeOpener(status=303)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(opener.open_calls, 1)

    def test_redirect_307_rejected(self) -> None:
        """HTTP 307 redirect is rejected as a failed response."""
        opener = FakeOpener(status=307)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(opener.open_calls, 1)

    def test_redirect_308_rejected(self) -> None:
        """HTTP 308 redirect is rejected as a failed response."""
        opener = FakeOpener(status=308)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 308)
        self.assertEqual(opener.open_calls, 1)

    def test_no_redirect_follow_up(self) -> None:
        """No redirect follow-up request is permitted (single open call)."""
        opener = FakeOpener(status=302)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            self.sender.send("POST", PRESS_URL, 5.0)
        self.assertEqual(opener.open_calls, 1)

    def test_no_redirect_handler_rejects_loopback_redirect(self) -> None:
        """_NoRedirectHandler rejects a redirect to a loopback URL."""
        handler = _NoRedirectHandler()
        req = Request(PRESS_URL, method="POST", data=None)
        result = handler.redirect_request(
            req, None, 302, "Found", {}, "http://127.0.0.1:5000/elsewhere"
        )
        self.assertIsNone(result)

    def test_no_redirect_handler_rejects_non_loopback_redirect(self) -> None:
        """_NoRedirectHandler rejects a redirect to a non-loopback URL."""
        handler = _NoRedirectHandler()
        req = Request(PRESS_URL, method="POST", data=None)
        result = handler.redirect_request(
            req, None, 302, "Found", {}, "http://192.168.1.1:5000/elsewhere"
        )
        self.assertIsNone(result)

    def test_post_to_get_prevention(self) -> None:
        """A redirect must not change POST to GET (no follow-up at all)."""
        opener = FakeOpener(status=303)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(opener.open_calls, 1)

    # ==================== Security: URL validation ====================

    def test_invalid_url_rejected(self) -> None:
        """Malformed URLs are rejected."""
        response = self.sender.send("POST", "not-a-url", 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_empty_url_rejected(self) -> None:
        """Empty URL is rejected."""
        response = self.sender.send("POST", "", 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_missing_scheme_rejected(self) -> None:
        """URL without scheme is rejected."""
        response = self.sender.send(
            "POST", "127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_https_scheme_rejected(self) -> None:
        """https:// scheme is rejected."""
        response = self.sender.send(
            "POST", "https://127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_ftp_scheme_rejected(self) -> None:
        """ftp:// scheme is rejected."""
        response = self.sender.send(
            "POST", "ftp://127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_file_scheme_rejected(self) -> None:
        """file:// scheme is rejected."""
        response = self.sender.send(
            "POST", "file:///etc/passwd", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_unsupported_scheme_rejected(self) -> None:
        """Unsupported schemes are rejected."""
        response = self.sender.send(
            "POST", "ws://127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_url_userinfo_rejected(self) -> None:
        """URLs with username/password userinfo are rejected."""
        response = self.sender.send(
            "POST", "http://user:pass@127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")
        self.assertNotIn("user", response.error_message or "")
        self.assertNotIn("pass", response.error_message or "")
        self.assertNotIn("@127.0.0.1", response.error_message or "")

    def test_url_username_only_rejected(self) -> None:
        """URLs with username-only userinfo are rejected."""
        response = self.sender.send(
            "POST", "http://user@127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_url_fragment_rejected(self) -> None:
        """URLs with fragments are rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:5000/api/location/1/0/0/press#section", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_url_query_rejected(self) -> None:
        """URLs with unexpected query parameters are rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:5000/api/location/1/0/0/press?foo=bar", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_invalid_endpoint_path_rejected(self) -> None:
        """Unexpected endpoint paths are rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:5000/api/other/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_missing_press_suffix_rejected(self) -> None:
        """URLs missing the /press suffix are rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:5000/api/location/1/0/0", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_none_host_rejected(self) -> None:
        """URL with no host is rejected."""
        response = self.sender.send(
            "POST", "http://:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")

    def test_invalid_port_zero_rejected(self) -> None:
        """Port 0 is rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:0/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_PORT")

    def test_invalid_port_negative_rejected(self) -> None:
        """Negative port is rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:-1/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_PORT")

    def test_invalid_port_too_large_rejected(self) -> None:
        """Port > 65535 is rejected."""
        response = self.sender.send(
            "POST", "http://127.0.0.1:65536/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_PORT")

    # ==================== Security: fail closed ====================

    def test_fail_closed_on_unknown_error(self) -> None:
        """Unexpected errors fail closed rather than succeeding."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(exc=OSError("boom")),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "CONNECTION_ERROR")

    def test_no_credential_leakage(self) -> None:
        """Error messages never include credentials or userinfo URLs."""
        response = self.sender.send(
            "POST", "http://admin:secret@127.0.0.1:5000/api/location/1/0/0/press", 5.0
        )
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_URL")
        self.assertNotIn("admin", response.error_message)
        self.assertNotIn("secret", response.error_message)
        self.assertNotIn("userinfo", response.error_message.lower())

    # ==================== HTTP status handling ====================

    def test_http_200_success(self) -> None:
        """HTTP 200 returns success."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(status=200),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.error_code)

    def test_http_204_no_control(self) -> None:
        """HTTP 204 returns unsuccessful (no control)."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(status=204),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.error_code, "NO_CONTROL")

    def test_http_400_invalid_location(self) -> None:
        """HTTP 400 returns invalid location error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 400, "Bad Request", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.error_code, "INVALID_LOCATION")

    def test_http_403_forbidden(self) -> None:
        """HTTP 403 returns forbidden error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 403, "Forbidden", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.error_code, "FORBIDDEN")

    def test_http_404_client_error(self) -> None:
        """HTTP 404 returns client error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 404, "Not Found", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.error_code, "CLIENT_ERROR")

    def test_http_409_client_error(self) -> None:
        """HTTP 409 returns client error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 409, "Conflict", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.error_code, "CLIENT_ERROR")

    def test_http_500_server_error(self) -> None:
        """HTTP 500 returns server error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 500, "Server Error", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.error_code, "SERVER_ERROR")

    def test_http_502_server_error(self) -> None:
        """HTTP 502 returns server error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 502, "Bad Gateway", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.error_code, "SERVER_ERROR")

    def test_http_503_server_error(self) -> None:
        """HTTP 503 returns server error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(
                exc=HTTPError(PRESS_URL, 503, "Unavailable", {}, None)
            ),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.error_code, "SERVER_ERROR")

    def test_http_unexpected_status(self) -> None:
        """Unexpected status codes return unexpected status error."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(status=301),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.error_code, "UNEXPECTED_STATUS")

    # ==================== Connection errors ====================

    def test_connection_refused(self) -> None:
        """Connection refused returns transport failure."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(exc=ConnectionRefusedError("refused")),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "CONNECTION_REFUSED")

    def test_connection_refused_via_urlerror(self) -> None:
        """Connection refused wrapped in URLError returns connection refused."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(exc=URLError(ConnectionRefusedError("refused"))),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "CONNECTION_REFUSED")

    def test_timeout(self) -> None:
        """Timeout returns transport timeout."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(exc=TimeoutError("timed out")),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "TIMEOUT")

    def test_timeout_via_urlerror(self) -> None:
        """Timeout wrapped in URLError returns timeout."""
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=FakeOpener(exc=URLError(TimeoutError("timed out"))),
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "TIMEOUT")

    # ==================== Request contract ====================

    def test_post_method_only(self) -> None:
        """Only POST method is accepted."""
        response = self.sender.send("GET", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_METHOD")

    def test_none_method_rejected(self) -> None:
        """None method is rejected."""
        response = self.sender.send(None, PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(response.error_code, "INVALID_METHOD")

    def test_timeout_passed_to_open(self) -> None:
        """Explicit timeout is passed through."""
        opener = FakeOpener(status=200)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            self.sender.send("POST", PRESS_URL, 7.5)
        self.assertEqual(opener.captured_timeout, 7.5)

    def test_no_retries_single_call(self) -> None:
        """Failed requests are not retried automatically."""
        opener = FakeOpener(exc=ConnectionRefusedError("refused"))
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertFalse(response.success)
        self.assertEqual(opener.open_calls, 1)

    def test_valid_companion_press_request(self) -> None:
        """A valid Companion press location request succeeds."""
        opener = FakeOpener(status=200)
        with patch(
            "aula_bridge.companion_http_sender.build_opener",
            return_value=opener,
        ):
            response = self.sender.send("POST", PRESS_URL, 5.0)
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(opener.open_calls, 1)


if __name__ == "__main__":
    unittest.main()
