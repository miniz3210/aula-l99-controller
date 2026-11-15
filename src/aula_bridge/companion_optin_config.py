"""Strictly validated Companion opt-in configuration loader.

Local JSON parsing and validation only. No network transport, no I/O beyond
reading the provided local file, no Companion connection, no hardware access.
Companion is disabled by default and is never automatically activated.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from aula_bridge.companion_button_mapping import _is_int

CONFIG_VERSION = 1
SUPPORTED_VERSIONS = frozenset({CONFIG_VERSION})

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_TIMEOUT = 5.0

KNOWN_TOP_LEVEL_FIELDS = frozenset({"version", "companion"})
KNOWN_COMPANION_FIELDS = frozenset(
    {"enabled", "host", "port", "timeout", "mapping_file"}
)


class CompanionOptInConfigError(ValueError):
    """Raised when Companion opt-in configuration is invalid."""


def _reject_duplicates(pairs):
    """object_pairs_hook that rejects duplicate JSON keys."""
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CompanionOptInConfigError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _is_genuine_number(value: Any) -> bool:
    """Return True for int/float that is not a bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_host(host: str) -> None:
    """Validate that host is a numeric loopback address."""
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        raise CompanionOptInConfigError(f"Invalid host address: {host}")

    if not addr.is_loopback:
        raise CompanionOptInConfigError(f"Non-loopback host rejected: {host}")


def _validate_port(port: Any) -> None:
    """Validate port range and type."""
    if not _is_int(port):
        raise CompanionOptInConfigError(
            f"Invalid port: {port!r}; must be an integer"
        )
    if port < 1 or port > 65535:
        raise CompanionOptInConfigError(
            f"Invalid port: {port}; must be 1-65535"
        )


def _validate_timeout(timeout: Any) -> None:
    """Validate timeout is positive and finite."""
    if not _is_genuine_number(timeout):
        raise CompanionOptInConfigError(
            f"Invalid timeout: {timeout!r}; must be a number"
        )
    if not math.isfinite(timeout):
        raise CompanionOptInConfigError(
            f"Invalid timeout: {timeout!r}; must be finite"
        )
    if timeout <= 0:
        raise CompanionOptInConfigError(
            f"Invalid timeout: {timeout!r}; must be positive"
        )


def _validate_mapping_path(mapping_file: Any) -> None:
    """Validate mapping file path syntax."""
    if not isinstance(mapping_file, str):
        raise CompanionOptInConfigError(
            f"mapping_file must be a string, got {type(mapping_file).__name__}"
        )
    if not mapping_file:
        raise CompanionOptInConfigError("mapping_file must not be empty")
    if "\x00" in mapping_file:
        raise CompanionOptInConfigError("mapping_file must not contain null bytes")


@dataclass(frozen=True)
class CompanionOptInConfig:
    """Immutable Companion opt-in configuration."""

    enabled: bool = False
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    timeout: float = DEFAULT_TIMEOUT
    mapping_file: Optional[str] = None


def load(path: Optional[str] = None) -> CompanionOptInConfig:
    """Load and validate Companion opt-in configuration from a JSON file.

    Missing or unreadable config files produce the default (disabled) config.
    No network connections are opened and no transport is constructed.
    """
    if path is None or not os.path.isfile(path):
        return CompanionOptInConfig()

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh, object_pairs_hook=_reject_duplicates)
    except CompanionOptInConfigError:
        raise
    except json.JSONDecodeError as exc:
        raise CompanionOptInConfigError(f"Malformed JSON: {exc}") from exc
    except OSError as exc:
        raise CompanionOptInConfigError(f"Cannot read config file: {exc}") from exc

    if not isinstance(data, dict):
        raise CompanionOptInConfigError(
            f"Top-level JSON must be an object, got {type(data).__name__}"
        )

    top_fields = set(data.keys())
    unknown_top = top_fields - KNOWN_TOP_LEVEL_FIELDS
    if unknown_top:
        raise CompanionOptInConfigError(
            f"Unknown top-level fields: {sorted(unknown_top)}"
        )

    version = data.get("version")
    if version is not None:
        if not _is_int(version):
            raise CompanionOptInConfigError(
                f"version must be an integer, got {type(version).__name__}"
            )
        if version not in SUPPORTED_VERSIONS:
            raise CompanionOptInConfigError(
                f"Unsupported version: {version}; supported versions: "
                f"{sorted(SUPPORTED_VERSIONS)}"
            )

    companion = data.get("companion")
    if companion is None:
        return CompanionOptInConfig()

    if not isinstance(companion, dict):
        raise CompanionOptInConfigError(
            f"companion must be an object, got {type(companion).__name__}"
        )

    comp_fields = set(companion.keys())
    unknown_comp = comp_fields - KNOWN_COMPANION_FIELDS
    if unknown_comp:
        raise CompanionOptInConfigError(
            f"Unknown companion fields: {sorted(unknown_comp)}"
        )

    enabled = companion.get("enabled", False)
    if not isinstance(enabled, bool):
        raise CompanionOptInConfigError(
            f"enabled must be a boolean, got {type(enabled).__name__}"
        )

    host = companion.get("host", DEFAULT_HOST)
    if not isinstance(host, str):
        raise CompanionOptInConfigError(
            f"host must be a string, got {type(host).__name__}"
        )
    _validate_host(host)

    port = companion.get("port", DEFAULT_PORT)
    _validate_port(port)

    timeout = companion.get("timeout", DEFAULT_TIMEOUT)
    _validate_timeout(timeout)

    mapping_file = companion.get("mapping_file", None)
    if mapping_file is not None:
        _validate_mapping_path(mapping_file)

    if enabled and mapping_file is None:
        raise CompanionOptInConfigError(
            "companion.enabled=true requires an explicit mapping_file"
        )

    return CompanionOptInConfig(
        enabled=enabled,
        host=host,
        port=port,
        timeout=timeout,
        mapping_file=mapping_file,
    )
