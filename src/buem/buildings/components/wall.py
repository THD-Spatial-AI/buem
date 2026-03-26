"""
Wall element — opaque vertical surface.

Wall elements are the most complex component due to LOD2 surface linkage:
each CityGML ``WallSurface`` becomes a separate ``WallElement`` with its own
area, azimuth, and height.  TABULA provides up to 3 wall groups with distinct
U-values (``U_Wall_1`` / ``U_Wall_2`` / ``U_Wall_3``).  The mapper assigns
LOD2 surfaces to TABULA groups based on orientation or area proportion.

LOD2 surface linkage fields (``surface_feature_id``, ``objectclass_id``,
``height``) are retained for traceability but are **not** serialised to
GeoJSON — they are internal metadata only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from buem.buildings.components.base import EnvelopeElement


@dataclass
class WallElement(EnvelopeElement):
    """Wall surface element.

    Inherits all fields from ``EnvelopeElement`` and adds LOD2-specific
    metadata for traceability.

    Additional Attributes
    ---------------------
    surface_feature_id : str or None
        LOD2 child surface identifier (from ``lod2_child_feature_surface``).
    objectclass_id : int or None
        CityGML object class (709 = WallSurface).
    height : float or None
        Surface height from LOD2 geometry [m].
    tabula_wall_group : int or None
        TABULA wall group index (1, 2, or 3) assigned during mapping.
    """

    element_type: str = "wall"
    tilt: float = 90.0
    surface_feature_id: Optional[str] = None
    objectclass_id: Optional[int] = None
    height: Optional[float] = None
    tabula_wall_group: Optional[int] = None
