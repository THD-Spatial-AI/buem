"""
Canonical Building representation — single source of truth.

All data sources (PostgreSQL, Excel, GeoJSON) produce Building objects.
All consumers (ModelBUEM, JSON generator, API) accept Building objects.
This decouples ingestion from computation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from buem.buildings.components.base import EnvelopeElement


@dataclass
class BuildingIdentity:
    """Thematic / classification parameters — maps to v3 schema ``building`` node.

    Attributes
    ----------
    building_feature_id : str
        Unique building identifier (from LOD2 database or user-defined).
    country : str
        ISO 3166-1 alpha-2 country code (e.g. ``"DE"``, ``"NL"``).
    building_type : str
        TABULA building size class (e.g. ``"SFH"``, ``"MFH"``, ``"TH"``, ``"AB"``).
    construction_period : str
        Construction year range (e.g. ``"1949-1957"``).
    tabula_variant_code : str or None
        Full TABULA variant code (e.g. ``"DE.N.MFH.03.Gen.ReEx.001.001"``).
    n_storeys : int
        Number of above-ground storeys.
    neighbour_status : str
        Attached neighbour code: ``"B_Alone"``, ``"B_N1"``, ``"B_N2"``.
    latitude : float
        Geographic latitude in decimal degrees.
    longitude : float
        Geographic longitude in decimal degrees.
    """

    building_feature_id: str
    country: str = "DE"
    building_type: str = "SFH"
    construction_period: str = ""
    tabula_variant_code: Optional[str] = None
    n_storeys: int = 1
    neighbour_status: str = "B_Alone"
    latitude: float = 52.0
    longitude: float = 5.0


@dataclass
class ThermalProperties:
    """Bulk thermal parameters — maps to v3 schema ``thermal`` node.

    All values use SI / TABULA-native units:
      - Air change rates in ``1/h``
      - Thermal capacity in ``kJ/(m²K)``
      - Temperatures in ``°C``
      - Dimensionless factors as fractions (0–1)

    Attributes
    ----------
    n_air_infiltration : float
        Design infiltration air change rate [1/h].
    n_air_use : float
        Usage / mechanical ventilation air change rate [1/h].
    c_m : float
        Internal thermal capacity per reference floor area [kJ/(m²K)].
    thermal_class : str
        ISO 13790 thermal mass class (``"light"``, ``"medium"``, ``"heavy"``).
    comfortT_lb : float
        Heating setpoint — indoor comfort lower bound [°C].
    comfortT_ub : float
        Cooling setpoint — indoor comfort upper bound [°C].
    design_T_min : float
        Outdoor design temperature for peak load sizing [°C].
    F_sh_hor : float
        Horizontal shading reduction factor (0–1).
    F_sh_vert : float
        Vertical shading reduction factor (0–1).
    F_f : float
        Window frame area fraction (0–1).
    F_w : float
        Window correction factor (0–1).
    h_room : float
        Average room height [m].
    phi_int : float or None
        Specific internal heat gains [W/m²].  ``None`` → use model default.
    q_w_nd : float or None
        Specific hot-water demand [kWh/(m²·a)].  ``None`` → not provided.
    """

    n_air_infiltration: float = 0.5
    n_air_use: float = 0.5
    c_m: float = 165.0
    thermal_class: str = "medium"
    comfortT_lb: float = 21.0
    comfortT_ub: float = 24.0
    design_T_min: float = -12.0
    F_sh_hor: float = 0.80
    F_sh_vert: float = 0.75
    F_f: float = 0.20
    F_w: float = 1.0
    h_room: float = 2.5
    phi_int: Optional[float] = None
    q_w_nd: Optional[float] = None


@dataclass
class Building:
    """Canonical building representation — assembled from any data source.

    A ``Building`` holds three concerns:

    1. **Identity** — what the building *is* (type, location, TABULA code).
    2. **Envelope** — geometric elements (walls, roofs, floors, windows, etc.)
       each carrying their own U-value, area, orientation, and tilt.
    3. **Thermal** — bulk thermal parameters (air change rates, setpoints,
       shading factors, etc.).

    The ``to_v3_geojson_feature()`` method serialises a ``Building`` into the
    v3 GeoJSON schema format used by the BUEM API and thermal model pipeline.

    Parameters
    ----------
    identity : BuildingIdentity
        Classification and location metadata.
    elements : list of EnvelopeElement
        All envelope elements (walls, roofs, floors, windows, doors, ventilation).
    thermal : ThermalProperties
        Bulk thermal / occupancy parameters.
    A_ref : float
        Heated reference floor area [m²].  If ``0``, derived from floor elements.
    """

    identity: BuildingIdentity
    elements: List[EnvelopeElement] = field(default_factory=list)
    thermal: ThermalProperties = field(default_factory=ThermalProperties)
    A_ref: float = 0.0

    # ── element accessors ────────────────────────────────────────────────────

    def walls(self) -> List[EnvelopeElement]:
        """Return all wall elements."""
        return [e for e in self.elements if e.element_type == "wall"]

    def roofs(self) -> List[EnvelopeElement]:
        """Return all roof elements."""
        return [e for e in self.elements if e.element_type == "roof"]

    def floors(self) -> List[EnvelopeElement]:
        """Return all floor elements."""
        return [e for e in self.elements if e.element_type == "floor"]

    def windows(self) -> List[EnvelopeElement]:
        """Return all window elements."""
        return [e for e in self.elements if e.element_type == "window"]

    def doors(self) -> List[EnvelopeElement]:
        """Return all door elements."""
        return [e for e in self.elements if e.element_type == "door"]

    def ventilation_elements(self) -> List[EnvelopeElement]:
        """Return all ventilation elements."""
        return [e for e in self.elements if e.element_type == "ventilation"]

    # ── derived properties ───────────────────────────────────────────────────

    def computed_A_ref(self) -> float:
        """Return ``A_ref`` if set, otherwise sum of floor element areas."""
        if self.A_ref > 0:
            return self.A_ref
        return sum(e.area for e in self.floors())

    # ── serialisation ────────────────────────────────────────────────────────

    def to_v3_geojson_feature(self) -> Dict[str, Any]:
        """Serialise to a v3-schema-compliant GeoJSON Feature dict.

        Returns
        -------
        dict
            A GeoJSON ``Feature`` with ``id``, ``geometry``, and ``properties``
            containing ``buem.building``, ``buem.envelope``, ``buem.thermal``,
            and ``buem.solver`` nodes.
        """
        ident = self.identity
        th = self.thermal
        a_ref = self.computed_A_ref()

        # --- envelope node (inside building, with inline thermal props) ---
        envelope_elements: List[Dict[str, Any]] = []
        for elem in self.elements:
            envelope_elements.append(elem.to_element_dict())

        # --- thermal node (inside building, bulk properties only) ---
        thermal_node: Dict[str, Any] = {
            "n_air_infiltration": {"value": round(th.n_air_infiltration, 4), "unit": "1/h"},
            "n_air_use": {"value": round(th.n_air_use, 4), "unit": "1/h"},
        }
        if th.thermal_class:
            thermal_node["thermal_class"] = th.thermal_class
        thermal_node["comfortT_lb"] = {"value": round(th.comfortT_lb, 1), "unit": "degC"}
        thermal_node["comfortT_ub"] = {"value": round(th.comfortT_ub, 1), "unit": "degC"}

        # --- building node (envelope + thermal nested inside) ---
        building_node: Dict[str, Any] = {
            "building_type": ident.building_type,
            "construction_period": ident.construction_period,
            "country": ident.country,
            "n_storeys": ident.n_storeys,
            "A_ref": {"value": round(a_ref, 2), "unit": "m2"},
            "h_room": {"value": round(th.h_room, 2), "unit": "m"},
            "neighbour_status": ident.neighbour_status,
            "envelope": {"elements": envelope_elements},
            "thermal": thermal_node,
        }

        # --- solver node (sibling of building) ---
        solver_node = {"use_milp": False}

        # --- assemble feature ---
        return {
            "type": "Feature",
            "id": str(ident.building_feature_id),
            "geometry": {
                "type": "Point",
                "coordinates": [
                    round(ident.longitude, 6),
                    round(ident.latitude, 6),
                ],
            },
            "properties": {
                "start_time": "2018-01-01T00:00:00Z",
                "end_time": "2018-12-31T23:00:00Z",
                "resolution": "60",
                "resolution_unit": "minutes",
                "buem": {
                    "building": building_node,
                    "solver": solver_node,
                },
            },
        }
