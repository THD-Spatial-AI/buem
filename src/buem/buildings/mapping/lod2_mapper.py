"""
LOD2 + TABULA → Building mapper.

Reads raw DataFrames from any ``BuildingSource`` (Excel or PostgreSQL) and
produces a list of canonical ``Building`` objects ready for v3 JSON generation.

Table linkages
--------------
- ``lod2_building_feature.building_feature_id`` → ``lod2_child_feature_surface.building_feature_id``  (1:N)
- ``lod2_building_feature.tabula_variant_code_id`` → ``tabula.id``  (N:1)

Surface classification
----------------------
- ``objectclass_id = 709`` → WallSurface  (tilt DB 0 → v3 90°, azimuth from DB)
- ``objectclass_id = 710`` → GroundSurface (tilt DB −90 → v3 0°, azimuth → 0°)
- ``objectclass_id = 712`` → RoofSurface  (tilt from DB clamped 0–90, azimuth → 180°)

TABULA variant selection
------------------------
Each component type (wall, roof, floor) may have multiple TABULA variants
(Wall_1/2/3, Roof_1/2, Floor_1/2) with different U-values and b_transmission
factors.  Only the *primary exterior variant* — the one with the largest area
and b_transmission > 0 — is used for LOD2 surfaces.  Windows are synthesised
from TABULA directional window areas (``A_Window_North/South/East/West``).
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Protocol, Tuple

import pandas as pd

from buem.buildings.building import Building, BuildingIdentity, ThermalProperties
from buem.buildings.components.base import EnvelopeElement

logger = logging.getLogger(__name__)


# ── objectclass_id → element type ────────────────────────────────────────────
OBJECTCLASS_WALL = 709
OBJECTCLASS_GROUND = 710
OBJECTCLASS_ROOF = 712

# Cardinal direction bins for window distribution (azimuth ranges in degrees)
# Each bin: (label, centre_azimuth, lower_bound, upper_bound)
_DIRECTION_BINS = [
    ("north", 0.0, 315.0, 45.0),    # wraps around 0°
    ("east", 90.0, 45.0, 135.0),
    ("south", 180.0, 135.0, 225.0),
    ("west", 270.0, 225.0, 315.0),
]


class BuildingSource(Protocol):
    """Minimal interface for data sources (Excel or PostgreSQL)."""

    @property
    def buildings(self) -> pd.DataFrame: ...

    @property
    def surfaces(self) -> pd.DataFrame: ...

    @property
    def tabula(self) -> pd.DataFrame: ...

    def get_surfaces_for_building(self, building_feature_id: int) -> pd.DataFrame: ...

    def get_tabula_row(self, tabula_id: float) -> Optional[pd.Series]: ...


class LOD2Mapper:
    """Map LOD2 geometry + TABULA typology into canonical Building objects.

    Parameters
    ----------
    source : BuildingSource
        Any object implementing the ``BuildingSource`` protocol
        (``ExcelBuildingSource`` or ``PostgresBuildingSource``).
    country : str
        ISO country code for all buildings (default ``"DE"``).
    """

    def __init__(self, source: BuildingSource, country: str = "DE"):
        self.source = source
        self.country = country

    # ── public API ───────────────────────────────────────────────────────────

    def map_building(self, building_feature_id: int) -> Optional[Building]:
        """Map a single building from LOD2 + TABULA data.

        Parameters
        ----------
        building_feature_id : int
            The ``building_feature_id`` from the building table.

        Returns
        -------
        Building or None
            A fully assembled Building object, or ``None`` if the building
            cannot be mapped (missing TABULA data, no surfaces, etc.).
        """
        # 1. Look up building row
        bldg_df = self.source.buildings
        bldg_rows = bldg_df[bldg_df["building_feature_id"] == building_feature_id]
        if bldg_rows.empty:
            logger.warning("Building %d not found in building table", building_feature_id)
            return None
        bldg_row = bldg_rows.iloc[0]

        # 2. Look up TABULA row
        tabula_id = bldg_row.get("tabula_variant_code_id")
        tabula_row = self.source.get_tabula_row(tabula_id)
        if tabula_row is None:
            logger.warning(
                "Building %d: no TABULA match for tabula_variant_code_id=%s",
                building_feature_id, tabula_id,
            )
            return None

        # 3. Get child surfaces
        surfaces_df = self.source.get_surfaces_for_building(building_feature_id)
        if surfaces_df.empty:
            logger.warning("Building %d: no child surfaces found", building_feature_id)
            return None

        # 4. Classify surfaces into walls, roofs, floors
        walls_df = surfaces_df[surfaces_df["objectclass_id"] == OBJECTCLASS_WALL]
        roofs_df = surfaces_df[surfaces_df["objectclass_id"] == OBJECTCLASS_ROOF]
        floors_df = surfaces_df[surfaces_df["objectclass_id"] == OBJECTCLASS_GROUND]

        # 5. Select primary TABULA variants for each component type
        wall_U, wall_b = self._select_primary_variant(tabula_row, "Wall", n_variants=3)
        roof_U, roof_b = self._select_primary_variant(tabula_row, "Roof", n_variants=2)
        floor_U, floor_b = self._select_primary_variant(tabula_row, "Floor", n_variants=2)
        window_U = self._safe_float(tabula_row, "U_Window_1", 2.8)
        window_g_gl = self._safe_float(tabula_row, "g_gl_n_Window_1", 0.5)
        door_U = self._safe_float(tabula_row, "U_Door_1", 3.0)

        # 6. Build envelope elements
        elements: List[EnvelopeElement] = []
        wall_counter = 0
        roof_counter = 0
        floor_counter = 0

        # --- walls ---
        for _, row in walls_df.iterrows():
            wall_counter += 1
            azimuth = self._normalise_azimuth(row["azimuth"])
            elements.append(EnvelopeElement(
                id=f"wall_{wall_counter}",
                element_type="wall",
                area=float(row["surface_area"]),
                azimuth=azimuth,
                tilt=90.0,  # DB stores 0 for walls → v3 uses 90°
                U=wall_U,
                b_transmission=wall_b,
            ))

        # --- roofs ---
        for _, row in roofs_df.iterrows():
            roof_counter += 1
            tilt = self._convert_roof_tilt(row["tilt"])
            elements.append(EnvelopeElement(
                id=f"roof_{roof_counter}",
                element_type="roof",
                area=float(row["surface_area"]),
                azimuth=180.0,  # DB has -1 for roofs → use south-facing placeholder
                tilt=tilt,
                U=roof_U,
                b_transmission=roof_b,
            ))

        # --- floors ---
        for _, row in floors_df.iterrows():
            floor_counter += 1
            elements.append(EnvelopeElement(
                id=f"floor_{floor_counter}",
                element_type="floor",
                area=float(row["surface_area"]),
                azimuth=0.0,  # DB has -1 for floors → use 0° placeholder
                tilt=0.0,     # DB has -90 for floors → v3 uses 0°
                U=floor_U,
                b_transmission=floor_b,
            ))

        # --- windows (synthesised from TABULA directional areas) ---
        window_elements = self._synthesise_windows(
            tabula_row=tabula_row,
            walls_df=walls_df,
            window_U=window_U,
            window_g_gl=window_g_gl,
        )
        elements.extend(window_elements)

        # --- door (single element from TABULA) ---
        elements.append(EnvelopeElement(
            id="door_1",
            element_type="door",
            area=2.0,  # TABULA standard door area
            azimuth=0.0,
            tilt=90.0,
            U=door_U,
            b_transmission=1.0,
        ))

        # --- ventilation ---
        n_air_use = self._safe_float(tabula_row, "n_air_use", 0.5)
        elements.append(EnvelopeElement(
            id="vent_main",
            element_type="ventilation",
            area=0.0,
            azimuth=0.0,
            tilt=0.0,
            air_changes=n_air_use,
        ))

        # 7. Build identity
        building_type = self._extract_building_type(tabula_row)
        construction_period = self._extract_construction_period(tabula_row)
        neighbour_status = str(tabula_row.get("Code_AttachedNeighbours", "B_Alone"))
        n_storeys = int(bldg_row.get("number_of_storeys", 1) or 1)

        identity = BuildingIdentity(
            building_feature_id=str(building_feature_id),
            country=self.country,
            building_type=building_type,
            construction_period=construction_period,
            tabula_variant_code=str(bldg_row.get("tabula_variant_code", "")),
            n_storeys=n_storeys,
            neighbour_status=neighbour_status,
        )

        # 8. Build thermal properties
        thermal = ThermalProperties(
            n_air_infiltration=self._safe_float(tabula_row, "n_air_infiltration", 0.5),
            n_air_use=n_air_use,
            c_m=self._safe_float(tabula_row, "c_m", 165.0),
            h_room=self._safe_float(tabula_row, "h_room", 2.5),
            F_sh_hor=self._safe_float(tabula_row, "F_sh_hor", 0.8),
            F_sh_vert=self._safe_float(tabula_row, "F_sh_vert", 0.75),
            F_f=self._safe_float(tabula_row, "F_f", 0.2),
            F_w=self._safe_float(tabula_row, "F_w", 1.0),
            phi_int=self._safe_float(tabula_row, "phi_int", None),
        )

        # 9. Compute reference floor area from LOD2 floor areas
        a_ref = float(bldg_row.get("area_total_floor", 0.0) or 0.0)
        if a_ref == 0.0:
            a_ref = sum(float(r["surface_area"]) for _, r in floors_df.iterrows())

        return Building(
            identity=identity,
            elements=elements,
            thermal=thermal,
            A_ref=a_ref * max(n_storeys, 1),
        )

    def map_all(
        self,
        building_ids: Optional[List[int]] = None,
        limit: Optional[int] = None,
    ) -> List[Building]:
        """Map multiple buildings.

        Parameters
        ----------
        building_ids : list of int or None
            Specific building IDs to map.  If ``None``, maps all buildings.
        limit : int or None
            Maximum number of buildings to process.

        Returns
        -------
        list of Building
            Successfully mapped buildings (skipping those with errors).
        """
        if building_ids is None:
            building_ids = self.source.buildings["building_feature_id"].tolist()
        if limit is not None:
            building_ids = building_ids[:limit]

        buildings: List[Building] = []
        skipped = 0
        for bid in building_ids:
            bldg = self.map_building(bid)
            if bldg is not None:
                buildings.append(bldg)
            else:
                skipped += 1

        logger.info(
            "Mapped %d buildings (%d skipped) out of %d requested",
            len(buildings), skipped, len(building_ids),
        )
        return buildings

    # ── private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _select_primary_variant(
        tabula_row: pd.Series, component: str, n_variants: int
    ) -> Tuple[float, float]:
        """Select the primary TABULA variant for a component type.

        Picks the variant with the largest area that has b_transmission > 0.
        Falls back to variant 1 if no variant qualifies.

        Parameters
        ----------
        tabula_row : pd.Series
            A single TABULA row.
        component : str
            Component name: ``"Wall"``, ``"Roof"``, or ``"Floor"``.
        n_variants : int
            Number of variants to check (e.g. 3 for walls, 2 for roof/floor).

        Returns
        -------
        tuple of (U_value, b_transmission)
        """
        best_area = -1.0
        best_U = 1.0
        best_b = 1.0

        for i in range(1, n_variants + 1):
            area_col = f"A_{component}_{i}"
            u_col = f"U_{component}_{i}"
            b_col = f"b_Transmission_{component}_{i}"

            area = float(tabula_row.get(area_col, 0.0) or 0.0)
            b_val = float(tabula_row.get(b_col, 0.0) or 0.0)

            if b_val > 0 and area > best_area:
                best_area = area
                best_U = float(tabula_row.get(u_col, 1.0) or 1.0)
                best_b = b_val

        # Fallback: if no variant had b > 0, use variant 1
        if best_area < 0:
            best_U = float(tabula_row.get(f"U_{component}_1", 1.0) or 1.0)
            best_b = float(tabula_row.get(f"b_Transmission_{component}_1", 1.0) or 1.0)

        return best_U, best_b

    @staticmethod
    def _synthesise_windows(
        tabula_row: pd.Series,
        walls_df: pd.DataFrame,
        window_U: float,
        window_g_gl: float,
    ) -> List[EnvelopeElement]:
        """Create window elements from TABULA directional window areas.

        TABULA provides total window areas per direction (N/S/E/W + Horizontal).
        These are distributed proportionally across wall surfaces facing each
        direction, then one window element is created per non-zero direction.

        Parameters
        ----------
        tabula_row : pd.Series
            TABULA typology row.
        walls_df : pd.DataFrame
            LOD2 wall surfaces for this building.
        window_U : float
            Window U-value [W/(m²K)].
        window_g_gl : float
            Window solar heat gain coefficient.

        Returns
        -------
        list of EnvelopeElement
            Window elements (one per cardinal direction with area > 0).
        """
        windows: List[EnvelopeElement] = []
        counter = 0

        # Directional window areas from TABULA
        dir_areas = {
            "north": float(tabula_row.get("A_Window_North", 0.0) or 0.0),
            "east": float(tabula_row.get("A_Window_East", 0.0) or 0.0),
            "south": float(tabula_row.get("A_Window_South", 0.0) or 0.0),
            "west": float(tabula_row.get("A_Window_West", 0.0) or 0.0),
        }

        # Horizontal windows (skylights) — add to roof-facing windows
        horizontal = float(tabula_row.get("A_Window_Horizontal", 0.0) or 0.0)

        # Find parent wall IDs per direction for proper linkage
        wall_ids_by_dir = _classify_walls_by_direction(walls_df)

        for direction, (label, centre_az, _, _) in zip(
            ["north", "east", "south", "west"], _DIRECTION_BINS
        ):
            area = dir_areas.get(direction, 0.0)
            if area <= 0:
                continue

            counter += 1
            # Link to the first wall in this direction, if any
            parent_walls = wall_ids_by_dir.get(direction, [])
            parent_id = parent_walls[0] if parent_walls else None

            windows.append(EnvelopeElement(
                id=f"win_{direction}",
                element_type="window",
                area=area,
                azimuth=centre_az,
                tilt=90.0,
                U=window_U,
                g_gl=window_g_gl,
                surface=parent_id,
            ))

        # Horizontal/skylight windows
        if horizontal > 0:
            counter += 1
            windows.append(EnvelopeElement(
                id="win_horizontal",
                element_type="window",
                area=horizontal,
                azimuth=180.0,
                tilt=0.0,  # horizontal
                U=window_U,
                g_gl=window_g_gl,
            ))

        return windows

    @staticmethod
    def _normalise_azimuth(azimuth: float) -> float:
        """Convert DB azimuth to 0–360° range.

        The database stores -1 for roofs/floors (handled elsewhere).
        Wall azimuths are real compass bearings but may need normalisation.
        """
        if pd.isna(azimuth) or azimuth < 0:
            return 0.0
        return float(azimuth) % 360.0

    @staticmethod
    def _convert_roof_tilt(db_tilt: float) -> float:
        """Convert DB roof tilt to v3 convention (0–90°).

        The DB stores the actual measured tilt angle, which can be
        near 90° for steep roofs.  We clamp to [0, 90] range.
        """
        if pd.isna(db_tilt):
            return 30.0  # default pitched roof
        tilt = abs(float(db_tilt))
        # DB stores values like 88.28° — convert to angle from horizontal
        # In the DB, 90° means vertical. For roofs, the v3 tilt is from horizontal.
        # A nearly-vertical tilt in the DB represents a steep surface.
        return min(max(tilt, 0.0), 90.0)

    @staticmethod
    def _extract_building_type(tabula_row: pd.Series) -> str:
        """Extract building size class from TABULA (SFH, MFH, TH, AB)."""
        code = str(tabula_row.get("Code_BuildingSizeClass", ""))
        # Map TABULA codes to standard abbreviations
        mapping = {"SFH": "SFH", "MFH": "MFH", "TH": "TH", "AB": "AB"}
        return mapping.get(code, code)

    @staticmethod
    def _extract_construction_period(tabula_row: pd.Series) -> str:
        """Extract construction year class from TABULA."""
        return str(tabula_row.get("Code_ConstructionYearClass", ""))

    @staticmethod
    def _safe_float(
        row: pd.Series, col: str, default: Optional[float]
    ) -> Optional[float]:
        """Read a float from a Series, returning *default* on NaN/missing."""
        val = row.get(col)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return default
        return float(val)


# ── module-level helpers ─────────────────────────────────────────────────────


def _classify_walls_by_direction(
    walls_df: pd.DataFrame,
) -> dict[str, list[str]]:
    """Group wall element IDs by cardinal direction.

    Uses the wall azimuth values to assign each wall to the nearest
    cardinal direction bin (N/E/S/W).

    Returns
    -------
    dict mapping direction name → list of wall element IDs (wall_1, wall_2, …)
    """
    result: dict[str, list[str]] = {
        "north": [], "east": [], "south": [], "west": [],
    }
    for idx, (_, row) in enumerate(walls_df.iterrows(), start=1):
        azimuth = float(row.get("azimuth", 0))
        if azimuth < 0 or pd.isna(azimuth):
            continue
        azimuth = azimuth % 360.0
        wall_id = f"wall_{idx}"
        for direction, centre, lower, upper in _DIRECTION_BINS:
            if direction == "north":
                # North wraps around 0°
                if azimuth >= lower or azimuth < upper:
                    result[direction].append(wall_id)
                    break
            else:
                if lower <= azimuth < upper:
                    result[direction].append(wall_id)
                    break

    return result
