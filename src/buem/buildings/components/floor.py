"""
Floor element — ground-contact or inter-storey surface.

LOD2 ``GroundSurface`` entries (objectclass_id 710) have azimuth ``-1`` in the
database.  The mapper assigns azimuth 0° and tilt 0° (horizontal, facing up)
since floors receive no direct solar radiation.  ``b_transmission`` is typically
< 1.0 for ground-contact floors (unheated cellar correction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from buem.buildings.components.base import EnvelopeElement


@dataclass
class FloorElement(EnvelopeElement):
    """Floor / ground surface element.

    Additional Attributes
    ---------------------
    surface_feature_id : str or None
        LOD2 child surface identifier.
    objectclass_id : int or None
        CityGML object class (710 = GroundSurface).
    tabula_floor_group : int or None
        TABULA floor group index (1 or 2) assigned during mapping.
    """

    element_type: str = "floor"
    tilt: float = 0.0
    azimuth: float = 0.0
    surface_feature_id: Optional[str] = None
    objectclass_id: Optional[int] = None
    tabula_floor_group: Optional[int] = None
