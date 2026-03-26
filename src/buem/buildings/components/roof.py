"""
Roof element — opaque surface above habitable space.

LOD2 ``RoofSurface`` entries (objectclass_id 712) typically have a tilt derived
from the 3D geometry.  The database azimuth field stores ``-1`` for roofs, so
the mapper assigns a sensible placeholder (e.g. 180° south-facing) because
roof azimuth has negligible effect on transmission losses but is used for
solar irradiance computation on tilted surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from buem.buildings.components.base import EnvelopeElement


@dataclass
class RoofElement(EnvelopeElement):
    """Roof surface element.

    Additional Attributes
    ---------------------
    surface_feature_id : str or None
        LOD2 child surface identifier.
    objectclass_id : int or None
        CityGML object class (712 = RoofSurface).
    tabula_roof_group : int or None
        TABULA roof group index (1 or 2) assigned during mapping.
    """

    element_type: str = "roof"
    tilt: float = 30.0
    surface_feature_id: Optional[str] = None
    objectclass_id: Optional[int] = None
    tabula_roof_group: Optional[int] = None
