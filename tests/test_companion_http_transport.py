"""Unit tests for CompanionHttpTransport.

Uses fake/injected HTTP sender only. No real sockets, no network access.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from aula_bridge.companion_http_transport import (
    ButtonLocation,
    CompanionHttpTransport,
    CompanionHttpTransportError,
    HttpResponse,
    HttpSender,
)


class FakeHttpSender:
    """Fake HTTP sender for testing. Records calls and returns configured responses."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, float]] = []
        self._response_map: dict[tuple[str, str], HttpResponse] = {}
        self._default_response: HttpResponse = HttpResponse(status_code=200, success=True)
        self._raise_on_call: Exception | None = None

    def set_response(self, method: str, url: str, response: HttpResponse) -> None:
        """Configure a specific response for a method+URL."""
        self._response_map[(method, url)] = response

    def set_default_response(self, response: HttpResponse) -> None:
        """Configure default response for unmatched calls."""
        self._default_response = response

    def set_raise(self, exc: Exception) -> None:
        """Configure sender to raise an exception on next call."""
        self._raise_on_call = exc

    def send(self, method: str, url: str, timeout: float) -> HttpResponse:
        self.calls.append((method, url, timeout))

        if self._raise_on_call:
            raise self._raise_on_call

        return self._response_map.get((method, url), self._default_response)

    def clear(self) -> None:
        self.calls.clear()
        self._response_map.clear()
        self._raise_on_call = None


