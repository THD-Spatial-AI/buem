"""
Ventilation element — air exchange placeholder.

Ventilation elements have no surface geometry or area.  They carry an
``air_changes`` field (informational) and serve as a marker for the thermal
model's ventilation conductance calculation, which uses
``n_air_infiltration`` + ``n_air_use`` from the thermal properties.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from buem.buildings.components.base import EnvelopeElement


@dataclass
class VentilationElement(EnvelopeElement):
    """Ventilation (air exchange) element — no surface geometry."""

    element_type: str = "ventilation"
    area: float = 0.0
    tilt: float = 0.0
    azimuth: float = 0.0
    air_changes: Optional[float] = 0.5
