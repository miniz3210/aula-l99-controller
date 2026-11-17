"""HTTP transport core for Bitfocus Companion 5.2.0.

Offline-testable HTTP transport with dependency-injected sender.
No network I/O, no retries, no buffering, no background threads.

The provider/action mapping alone may remain pure or dry-run; live Companion
dispatch is explicitly opt-in and network I/O occurs only through the configured
live Companion sender/transport path. There are no automatic retries or redirects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, Optional
import ipaddress

from aula_bridge.companion_types import ButtonLocation


@dataclass(frozen=True)
class HttpResponse:
    """Result of an HTTP request."""

    status_code: int
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class HttpSender(Protocol):
    """Dependency-injected HTTP sender protocol. No actual I/O in tests."""

    def send(
        self,
        method: str,
        url: str,
        timeout: float,
    ) -> HttpResponse:
        """Send an HTTP request and return the response.

        Args:
            method: HTTP method (e.g., "POST").
            url: Full URL including host, port, and path.
            timeout: Request timeout in seconds.

        Returns:
            HttpResponse with status_code and success flag.
        """
        ...


class CompanionHttpTransportError(Exception):
    """Raised for transport configuration or validation errors."""

    pass


class CompanionHttpTransport:
    """HTTP transport for Bitfocus Companion button press API.

    Uses dependency-injected HttpSender for offline testing.
    No automatic retries, no event buffering, no background threads.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8000
    DEFAULT_TIMEOUT = 5.0

    def __init__(
        self,
        http_sender: HttpSender,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize HTTP transport.

        Args:
            http_sender: Dependency-injected HTTP sender (protocol).
            host: Target host (must be loopback).
            port: Target port (1-65535).
            timeout: Request timeout in seconds.

        Raises:
            CompanionHttpTransportError: If host or port is invalid.
        """
        self._validate_host(host)
        self._validate_port(port)
        self._validate_timeout(timeout)

        self._http_sender = http_sender
        self._host = host
        self._port = port
        self._timeout = timeout

    def _validate_host(self, host: str) -> None:
        """Validate that host is a loopback address."""
        try:
            addr = ipaddress.ip_address(host)
        except ValueError:
            raise CompanionHttpTransportError(f"Invalid host address: {host}")

        if not addr.is_loopback:
            raise CompanionHttpTransportError(f"Non-loopback host rejected: {host}")

    def _validate_port(self, port: int) -> None:
        """Validate port range."""
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise CompanionHttpTransportError(f"Invalid port: {port}; must be 1-65535")

    def _validate_timeout(self, timeout: float) -> None:
        """Validate timeout is positive."""
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise CompanionHttpTransportError(f"Invalid timeout: {timeout}; must be positive")

    def _validate_location(self, location: ButtonLocation) -> None:
        """Validate button location fields."""
        if not isinstance(location.page, int) or location.page < 1:
            raise CompanionHttpTransportError(f"Invalid page: {location.page}; must be >= 1")
        if not isinstance(location.row, int) or location.row < 0:
            raise CompanionHttpTransportError(f"Invalid row: {location.row}; must be >= 0")
        if not isinstance(location.column, int) or location.column < 0:
            raise CompanionHttpTransportError(f"Invalid column: {location.column}; must be >= 0")

    def _build_url(self, location: ButtonLocation) -> str:
        """Build the full URL for the button press endpoint."""
        return f"http://{self._host}:{self._port}/api/location/{location.page}/{location.row}/{location.column}/press"

    def press(self, location: ButtonLocation) -> HttpResponse:
        """Send a button press request to Companion.

        Args:
            location: Validated button location (page, row, column).

        Returns:
            HttpResponse with status_code and success flag.

        Raises:
            CompanionHttpTransportError: If location is invalid.
        """
        self._validate_location(location)

        url = self._build_url(location)

        try:
            response = self._http_sender.send("POST", url, self._timeout)
        except ConnectionRefusedError:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="CONNECTION_REFUSED",
                error_message="Connection refused",
            )
        except TimeoutError:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="TIMEOUT",
                error_message="Request timeout",
            )

        return self._handle_response(response)

    def _handle_response(self, response: HttpResponse) -> HttpResponse:
        """Handle HTTP response according to Companion API semantics."""
        status = response.status_code

        if status == 200:
            return HttpResponse(status_code=200, success=True)
        elif status == 204:
            return HttpResponse(
                status_code=204,
                success=False,
                error_code="NO_CONTROL",
                error_message="No control at location",
            )
        elif status == 400:
            return HttpResponse(
                status_code=400,
                success=False,
                error_code="INVALID_LOCATION",
                error_message="Invalid location",
            )
        elif status == 403:
            return HttpResponse(
                status_code=403,
                success=False,
                error_code="FORBIDDEN",
                error_message="HTTP API disabled or access forbidden",
            )
        elif 400 <= status < 500:
            return HttpResponse(
                status_code=status,
                success=False,
                error_code="CLIENT_ERROR",
                error_message=f"HTTP {status} client error",
            )
        elif 500 <= status < 600:
            return HttpResponse(
                status_code=status,
                success=False,
                error_code="SERVER_ERROR",
                error_message=f"HTTP {status} server error",
            )
        else:
            return HttpResponse(
                status_code=status,
                success=False,
                error_code="UNEXPECTED_STATUS",
                error_message=f"Unexpected HTTP status: {status}",
            )

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def timeout(self) -> float:
        return self._timeout