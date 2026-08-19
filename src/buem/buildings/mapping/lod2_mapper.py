"""
LOD2 + TABULA → Building mapper (orchestration).

Reads raw DataFrames from any ``BuildingSource`` (Excel or PostgreSQL) and
produces a list of canonical ``Building`` objects ready for v3 JSON generation.

This module orchestrates the mapping pipeline.  Domain-specific logic is
delegated to focused helper modules:

- **element_factory** — window, door, ventilation element creation
- **tabula_helpers** — TABULA variant selection, window ratios, safe numerics
- **wall_classifier** — shared (party) wall detection

Table linkages
--------------
- ``lod2_building_feature.building_feature_id`` → ``lod2_child_feature_surface.building_feature_id``  (1:N)
- ``lod2_building_feature.tabula_variant_code_id`` → ``tabula.id``  (N:1)

Surface classification
----------------------
- ``objectclass_id = 709`` → WallSurface  (tilt always 90°; azimuth from DB, −1 → 0°)
- ``objectclass_id = 710`` → GroundSurface (tilt always 0°; azimuth always 0°)
- ``objectclass_id = 712`` → RoofSurface  (tilt: DB≥0 → as-is, DB<0 → 0°; azimuth always 0°)

Party-wall detection
--------------------
A wall is *shared* (party wall) when its ``surface_feature_id`` appears under
two or more ``building_feature_id`` values.  For shared walls:

- ``U = 0``  (adjacent heated space — no net heat transfer)
- ``b_transmission = 0``
- No windows, doors, or ventilation openings on shared walls

Front / back wall identification
--------------------------------
After filtering out party walls, the **front wall** is the exposed wall with the
largest area.  The **back wall** is the exposed wall whose azimuth is closest
to 180° opposite the front wall's azimuth (within a 90° tolerance; if no
candidate is close enough, there is no back wall).  See
:func:`~buem.buildings.mapping.element_factory.identify_front_back`.

Window / door / ventilation sizing
-----------------------------------
Window and door areas are **proportional** to actual LOD2 wall areas via TABULA
ratios.  Ventilation openings (1.0 m² front, 0.5 m² back) are capped at 10 %
of wall area and subtracted from the wall's opaque area.  See
:func:`~buem.buildings.mapping.element_factory.synthesize_openings` — this
same function (and the same documented rules) also drives the live
request-handling path when a caller doesn't supply its own window/door/
ventilation detail; see :mod:`buem.buildings.mapping.live_synthesis`.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

import pandas as pd

from buem.buildings.building import Building, BuildingIdentity, ThermalProperties
from buem.buildings.components.base import EnvelopeElement
from buem.buildings.mapping import geometry_utils
from buem.buildings.mapping.element_factory import (
    WallInfo,
    identify_front_back,
    synthesize_openings,
    uniform_window_ratios,
)
from buem.buildings.mapping.tabula_helpers import (
    apply_refurbishment_measures,
    safe_series_float,
    select_primary_variant,
)
from buem.buildings.mapping.wall_classifier import SharedWallDetector

logger = logging.getLogger(__name__)


# ── objectclass_id → element type ────────────────────────────────────────────
OBJECTCLASS_WALL = 709
OBJECTCLASS_GROUND = 710
OBJECTCLASS_ROOF = 712


class BuildingSource(Protocol):
    """Minimal interface for data sources (Excel or PostgreSQL)."""

    @property
    def buildings(self) -> pd.DataFrame: ...

    @property
    def surfaces(self) -> pd.DataFrame: ...

    @property
    def tabula(self) -> pd.DataFrame: ...

    def get_surfaces_for_building(self, building_feature_id: int) -> pd.DataFrame: ...

    def get_tabula_row(self, tabula_id: float) -> pd.Series | None: ...


class LOD2Mapper:
    """Map LOD2 geometry + TABULA typology into canonical Building objects.

    Parameters
    ----------
    source : BuildingSource
        Any object implementing the ``BuildingSource`` protocol
        (``ExcelBuildingSource``, ``PostgresBuildingSource``, or
        ``CsvBuildingSource``).
    country : str
        ISO country code for all buildings (default ``"DE"``).
    u_value_overrides : pd.DataFrame or None
        Optional editable U-value table (2026-08-17, e.g.
        ``src/buem/data/buildings/netherlands/u_value_reference.csv`` --
        see that file and ``nl_archetype_mapper``'s module docstring for
        why this exists: TABULA's own per-row U-values are trustworthy,
        but the user asked for "a clean table... providing U values that
        users can easily change if needed" -- a plain, small,
        human-editable CSV rather than a 200-column TABULA row). Must
        have columns ``construction_year_class``, ``building_type``,
        ``U_Wall``, ``U_Roof``, ``U_Floor``, ``U_Window``, ``U_Door``.
        When a building's resolved TABULA row's own
        ``Code_ConstructionYearClass``/``Code_BuildingSizeClass`` matches
        a row here, these values are used *instead of* that TABULA row's
        own ``U_Wall_1``/etc. (transmission factors and every other
        thermal parameter still come from the real TABULA row
        unchanged). ``None`` (default) preserves the original behavior
        exactly -- no effect on the German path.
    """

    def __init__(
        self, source: BuildingSource, country: str = "DE",
        u_value_overrides: pd.DataFrame | None = None,
    ):
        self.source = source
        self.country = country
        self.u_value_overrides = u_value_overrides
        # Pre-compute shared wall set once across the full surface table
        self._shared_detector = SharedWallDetector(source.surfaces)

    # ── public API ───────────────────────────────────────────────────────────

    def map_building(self, building_feature_id: int) -> Building | None:
        """Map a single building from LOD2 + TABULA data.

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
        #    Skip near-zero-area surfaces (LOD2 geometry artefacts, e.g. 1e-16 m²)
        valid = surfaces_df[surfaces_df["surface_area"] > 0.01]
        walls_df = valid[valid["objectclass_id"] == OBJECTCLASS_WALL]
        roofs_df = valid[valid["objectclass_id"] == OBJECTCLASS_ROOF]
        floors_df = valid[valid["objectclass_id"] == OBJECTCLASS_GROUND]

        # 5. Select primary TABULA variants for each component type
        wall_U, wall_b = select_primary_variant(tabula_row, "Wall", n_variants=3)
        roof_U, roof_b = select_primary_variant(tabula_row, "Roof", n_variants=2)
        floor_U, floor_b = select_primary_variant(tabula_row, "Floor", n_variants=2)
        window_U = safe_series_float(tabula_row, "U_Window_1", 2.8)
        window_g_gl = safe_series_float(tabula_row, "g_gl_n_Window_1", 0.5)
        door_U = safe_series_float(tabula_row, "U_Door_1", 3.0)

        # 5b. Apply the editable U-value override table, if one was given
        # and this building's resolved archetype has a matching row --
        # b_transmission and every other TABULA parameter are untouched.
        if self.u_value_overrides is not None:
            override_row = self._lookup_u_value_override(tabula_row)
            if override_row is not None:
                wall_U = float(override_row["U_Wall"])
                roof_U = float(override_row["U_Roof"])
                floor_U = float(override_row["U_Floor"])
                window_U = float(override_row["U_Window"])
                door_U = float(override_row["U_Door"])

        # 5c. Apply the matched variant row's own refurbishment measures
        # (a no-op for as-built variant rows, whose measure columns are
        # all zero). Applied after the override table so added insulation
        # compounds with whichever base U-value is in effect.
        adjusted = apply_refurbishment_measures(tabula_row, {
            "Wall": wall_U, "Roof": roof_U, "Floor": floor_U,
            "Window": window_U, "Door": door_U,
        })
        wall_U, roof_U, floor_U = adjusted["Wall"], adjusted["Roof"], adjusted["Floor"]
        window_U, door_U = adjusted["Window"], adjusted["Door"]

        # 6. Classify walls into shared (party) vs exposed
        wall_infos = self._classify_walls(walls_df)
        exposed_walls = [w for w in wall_infos if not w.is_shared]

        logger.debug(
            "Building %d: %d walls (%d exposed, %d shared)",
            building_feature_id, len(wall_infos),
            len(exposed_walls), len(wall_infos) - len(exposed_walls),
        )

        # 7. Identify front wall (largest exposed) and back wall (opposite)
        front_wall, back_wall = identify_front_back(exposed_walls)

        # 8. Compute proportional window/door ratios from TABULA, then
        #    synthesize window/door/ventilation elements (shared with the
        #    live request-handling path — see element_factory.synthesize_openings).
        a_wall_1 = safe_series_float(tabula_row, "A_Wall_1", 0.0)
        # Windows are sized from each wall's own area, not from TABULA's
        # per-direction window columns -- see
        # element_factory.uniform_window_ratios(). Doors still use
        # TABULA's own door-to-wall ratio, which carries no orientation
        # assumption.
        win_ratios = uniform_window_ratios()
        door_ratio = (
            safe_series_float(tabula_row, "A_Door_1", 0.0) / a_wall_1
            if a_wall_1 > 0 else 0.0
        )
        horizontal = safe_series_float(tabula_row, "A_Window_Horizontal", 0.0)
        n_air_use = safe_series_float(tabula_row, "n_air_use", 0.5)

        opening_elements = synthesize_openings(
            exposed_walls, front_wall, back_wall,
            window_ratios=win_ratios,
            door_ratio=door_ratio,
            window_U=window_U,
            window_g_gl=window_g_gl,
            door_U=door_U,
            n_air_use=n_air_use,
            horizontal_window_area=horizontal,
        )

        # 9. Build envelope elements
        #    (steps 10-12 follow below: identity, thermal, A_ref)
        elements: list[EnvelopeElement] = []

        # --- walls (shared → U=0, exposed → net area after openings) ---
        for w in wall_infos:
            if w.is_shared:
                elements.append(EnvelopeElement(
                    id=w.wall_id,
                    element_type="wall",
                    area=w.area,
                    azimuth=w.azimuth,
                    tilt=90.0,
                    U=0.0,
                    b_transmission=0.0,
                ))
            else:
                elements.append(EnvelopeElement(
                    id=w.wall_id,
                    element_type="wall",
                    area=w.net_area,
                    azimuth=w.azimuth,
                    tilt=90.0,
                    U=wall_U,
                    b_transmission=wall_b,
                ))

        # --- roofs ---
        for roof_counter, (_, row) in enumerate(roofs_df.iterrows(), start=1):
            tilt = self._convert_roof_tilt(row["tilt"])
            # Real azimuth, not a placeholder (fixed 2026-08-18): model_buem
            # ._calcRadiation() passes every element's own tilt AND azimuth
            # through pvlib.irradiance.get_total_irradiance() -- roof solar
            # gain is NOT azimuth-independent in the actual model, so a
            # hardcoded 0.0 here silently modeled every non-flat German
            # roof as due-north-facing. The source DB has real azimuth for
            # 10,732/16,558 (64.8%) of German roof surfaces (checked
            # directly, not assumed) -- the same negative/NaN "unknown"
            # sentinel walls already handle is normalised here too.
            roof_azimuth = self._normalise_azimuth(row["azimuth"])
            elements.append(EnvelopeElement(
                id=f"roof_{roof_counter}",
                element_type="roof",
                area=float(row["surface_area"]),
                azimuth=roof_azimuth,
                tilt=tilt,
                U=roof_U,
                b_transmission=roof_b,
            ))

        # --- floors ---
        for floor_counter, (_, row) in enumerate(floors_df.iterrows(), start=1):
            elements.append(EnvelopeElement(
                id=f"floor_{floor_counter}",
                element_type="floor",
                area=float(row["surface_area"]),
                azimuth=0.0,  # DB has -1 for floors → use 0° placeholder
                tilt=0.0,     # DB has -90 for floors → v3 uses 0°
                U=floor_U,
                b_transmission=floor_b,
            ))

        # --- windows, door, ventilation (computed together in step 8 above) ---
        elements.extend(opening_elements)

        # 10. Build identity
        building_type = self._extract_building_type(tabula_row)
        construction_period = self._extract_construction_period(tabula_row)
        neighbour_status = str(tabula_row.get("Code_AttachedNeighbours", "B_Alone"))
        n_storeys = int(bldg_row.get("number_of_storeys", 1) or 1)

        identity_kwargs: dict[str, Any] = {
            "building_feature_id": str(building_feature_id),
            "country": self.country,
            "building_type": building_type,
            "construction_period": construction_period,
            "tabula_variant_code": str(bldg_row.get("tabula_variant_code", "")),
            "n_storeys": n_storeys,
            "neighbour_status": neighbour_status,
        }
        # Real (latitude, longitude) from the source row's own geometry,
        # when available -- previously never wired in here (see
        # .claude/residential/open.md, found 2026-08-16 via a building
        # that got weather fetched at the wrong country entirely because
        # of this exact gap), so every LOD2Mapper-mapped building silently
        # kept BuildingIdentity's class default (52.0, 5.0) regardless of
        # its real location. Harmless while it was combined with "no NL
        # building could be mapped at all" (no TABULA match); closing it
        # now that TABULA matching makes that combination possible.
        latlon = geometry_utils.building_lat_lon(bldg_row)
        if latlon is not None:
            identity_kwargs["latitude"], identity_kwargs["longitude"] = latlon

        identity = BuildingIdentity(**identity_kwargs)

        # 11. Build thermal properties
        thermal = ThermalProperties(
            n_air_infiltration=safe_series_float(tabula_row, "n_air_infiltration", 0.5),
            n_air_use=n_air_use,
            c_m=safe_series_float(tabula_row, "c_m", 165.0),
            h_room=safe_series_float(tabula_row, "h_room", 2.5),
            F_sh_hor=safe_series_float(tabula_row, "F_sh_hor", 0.8),
            F_sh_vert=safe_series_float(tabula_row, "F_sh_vert", 0.75),
            F_f=safe_series_float(tabula_row, "F_f", 0.2),
            F_w=safe_series_float(tabula_row, "F_w", 1.0),
            phi_int=safe_series_float(tabula_row, "phi_int", None),
            q_w_nd=safe_series_float(tabula_row, "q_w_nd", None),
            design_T_min=safe_series_float(tabula_row, "Theta_e", -12.0),
            F_red_htr=safe_series_float(tabula_row, "F_red_htr1", 1.0),
            # Comfort setpoints are deliberately left at buem's own
            # defaults rather than taken from the matched archetype's
            # `theta_i`. TABULA's theta_i is the setpoint its *reference
            # calculation* assumes (a constant 20 degC across every Dutch
            # archetype, so it carries no per-building information here),
            # whereas buem's default represents observed occupant
            # behavior -- see building_registry.DEFAULT_COMFORT_T_LB.
        )

        # 12. Compute reference floor area from LOD2 floor areas
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
        building_ids: list[int] | None = None,
        limit: int | None = None,
    ) -> list[Building]:
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

        buildings: list[Building] = []
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

    # ── wall classification ──────────────────────────────────────────────────

    def _classify_walls(self, walls_df: pd.DataFrame) -> list[WallInfo]:
        """Classify each wall as shared (party) or exposed using surface_feature_id.

        Returns a list of ``WallInfo`` in the same iteration order as the
        input DataFrame, with sequential IDs ``wall_1``, ``wall_2``, etc.
        Logs a warning when an exposed wall has a negative (unknown) azimuth.
        """
        result: list[WallInfo] = []
        for idx, (_, row) in enumerate(walls_df.iterrows(), start=1):
            sfid = int(row["surface_feature_id"])
            raw_az = row["azimuth"]
            azimuth = self._normalise_azimuth(raw_az)
            is_shared = self._shared_detector.is_shared(sfid)
            azimuth_unknown = pd.notna(raw_az) and float(raw_az) < 0

            # Log negative azimuth conversion for traceability. The
            # fallback value itself (0°/north) is no longer trusted for
            # window/door placement on an exposed wall -- see WallInfo
            # .azimuth_known and synthesize_openings() -- this wall still
            # counts fully toward opaque envelope area/conductance either
            # way, just not toward where openings go.
            if azimuth_unknown:
                if is_shared:
                    logger.debug(
                        "wall_%d (sfid=%d): shared wall azimuth %.1f → 0°",
                        idx, sfid, float(raw_az),
                    )
                else:
                    logger.warning(
                        "wall_%d (sfid=%d): EXPOSED wall azimuth %.1f unknown "
                        "-- excluded from window/door placement (still counted "
                        "as opaque envelope area).",
                        idx, sfid, float(raw_az),
                    )

            result.append(WallInfo(
                wall_id=f"wall_{idx}",
                surface_feature_id=sfid,
                area=float(row["surface_area"]),
                azimuth=azimuth,
                is_shared=is_shared,
                # Shared walls never reach window/door placement anyway
                # (filtered to exposed-only before synthesize_openings()
                # runs), so this only matters for exposed walls -- kept
                # unconditional rather than re-deriving that filter here.
                azimuth_known=not azimuth_unknown,
            ))
        return result

    def _lookup_u_value_override(self, tabula_row: pd.Series) -> pd.Series | None:
        """Find this building's row in ``self.u_value_overrides``, matched
        on the resolved TABULA row's own ``Code_ConstructionYearClass``/
        ``Code_BuildingSizeClass`` -- or ``None`` if no override table was
        given, or none of its rows match. See ``__init__``'s
        ``u_value_overrides`` docstring.
        """
        assert self.u_value_overrides is not None  # only called when set
        year_class = tabula_row.get("Code_ConstructionYearClass")
        building_type = tabula_row.get("Code_BuildingSizeClass")
        if pd.isna(year_class) or pd.isna(building_type):
            return None
        matches = self.u_value_overrides[
            (self.u_value_overrides["construction_year_class"] == year_class)
            & (self.u_value_overrides["building_type"] == building_type)
        ]
        if matches.empty:
            return None
        return matches.iloc[0]

    # ── generic helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _normalise_azimuth(azimuth: float) -> float:
        """Convert DB azimuth to 0–360° range.

        Negative or NaN values are mapped to 0° (North).  A warning is
        logged by ``_classify_walls`` when this affects an exposed wall.
        """
        if pd.isna(azimuth) or azimuth < 0:
            return 0.0
        return float(azimuth) % 360.0

    @staticmethod
    def _convert_roof_tilt(db_tilt: float) -> float:
        """Convert DB roof tilt to pvlib convention [0, 90]°.

        The DB already stores tilt in pvlib convention (0° = horizontal,
        90° = vertical).  Negative values (2,524 roof surfaces) are
        treated as 0° (flat) until a better correction is available.
        """
        if pd.isna(db_tilt) or db_tilt < 0:
            return 0.0  # negative or missing → flat roof
        return min(float(db_tilt), 90.0)

    @staticmethod
    def _extract_building_type(tabula_row: pd.Series) -> str:
        """Extract building size class from TABULA (SFH, MFH, TH, AB)."""
        return str(tabula_row.get("Code_BuildingSizeClass", ""))

    @staticmethod
    def _extract_construction_period(tabula_row: pd.Series) -> str:
        """Extract construction year class from TABULA."""
        return str(tabula_row.get("Code_ConstructionYearClass", ""))

