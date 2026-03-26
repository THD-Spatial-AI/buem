"""
Door element — opaque entrance surface.

Doors are synthesised from TABULA typology (``A_Door_1``, ``U_Door_1``).
Like windows, each door references a parent wall via the ``surface`` field.
"""

from __future__ import annotations

from dataclasses import dataclass

from buem.buildings.components.base import EnvelopeElement


@dataclass
class DoorElement(EnvelopeElement):
    """Door element, always opaque and vertical."""

    element_type: str = "door"
    tilt: float = 90.0
