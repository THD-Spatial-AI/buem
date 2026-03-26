"""
Base envelope element dataclass.

All building surface types (wall, roof, floor, window, door, ventilation) inherit
from ``EnvelopeElement``.  The base class carries the fields common to all element
types and provides serialisation helpers for the v3 GeoJSON schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EnvelopeElement:
    """A single building envelope element.

    Maps to one entry in ``envelope.elements`` (geometry) and one entry in
    ``thermal.element_properties`` (performance) in the v3 GeoJSON schema.

    Attributes
    ----------
    id : str
        Unique element identifier within the building (e.g. ``"wall_south"``).
    element_type : str
        One of ``"wall"``, ``"roof"``, ``"floor"``, ``"window"``, ``"door"``,
        ``"ventilation"``.
    area : float
        Surface area [m²].  Zero for ventilation elements.
    azimuth : float
        Compass bearing in degrees, 0 = North, 90 = East, 180 = South, 270 = West.
    tilt : float
        Angle from horizontal:  0 = horizontal up (floor/flat roof),
        90 = vertical (wall), value for pitched roof elements.
    U : float or None
        Thermal transmittance [W/(m²K)].
    b_transmission : float
        Transmission correction factor (0–1).  Default 1.0 for exterior elements.
    surface : str or None
        ID of the parent wall element — used for windows and doors only.
    g_gl : float or None
        Solar heat gain coefficient — window elements only.
    air_changes : float or None
        Air changes per hour — ventilation elements only.
    """

    id: str = ""
    element_type: str = "wall"
    area: float = 0.0
    azimuth: float = 0.0
    tilt: float = 90.0
    U: Optional[float] = None
    b_transmission: float = 1.0
    surface: Optional[str] = None
    g_gl: Optional[float] = None
    air_changes: Optional[float] = None

    # ── serialisation to v3 GeoJSON ──────────────────────────────────────────

    def to_element_dict(self) -> Dict[str, Any]:
        """Return a complete ``envelope.elements[i]`` dict with inline thermal props.

        Matches the v3 example_request.json structure where geometry and
        thermal properties live together on each element.  Ventilation
        elements carry only ``air_changes``.
        """
        d: Dict[str, Any] = {
            "id": self.id,
            "type": self.element_type,
        }

        if self.element_type == "ventilation":
            if self.air_changes is not None:
                d["air_changes"] = {"value": round(self.air_changes, 4), "unit": "1/h"}
            return d

        # Geometry
        d["area"] = {"value": round(self.area, 2), "unit": "m2"}
        d["azimuth"] = {"value": round(self.azimuth, 1), "unit": "deg"}
        d["tilt"] = {"value": round(self.tilt, 1), "unit": "deg"}

        # Parent linkage (windows, doors)
        if self.surface is not None:
            d["parent_id"] = self.surface

        # Thermal properties — inline per v3 schema
        if self.U is not None:
            d["U"] = {"value": round(self.U, 4), "unit": "W/(m2K)"}

        if self.element_type == "window":
            if self.g_gl is not None:
                d["g_gl"] = {"value": round(self.g_gl, 4), "unit": "-"}
        else:
            d["b_transmission"] = {"value": round(self.b_transmission, 4), "unit": "-"}

        return d

        return d
