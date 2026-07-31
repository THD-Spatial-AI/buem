"""
Window element — transparent envelope surface.

Windows are **not** present in the LOD2 geometry data.  They are synthesised
from TABULA typology fields (``A_Window_1`` / ``A_Window_2``, directional areas
``A_Window_North`` / ``East`` / ``South`` / ``West``, U-values, and g-values).

Each window element must reference a parent wall via the ``surface`` field so
the thermal model can correctly subtract window area from the net opaque wall
area for transmission loss calculations.

Window areas are computed proportionally::

    window_area = (A_Window_<Direction> / A_Wall_1) × LOD2_wall_area

This ensures glazing scales with actual geometry, not the TABULA archetype's
reference areas.
"""

from __future__ import annotations

from dataclasses import dataclass

from buem.buildings.components.base import EnvelopeElement


@dataclass
class WindowElement(EnvelopeElement):
    """Window (glazing) element.

    ``surface`` must reference the ID of the parent wall element.
    ``g_gl`` is the total solar energy transmittance (TABULA: ``g_gl_n_Window``).

    Attributes
    ----------
    g_gl : float or None
        Total solar energy transmittance [-] (SHGC).  Typical range 0.4–0.8.
    F_sh_vert : float
        Vertical shading reduction factor (0–1).  Accounts for external
        obstructions on vertical surfaces (ISO 13790 §11.4.4).
    F_f : float
        Frame area fraction (0–1).  Ratio of frame to total window area
        (ISO 13790 §11.4.5).  Typical: 0.2–0.3.
    F_w : float
        Non-perpendicular incidence correction factor (0–1).  Accounts for
        angular dependence of g-value (ISO 13790 §11.4.2).
    """

    element_type: str = "window"
    tilt: float = 90.0
    g_gl: float | None = 0.5
    F_sh_vert: float = 0.75
    F_f: float = 0.20
    F_w: float = 1.0
