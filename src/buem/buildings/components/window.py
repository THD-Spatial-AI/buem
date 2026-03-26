"""
Window element — transparent envelope surface.

Windows are **not** present in the LOD2 geometry data.  They are synthesised
from TABULA typology fields (``A_Window_1`` / ``A_Window_2``, directional areas
``A_Window_North`` / ``East`` / ``South`` / ``West``, U-values, and g-values).

Each window element must reference a parent wall via the ``surface`` field so
the thermal model can correctly subtract window area from the net opaque wall
area for transmission loss calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from buem.buildings.components.base import EnvelopeElement


@dataclass
class WindowElement(EnvelopeElement):
    """Window (glazing) element.

    ``surface`` must reference the ID of the parent wall element.
    ``g_gl`` is the total solar energy transmittance (TABULA: ``g_gl_n_Window``).
    """

    element_type: str = "window"
    tilt: float = 90.0
    g_gl: Optional[float] = 0.5