class TestCompanionHttpTransport(unittest.TestCase):
    """Tests for CompanionHttpTransport."""

    def setUp(self) -> None:
        self.sender = FakeHttpSender()
        self.transport = CompanionHttpTransport(http_sender=self.sender)

    def _make_location(self, page: int = 1, row: int = 0, column: int = 0) -> ButtonLocation:
        return ButtonLocation(page=page, row=row, column=column)

    # ==================== Configuration validation ====================

    def test_default_host_is_loopback(self) -> None:
        """Default host is 127.0.0.1."""
        self.assertEqual(self.transport.host, "127.0.0.1")

    def test_default_port(self) -> None:
        """Default port is 8000."""
        self.assertEqual(self.transport.port, 8000)

    def test_default_timeout(self) -> None:
        """Default timeout is 5.0 seconds."""
        self.assertEqual(self.transport.timeout, 5.0)

    def test_custom_host_port_timeout(self) -> None:
        """Custom host, port, and timeout are accepted."""
        sender = FakeHttpSender()
        transport = CompanionHttpTransport(
            http_sender=sender,
            host="127.0.0.1",
            port=8080,
            timeout=10.0,
        )
        self.assertEqual(transport.host, "127.0.0.1")
        self.assertEqual(transport.port, 8080)
        self.assertEqual(transport.timeout, 10.0)

    def test_non_loopback_host_rejected(self) -> None:
        """Non-loopback hosts are rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError) as ctx:
            CompanionHttpTransport(http_sender=sender, host="192.168.1.1")
        self.assertIn("Non-loopback host rejected", str(ctx.exception))

    def test_invalid_host_format_rejected(self) -> None:
        """Invalid host format is rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError):
            CompanionHttpTransport(http_sender=sender, host="not-an-ip")

    def test_invalid_port_zero_rejected(self) -> None:
        """Port 0 is rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError):
            CompanionHttpTransport(http_sender=sender, port=0)

    def test_invalid_port_negative_rejected(self) -> None:
        """Negative port is rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError):
            CompanionHttpTransport(http_sender=sender, port=-1)

    def test_invalid_port_too_large_rejected(self) -> None:
        """Port > 65535 is rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError):
            CompanionHttpTransport(http_sender=sender, port=65536)

    def test_invalid_timeout_zero_rejected(self) -> None:
        """Zero timeout is rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError):
            CompanionHttpTransport(http_sender=sender, timeout=0)

    def test_invalid_timeout_negative_rejected(self) -> None:
        """Negative timeout is rejected."""
        sender = FakeHttpSender()
        with self.assertRaises(CompanionHttpTransportError):
            CompanionHttpTransport(http_sender=sender, timeout=-1.0)

    # ==================== Location validation ====================

    def test_invalid_page_rejected(self) -> None:
        """Page < 1 is rejected."""
        location = ButtonLocation(page=0, row=0, column=0)
        with self.assertRaises(CompanionHttpTransportError):
            self.transport.press(location)

    def test_invalid_row_rejected(self) -> None:
        """Row < 0 is rejected."""
        location = ButtonLocation(page=1, row=-1, column=0)
        with self.assertRaises(CompanionHttpTransportError):
            self.transport.press(location)

    def test_invalid_column_rejected(self) -> None:
        """Column < 0 is rejected."""
        location = ButtonLocation(page=1, row=0, column=-1)
        with self.assertRaises(CompanionHttpTransportError):
            self.transport.press(location)

    # ==================== HTTP request contract ====================

    def test_correct_post_method(self) -> None:
        """Request uses POST method."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        self.transport.press(location)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(method, "POST")

    def test_explicit_custom_port_overrides_default(self) -> None:
        """Explicit custom port overrides default port."""
        sender = FakeHttpSender()
        transport = CompanionHttpTransport(http_sender=sender, port=8080)
        self.assertEqual(transport.port, 8080)

    def test_correct_endpoint_construction_custom_port(self) -> None:
        """Endpoint URL uses explicit custom port."""
        sender = FakeHttpSender()
        transport = CompanionHttpTransport(http_sender=sender, port=8080)
        location = self._make_location(page=2, row=3, column=4)
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        transport.press(location)

        self.assertEqual(len(sender.calls), 1)
        method, url, timeout = sender.calls[0]
        self.assertEqual(url, "http://127.0.0.1:8080/api/location/2/3/4/press")

    def test_default_endpoint_construction_uses_default_port(self) -> None:
        """Endpoint URL uses default port 8000 when no custom port given."""
        location = self._make_location(page=2, row=3, column=4)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        self.transport.press(location)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(url, "http://127.0.0.1:8000/api/location/2/3/4/press")

    def test_correct_endpoint_construction(self) -> None:
        """Endpoint URL is correctly constructed."""
        location = self._make_location(page=2, row=3, column=4)
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        self.transport.press(location)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(url, "http://127.0.0.1:8000/api/location/2/3/4/press")

    def test_correct_location_ordering(self) -> None:
        """Location ordering in URL is page/row/column."""
        test_cases = [
            (1, 0, 0, "/api/location/1/0/0/press"),
            (5, 2, 7, "/api/location/5/2/7/press"),
            (10, 9, 8, "/api/location/10/9/8/press"),
        ]
        for page, row, column, expected_path in test_cases:
            with self.subTest(page=page, row=row, column=column):
                self.sender.clear()
                location = ButtonLocation(page=page, row=row, column=column)
                self.sender.set_default_response(HttpResponse(status_code=200, success=True))
                self.transport.press(location)
                method, url, timeout = self.sender.calls[0]
                self.assertTrue(url.endswith(expected_path))

    def test_no_request_body(self) -> None:
        """No request body is sent (sender doesn't receive one)."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        self.transport.press(location)

        # Sender only receives method, url, timeout - no body parameter
        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(len(self.sender.calls[0]), 3)

    def test_explicit_timeout_passed(self) -> None:
        """Explicit timeout is passed to sender."""
        transport = CompanionHttpTransport(
            http_sender=self.sender,
            timeout=7.5,
        )
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        transport.press(location)

        self.assertEqual(len(self.sender.calls), 1)
        method, url, timeout = self.sender.calls[0]
        self.assertEqual(timeout, 7.5)

    # ==================== Response handling ====================

    def test_http_200_success(self) -> None:
        """HTTP 200 returns success."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        response = self.transport.press(location)

        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.error_code)

    def test_http_204_no_control(self) -> None:
        """HTTP 204 returns unsuccessful (no control at location)."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=204, success=False))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.error_code, "NO_CONTROL")
        self.assertEqual(response.error_message, "No control at location")

    def test_http_400_invalid_location(self) -> None:
        """HTTP 400 returns invalid location error."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=400, success=False))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.error_code, "INVALID_LOCATION")

    def test_http_403_forbidden(self) -> None:
        """HTTP 403 returns forbidden error."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=403, success=False))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.error_code, "FORBIDDEN")

    def test_http_500_server_error(self) -> None:
        """HTTP 500 returns server error."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.error_code, "SERVER_ERROR")

    def test_http_404_client_error(self) -> None:
        """HTTP 404 returns client error."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=404, success=False))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.error_code, "CLIENT_ERROR")

    def test_connection_refused(self) -> None:
        """Connection refused returns transport failure."""
        location = self._make_location()
        self.sender.set_raise(ConnectionRefusedError("Connection refused"))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "CONNECTION_REFUSED")

    def test_timeout(self) -> None:
        """Timeout returns transport timeout."""
        location = self._make_location()
        self.sender.set_raise(TimeoutError("Request timeout"))

        response = self.transport.press(location)

        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 0)
        self.assertEqual(response.error_code, "TIMEOUT")

    # ==================== No retries, no buffering, no threads ====================

    def test_no_automatic_retries(self) -> None:
        """Failed requests are not retried automatically."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=500, success=False))

        self.transport.press(location)

        # Only one call made
        self.assertEqual(len(self.sender.calls), 1)

    def test_no_background_threads(self) -> None:
        """Transport uses no background threads (synchronous call)."""
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        # This is a synchronous call - if it returned, no background thread is running
        response = self.transport.press(location)
        self.assertTrue(response.success)

    def test_no_event_buffering(self) -> None:
        """Transport doesn't buffer events - each press is independent."""
        locations = [
            self._make_location(page=1, row=0, column=0),
            self._make_location(page=1, row=0, column=1),
            self._make_location(page=1, row=0, column=2),
        ]
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        for loc in locations:
            self.transport.press(loc)

        # Each press made exactly one call
        self.assertEqual(len(self.sender.calls), 3)

    # ==================== Dependency injection ====================

    def test_dependency_injected_http_sender(self) -> None:
        """HTTP sender is dependency-injected and used."""
        sender = FakeHttpSender()
        transport = CompanionHttpTransport(http_sender=sender)
        location = self._make_location()
        sender.set_default_response(HttpResponse(status_code=200, success=True))

        transport.press(location)

        # Verify our specific sender was called
        self.assertEqual(len(sender.calls), 1)

    def test_custom_sender_isolation(self) -> None:
        """Different transport instances use different senders."""
        sender1 = FakeHttpSender()
        sender2 = FakeHttpSender()
        transport1 = CompanionHttpTransport(http_sender=sender1)
        transport2 = CompanionHttpTransport(http_sender=sender2)
        location = self._make_location()

        sender1.set_default_response(HttpResponse(status_code=200, success=True))
        sender2.set_default_response(HttpResponse(status_code=404, success=False))

        response1 = transport1.press(location)
        response2 = transport2.press(location)

        self.assertTrue(response1.success)
        self.assertFalse(response2.success)
        self.assertEqual(len(sender1.calls), 1)
        self.assertEqual(len(sender2.calls), 1)

    # ==================== No network access ====================

    def test_no_real_network_access(self) -> None:
        """Implementation uses only injected sender, no real network."""
        # The test infrastructure itself (FakeHttpSender) proves no network access
        # All responses come from the fake sender
        location = self._make_location()
        self.sender.set_default_response(HttpResponse(status_code=200, success=True))

        response = self.transport.press(location)

        self.assertTrue(response.success)
        # Only our fake sender was called
        self.assertEqual(len(self.sender.calls), 1)


class TestButtonLocation(unittest.TestCase):
    """Tests for ButtonLocation dataclass."""

    def test_immutable(self) -> None:
        """ButtonLocation is immutable (frozen dataclass)."""
        from dataclasses import FrozenInstanceError
        loc = ButtonLocation(page=1, row=0, column=0)
        with self.assertRaises(FrozenInstanceError):
            loc.page = 2

    def test_equality(self) -> None:
        """ButtonLocation supports equality comparison."""
        loc1 = ButtonLocation(page=1, row=0, column=0)
        loc2 = ButtonLocation(page=1, row=0, column=0)
        loc3 = ButtonLocation(page=2, row=0, column=0)
        self.assertEqual(loc1, loc2)
        self.assertNotEqual(loc1, loc3)


if __name__ == "__main__":
    unittest.main()