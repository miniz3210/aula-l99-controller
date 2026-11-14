"""Concrete HTTP sender using Python standard library urllib.request.

Security-hardened, offline-testable sender:
- HTTP POST only, no request body
- Explicit timeout
- No automatic retries, no redirects of any kind
- No proxy usage, no credentials, no background threads, no buffering
- Fail closed: only 127.0.0.1 is allowed, http:// scheme only
"""

from __future__ import annotations

import re
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    HTTPRedirectHandler,
    OpenerDirector,
    ProxyHandler,
    Request,
    build_opener,
)

from aula_bridge.companion_http_transport import HttpResponse, HttpSender

_PRESS_ENDPOINT_RE = re.compile(r"^/api/location/(\d+)/(\d+)/(\d+)/press$")

_INVALID_PORT = ("__INVALID_PORT__", None)


class _NoRedirectHandler(HTTPRedirectHandler):
    """Redirect handler that rejects all HTTP redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return None to reject following any redirect."""
        return None


def _parse_host(url: str):
    """Return (host, port) for a validated http:// press-endpoint URL.

    Returns None when the URL is invalid (bad scheme, userinfo, fragment,
    query, malformed host, or unexpected path). Returns _INVALID_PORT when
    the port is out of range.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return _INVALID_PORT

    # Only the http scheme is permitted.
    if parsed.scheme != "http":
        return None

    # Reject userinfo (username/password). Never echo credentials.
    if parsed.username is not None or parsed.password is not None:
        return None

    # Reject fragments and query parameters.
    if parsed.fragment:
        return None
    if parsed.query:
        return None

    host = parsed.hostname
    if host is None:
        return None

    # Allow only the verified Companion location press endpoint.
    if not _PRESS_ENDPOINT_RE.match(parsed.path or ""):
        return None

    try:
        port = parsed.port
    except ValueError:
        return _INVALID_PORT

    if port is None:
        port = 80

    return host, port


class CompanionHttpSender(HttpSender):
    """Concrete HTTP sender backed by urllib.request."""

    def send(self, method: str, url: str, timeout: float) -> HttpResponse:
        """Send an HTTP POST request with no body to a loopback target."""
        if method is None or str(method).upper() != "POST":
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="INVALID_METHOD",
                error_message=f"Unsupported HTTP method: {method!r}",
            )

        parsed = _parse_host(url)
        if parsed is None:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="INVALID_URL",
                error_message="Invalid URL",
            )

        host, port = parsed

        if port is None or port < 1 or port > 65535:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="INVALID_PORT",
                error_message=f"Invalid port: {port}",
            )

        try:
            addr = ip_address(host)
        except ValueError:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="INVALID_HOST",
                error_message=f"Invalid host: {host!r}",
            )

        if not addr.is_loopback:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="NON_LOOPBACK_HOST",
                error_message=f"Remote host rejected: {host}",
            )

        opener = build_opener(
            ProxyHandler({}),
            _NoRedirectHandler(),
        )

        request = Request(url, method="POST", data=None)

        return self._send_once(opener, request, timeout)

    def _send_once(self, opener: OpenerDirector, request: Request, timeout: float) -> HttpResponse:
        """Open the request once and translate the result into an HttpResponse."""
        try:
            response = opener.open(request, timeout=timeout)
            status_code = response.status
            try:
                response.read()
            finally:
                response.close()
            return _status_to_response(status_code)
        except HTTPError as exc:
            return _status_to_response(exc.code)
        except URLError as exc:
            return _url_error_to_response(exc)
        except TimeoutError:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="TIMEOUT",
                error_message="Request timeout",
            )
        except ConnectionRefusedError:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="CONNECTION_REFUSED",
                error_message="Connection refused",
            )
        except OSError as exc:
            return HttpResponse(
                status_code=0,
                success=False,
                error_code="CONNECTION_ERROR",
                error_message=str(exc),
            )


def _url_error_to_response(exc: URLError) -> HttpResponse:
    reason = exc.reason
    if isinstance(reason, TimeoutError):
        return HttpResponse(
            status_code=0,
            success=False,
            error_code="TIMEOUT",
            error_message="Request timeout",
        )
    if isinstance(reason, ConnectionRefusedError):
        return HttpResponse(
            status_code=0,
            success=False,
            error_code="CONNECTION_REFUSED",
            error_message="Connection refused",
        )
    return HttpResponse(
        status_code=0,
        success=False,
        error_code="CONNECTION_ERROR",
        error_message=str(reason),
    )


def _status_to_response(status_code: int) -> HttpResponse:
    if status_code == 200:
        return HttpResponse(status_code=200, success=True)
    if status_code == 204:
        return HttpResponse(
            status_code=204,
            success=False,
            error_code="NO_CONTROL",
            error_message="No control at location",
        )
    if status_code == 400:
        return HttpResponse(
            status_code=400,
            success=False,
            error_code="INVALID_LOCATION",
            error_message="Invalid location",
        )
    if status_code == 403:
        return HttpResponse(
            status_code=403,
            success=False,
            error_code="FORBIDDEN",
            error_message="HTTP API disabled or access forbidden",
        )
    if 400 <= status_code < 500:
        return HttpResponse(
            status_code=status_code,
            success=False,
            error_code="CLIENT_ERROR",
            error_message=f"HTTP {status_code} client error",
        )
    if 500 <= status_code < 600:
        return HttpResponse(
            status_code=status_code,
            success=False,
            error_code="SERVER_ERROR",
            error_message=f"HTTP {status_code} server error",
        )
    return HttpResponse(
        status_code=status_code,
        success=False,
        error_code="UNEXPECTED_STATUS",
        error_message=f"Unexpected HTTP status: {status_code}",
    )
