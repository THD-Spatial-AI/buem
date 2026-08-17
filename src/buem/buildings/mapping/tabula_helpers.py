"""
TABULA typology helper functions.

Extracted from ``lod2_mapper.py`` to keep the mapper focused on orchestration.
These functions handle TABULA variant selection, window-to-wall ratio
computation, and safe numeric extraction from pandas Series.

TABULA variant selection
------------------------
Each component type (wall, roof, floor) may have multiple TABULA variants
(Wall_1/2/3, Roof_1/2, Floor_1/2) with different U-values and b_transmission
factors.  Only the *primary exterior variant* — the one with the largest area
and b_transmission > 0 — is used for LOD2 surfaces.

Window ratios
-------------
Window areas are proportional: ``A_Window_<Dir> / A_Wall_1``, so glazing
scales with the actual building geometry rather than the TABULA archetype's
reference areas.
"""

from __future__ import annotations

import functools
import logging
import math
from typing import overload

import pandas as pd

logger = logging.getLogger(__name__)


@overload
def safe_series_float(row: pd.Series, col: str, default: float) -> float: ...
@overload
def safe_series_float(row: pd.Series, col: str, default: None) -> float | None: ...
def safe_series_float(row: pd.Series, col: str, default: float | None) -> float | None:
    """Read a float from a pandas Series, returning *default* on NaN/missing.

    Parameters
    ----------
    row : pd.Series
        A TABULA or building row.
    col : str
        Column / field name.
    default : float | None
        Value to return when the column is absent, ``None``, or ``NaN``.
    """
    val = row.get(col)
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return default
    return float(val)


