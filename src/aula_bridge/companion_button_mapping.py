"""Strictly validated Companion button mapping configuration loader.

Local JSON parsing and validation only. No network transport, no I/O beyond
reading the provided local file, no Companion connection, no hardware access.

Maps logical numpad keys to immutable button locations (page, row, column).
"""

from __future__ import annotations

import json
import os
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Tuple

from aula_bridge.action_mapping import NUM_PAD_KEYS
from aula_bridge.companion_types import ButtonLocation

MAPPING_VERSION = 1
SUPPORTED_VERSIONS = frozenset({MAPPING_VERSION})

REQUIRED_LOCATION_FIELDS = frozenset({"page", "row", "column"})
ALLOWED_LOCATION_FIELDS = frozenset({"page", "row", "column"})


class CompanionButtonMappingError(ValueError):
    """Raised when a Companion button mapping configuration is invalid."""


def _reject_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    """object_pairs_hook that rejects duplicate JSON keys."""
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CompanionButtonMappingError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _is_int(value: Any) -> bool:
    """Return True only for genuine integers (booleans are excluded)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_location(value: Any, logical_key: str) -> ButtonLocation:
    """Validate a single location object and return a ButtonLocation."""
    if not isinstance(value, dict):
        raise CompanionButtonMappingError(
            f"Location for {logical_key!r} must be an object, got {type(value).__name__}"
        )

    fields = set(value.keys())
    missing = REQUIRED_LOCATION_FIELDS - fields
    if missing:
        raise CompanionButtonMappingError(
            f"Location for {logical_key!r} missing fields: {sorted(missing)}"
        )

    extra = fields - ALLOWED_LOCATION_FIELDS
    if extra:
        raise CompanionButtonMappingError(
            f"Location for {logical_key!r} has unknown fields: {sorted(extra)}"
        )

    page = value["page"]
    row = value["row"]
    column = value["column"]

    if not _is_int(page):
        raise CompanionButtonMappingError(
            f"page for {logical_key!r} must be an integer, got {type(page).__name__}"
        )
    if not _is_int(row):
        raise CompanionButtonMappingError(
            f"row for {logical_key!r} must be an integer, got {type(row).__name__}"
        )
    if not _is_int(column):
        raise CompanionButtonMappingError(
            f"column for {logical_key!r} must be an integer, got {type(column).__name__}"
        )

    if page < 1:
        raise CompanionButtonMappingError(
            f"page for {logical_key!r} must be >= 1, got {page}"
        )
    if row < 0:
        raise CompanionButtonMappingError(
            f"row for {logical_key!r} must be >= 0, got {row}"
        )
    if column < 0:
        raise CompanionButtonMappingError(
            f"column for {logical_key!r} must be >= 0, got {column}"
        )

    return ButtonLocation(page=page, row=row, column=column)


def load_companion_button_mapping(path: str) -> Mapping[str, ButtonLocation]:
    """Load and validate a Companion button mapping from a local JSON file.

    Args:
        path: Path to a local JSON configuration file.

    Returns:
        An immutable mapping from logical numpad key to ButtonLocation.

    Raises:
        CompanionButtonMappingError: If the file is missing, malformed, or fails
            any validation rule.
    """
    if not os.path.isfile(path):
        raise CompanionButtonMappingError(f"Mapping file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh, object_pairs_hook=_reject_duplicates)
    except CompanionButtonMappingError:
        raise
    except json.JSONDecodeError as exc:
        raise CompanionButtonMappingError(f"Malformed JSON: {exc}") from exc
    except OSError as exc:
        raise CompanionButtonMappingError(f"Cannot read mapping file: {exc}") from exc

    if not isinstance(data, dict):
        raise CompanionButtonMappingError(
            f"Top-level JSON must be an object, got {type(data).__name__}"
        )

    version = data.get("version")
    if not _is_int(version):
        raise CompanionButtonMappingError(
            f"version must be an integer, got {type(version).__name__}"
        )
    if version not in SUPPORTED_VERSIONS:
        raise CompanionButtonMappingError(
            f"Unsupported version: {version}; supported versions: "
            f"{sorted(SUPPORTED_VERSIONS)}"
        )

    mappings = data.get("mappings")
    if mappings is None:
        raise CompanionButtonMappingError("mappings field is required")
    if not isinstance(mappings, dict):
        raise CompanionButtonMappingError(
            f"mappings must be an object, got {type(mappings).__name__}"
        )

    allowed_keys = frozenset(NUM_PAD_KEYS)
    result: Dict[str, ButtonLocation] = {}
    for logical_key, location in mappings.items():
        if not isinstance(logical_key, str):
            raise CompanionButtonMappingError(
                f"Mapping key must be a string, got {type(logical_key).__name__}"
            )
        if logical_key not in allowed_keys:
            raise CompanionButtonMappingError(
                f"Unknown logical key: {logical_key!r}; allowed keys: "
                f"{sorted(allowed_keys)}"
            )
        result[logical_key] = _validate_location(location, logical_key)

    return MappingProxyType(result)
