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

import math

import pandas as pd


def safe_series_float(row: pd.Series, col: str, default: float) -> float:
    """Read a float from a pandas Series, returning *default* on NaN/missing.

    Parameters
    ----------
    row : pd.Series
        A TABULA or building row.
    col : str
        Column / field name.
    default : float
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