def select_primary_variant(
    tabula_row: pd.Series, component: str, n_variants: int
) -> tuple[float, float]:
    """Select the primary TABULA variant for a component type.

    Picks the variant with the largest area that has ``b_transmission > 0``.
    Falls back to variant 1 if no variant qualifies.

    Parameters
    ----------
    tabula_row : pd.Series
        A single TABULA row.
    component : str
        Component base name: ``"Wall"``, ``"Roof"``, or ``"Floor"``.
    n_variants : int
        Number of TABULA variants for this component type (e.g. 3 for walls).

    Returns
    -------
    tuple of (U_value, b_transmission)
        U-value [W/(m²K)] and b_transmission factor [-] of the selected variant.
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


def compute_window_ratios(
    tabula_row: pd.Series, a_wall_1: float
) -> dict[str, float]:
    """Compute per-direction window-to-wall area ratios from TABULA.

    Returns a dict ``{"north": ratio, "east": ratio, …}`` where each
    ratio is ``A_Window_<Dir> / A_Wall_1``.  Returns all zeros if
    ``A_Wall_1`` is zero or missing.

    Parameters
    ----------
    tabula_row : pd.Series
        A single TABULA row.
    a_wall_1 : float
        TABULA reference wall area [m²] (``A_Wall_1``).
    """
    if a_wall_1 <= 0:
        return {"north": 0.0, "east": 0.0, "south": 0.0, "west": 0.0}
    return {
        "north": safe_series_float(tabula_row, "A_Window_North", 0.0) / a_wall_1,
        "east":  safe_series_float(tabula_row, "A_Window_East",  0.0) / a_wall_1,
        "south": safe_series_float(tabula_row, "A_Window_South", 0.0) / a_wall_1,
        "west":  safe_series_float(tabula_row, "A_Window_West",  0.0) / a_wall_1,
    }


def azimuth_diff(a: float, b: float) -> float:
    """Signed shortest angular difference between two azimuths (−180, 180]."""
    d = (a - b) % 360.0
    return d - 360.0 if d > 180.0 else d


def azimuth_to_direction(azimuth: float) -> str:
    """Map an azimuth (0–360°) to the nearest cardinal direction label.

    Bins
    ----
    - north:  [315, 360) ∪ [0, 45)
    - east:   [45, 135)
    - south:  [135, 225)
    - west:   [225, 315)
    """
    az = azimuth % 360.0
    if az >= 315.0 or az < 45.0:
        return "north"
    if az < 135.0:
        return "east"
    if az < 225.0:
        return "south"
    return "west"


# ── TABULA archetype lookup (live request-handling path) ────────────────────
#
# LOD2Mapper resolves a TABULA row via a numeric FK already attached to a
# specific LOD2 building (``tabula_variant_code_id`` -> ``tabula.id``). The
# live request-handling path (buem.buildings.mapping.live_synthesis) has no
# such per-building link -- only whatever building_type/construction_period/
# country a caller supplied -- so it needs to *match* a row instead. Both
# read the same bundled reference workbook LOD2Mapper's own ExcelBuildingSource
# uses, so results are identical to the offline pipeline whenever a match is
# found.


@functools.lru_cache(maxsize=1)
def _tabula_reference_sheet() -> pd.DataFrame:
    """Lazily load and cache the bundled TABULA reference sheet.

    Loaded on first use (not at import time) so importing this module -- or
    anything importing ``cfg_building.py``, which now calls
    :func:`lookup_tabula_archetype` on every request -- doesn't pay this
    cost unless a live request actually needs a TABULA-based lookup (i.e.
    the caller omitted window/door/ventilation detail).
    """
    # Local imports: avoids a module-level dependency from this
    # previously pandas-only helper module onto the datasources/pipeline
    # packages for callers that never need the archetype lookup.
    from buem.buildings.datasources.excel_source import ExcelBuildingSource
    from buem.buildings.pipeline import DEFAULT_WORKBOOK

    return ExcelBuildingSource(DEFAULT_WORKBOOK).tabula


def lookup_tabula_archetype(
    building_type: str,
    construction_period: str | None,
    country: str | None,
    *,
    bldg_tabula_id: str | None = None,
    sheet: pd.DataFrame | None = None,
) -> pd.Series | None:
    """Resolve a TABULA archetype row for the live (non-LOD2) synthesis path.

    Tries an explicit ``bldg_tabula_id`` first (a full ``Code_BuildingVariant``
    string, e.g. ``"DE.N.MFH.03.Gen.ReEx.001.001"``), then falls back to
    matching ``country`` + ``building_type`` + ``construction_period``
    against the bundled reference sheet's ``Code_Country`` /
    ``Code_BuildingSizeClass`` / ``Code_ConstructionYearClass`` columns --
    the same sheet :class:`~buem.buildings.datasources.excel_source.
    ExcelBuildingSource`/``LOD2Mapper`` use.

    Parameters
    ----------
    sheet : pd.DataFrame or None
        The TABULA reference table to search. Defaults to the bundled
        German Excel workbook's sheet (cached, lazily loaded) for
        backward compatibility with existing callers. Pass the
        Netherlands ``tabula.csv`` (``CsvBuildingSource(...).tabula``,
        real Dutch archetype data, ``Code_Country == "NL"``) to resolve
        against that instead -- added 2026-08-17 for
        ``nl_archetype_mapper``, which needs the *same* selection logic
        (prefer a ``.Gen.`` variant, lowest ``id`` for determinism)
        against a different table, not a reimplementation of it.

    ``construction_period`` is accepted either as TABULA's own
    country-prefixed class code (``"DE.04"``) or the bare class code
    (``"04"``, prefixed with ``country`` here) -- EnerPlanET's v3/v4 both
    send the bare form. A literal year-range string (e.g. ``"1965-1974"``,
    still used by some of buem's own example data -- see CLAUDE.md's
    "v2 vs v3/v4 request formats" note) will not match anything and
    correctly falls through to ``None``.

    Returns
    -------
    pd.Series or None
        The best-matching TABULA row, or ``None`` if nothing matches (e.g.
        the bundled sheet currently only covers ``Code_Country == "DE"``).
        Callers should fall back to the documented safe-default ratios in
        that case -- see buildings.rst "Missing TABULA values use safe
        defaults" -- exactly as for any other missing TABULA value.

    Among multiple matches (refurbishment states, sub-variants), prefers a
    generic (``".Gen."``) variant, then the lowest ``id`` for determinism.
    """
    if sheet is None:
        try:
            sheet = _tabula_reference_sheet()
        except (OSError, ValueError) as exc:
            logger.warning("TABULA archetype reference sheet could not be loaded: %s", exc)
            return None

    if bldg_tabula_id:
        matches = sheet[sheet["Code_BuildingVariant"] == bldg_tabula_id]
        if not matches.empty:
            return matches.sort_values("id").iloc[0]
        logger.warning(
            "bldg_tabula_id=%r did not match any row in the bundled TABULA "
            "reference sheet; falling back to building_type/construction_period"
            "/country matching.", bldg_tabula_id,
        )

    if not building_type or not construction_period or not country:
        return None

    year_class = (
        construction_period if "." in construction_period
        else f"{country}.{construction_period}"
    )
    matches = sheet[
        (sheet["Code_Country"] == country)
        & (sheet["Code_BuildingSizeClass"] == building_type)
        & (sheet["Code_ConstructionYearClass"] == year_class)
    ]
    if matches.empty:
        return None

    generic = matches[matches["Code_BuildingVariant"].str.contains(r"\.Gen\.", regex=True, na=False)]
    if not generic.empty:
        matches = generic
    return matches.sort_values("id").iloc[0]
