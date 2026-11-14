"""Shared Companion type definitions.

Holds the canonical immutable ButtonLocation dataclass used across the
Companion integration modules to avoid duplicate type definitions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ButtonLocation:
    """Immutable button location on a Companion page grid."""

    page: int
    row: int
    column: int
