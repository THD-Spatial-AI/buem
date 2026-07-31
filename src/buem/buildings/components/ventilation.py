"""
Ventilation element — air exchange opening or infiltration placeholder.

Ventilation elements model physical openings (ventilation grilles, trickle
vents) on exterior walls, or an infiltration-only placeholder when no such
openings exist (fully party-walled buildings).

Physical openings carry area, azimuth, and tilt inherited from their host
wall, and reference that wall via ``surface`` (parent_id).  The thermal
model's ventilation conductance is driven by the *air change rate*
(``n_air_use`` + ``n_air_infiltration``) and the building volume, **not** by
the opening area — the area is used for net wall area accounting and future
wind-driven ventilation models.

Opening sizes
-------------
- Front wall: :data:`~buem.buildings.mapping.element_factory.VENT_AREA_FRONT`
  (1.0 m², capped at 10 % of wall area)
- Back wall:  :data:`~buem.buildings.mapping.element_factory.VENT_AREA_BACK`
  (0.5 m², capped at 10 % of wall area)
"""

from __future__ import annotations

from dataclasses import dataclass

from buem.buildings.components.base import EnvelopeElement


@dataclass
class VentilationElement(EnvelopeElement):
    """Ventilation (air exchange) element.

    Physical openings have ``area > 0``, ``azimuth``/``tilt`` matching the
    host wall, and ``surface`` pointing to the parent wall ID.
    Infiltration-only elements have ``area = 0`` and no parent.

    Attributes
    ----------
    air_changes : float or None
        Intentional air change rate [1/h] assigned to this opening.
        For cross-ventilation, each opening carries half of ``n_air_use``.
    """

    element_type: str = "ventilation"
    area: float = 0.0
    tilt: float = 0.0
    azimuth: float = 0.0
    air_changes: float | None = 0.5
