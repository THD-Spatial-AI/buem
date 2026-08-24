"""
CSV-based building data source.

Loads building data from three plain CSV files — a direct export of the
same three tables ``ExcelBuildingSource``/``PostgresBuildingSource`` read
from an Excel workbook or a live Postgres connection:

  - ``lod2_building_feature.csv``          -> building-level aggregates
  - ``lod2_child_feature_surface.csv``     -> per-surface geometry (with
    pre-computed ``surface_area``/``tilt``/``azimuth``/``height`` columns
    -- **not** the raw, un-enriched ``lod2_child_feature.csv`` shape some
    exports produce, which carries only a raw ``geom`` blob and nothing
    ``LOD2Mapper`` can use directly; see the 2026-08-16 Netherlands data
    incident in ``.claude/residential/resolved.md`` for why this
    distinction matters)
  - ``tabula.csv``                         -> TABULA typology, any country

The DataFrames produced are column-compatible with ``ExcelBuildingSource``/
``PostgresBuildingSource`` so downstream mapping code (``LOD2Mapper``,
``building_selection.py``, ``batch.py``) works identically regardless of
data origin -- this exists specifically so a country without a bundled
Excel workbook or a live Postgres connection (e.g. a one-off CSV export
for a new region) can still go through the exact same pipeline.

CSV quirks handled explicitly, matching what a Postgres/pgAdmin CSV
export actually produces (confirmed against the real Netherlands/Loenen
export this loader was built for):

- Literal ``NULL`` text (not an empty field) for SQL NULLs -- parsed as
  a real ``NaN``, not left as the string ``"NULL"``.
- ``building_feature_id``/``surface_feature_id``/``tabula_variant_code_id``
  coerced to nullable integer dtype (``Int64``) -- these are compared
  against plain Python ``int`` elsewhere (``LOD2Mapper.map_building()``),
  and a CSV round-trip through a column with any missing values would
  otherwise infer ``float64``, which does not compare equal to ``int``
  the way ``pd.read_excel``'s dtype inference usually does.
- **Delimiter/decimal convention auto-detected per file**, not assumed
  comma+period. Found the hard way (2026-08-16): a re-export of the
  Netherlands surfaces table arrived semicolon-delimited with European
  decimal commas (``10,412`` for 10.412, common for a European-locale
  export tool) -- silently parsing that with comma/period assumptions
  doesn't raise (pandas dutifully reads each semicolon-delimited line as
  one giant single-column string) until something *downstream* breaks in
  a confusing way. Detected by comparing how many columns a comma split
  vs. a semicolon split of the header line produces; whichever matches
  header field count more plausibly wins. See ``.claude/residential/
  resolved.md`` for the fuller incident writeup, including why this
  mattered for real: the file this was found on turned out to be missing
  ~45% of its true rows under the old (correct-format, but truncated)
  export it replaced.
- **Surface rows are deduped on load (2026-08-15 root-cause investigation,
  fix applied 2026-08-16)**: ``lod2_child_feature_surface.csv`` carries a
  systematic ~2x duplicate-row bug, confirmed dataset-wide (98.1% of
  286,579 rows, 0 of 3,782 buildings unaffected) and root-caused via the
  raw ``lod2_child_feature.csv`` (every duplicate pair has byte-identical
  WKB geometry -- a literal duplicate-insert/duplicate-export bug
  upstream, not ambiguous or summable data). See
  ``.claude/residential/resolved.md``'s "Netherlands (Loenen) building
  data" entry for the full evidence trail. ``_dedup_surfaces`` drops
  these before any caller sees them. ``lod2_building_feature.csv``'s own
  ``area_total_wall``/``area_total_roof``/``area_total_floor``/
  ``surface_count_wall``/``surface_count_roof`` columns carry the *same*
  bug independently (they're stored aggregates, not derived from
  ``surfaces`` at read time, so deduping the surface rows alone does not
  fix them) -- ``_recompute_building_aggregates`` overwrites them from
  the deduped surfaces so ``LOD2Mapper``'s ``A_ref`` computation (which
  reads ``area_total_floor`` directly) isn't silently fed a ~2x-inflated
  value even after the surface-row fix above.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

FILE_BUILDINGS = "lod2_building_feature.csv"
FILE_SURFACES = "lod2_child_feature_surface.csv"
FILE_TABULA = "tabula.csv"

_ID_COLUMNS = ("building_feature_id", "surface_feature_id", "tabula_variant_code_id")

# Columns that always differ between a duplicate pair (this row's own
# primary key, and its FK into the raw lod2_child_feature table) -- every
# *other* column, including surface_area/tilt/azimuth, is byte-identical
# between the two rows of a confirmed duplicate. See module docstring.
_SURFACE_DUPLICATE_KEY_EXCLUDE = ("id", "child_row_id")

# classname -> (area column, count column) on lod2_building_feature.csv
# that _recompute_building_aggregates overwrites from deduped surfaces.
_AGGREGATE_COLUMNS = {
    "WallSurface": ("area_total_wall", "surface_count_wall"),
    "RoofSurface": ("area_total_roof", "surface_count_roof"),
    "GroundSurface": ("area_total_floor", "surface_count_floor"),
}


def _dedup_surfaces(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact-attribute-duplicate rows from a surfaces DataFrame.

    Confirmed root cause (2026-08-15, ``.claude/residential/resolved.md``):
    the raw table this surface export is derived from has, for 38,840 of
    its ``(building_feature_id, surface_feature_id)`` groups, exactly two
    rows with byte-identical WKB geometry -- a literal duplicate-insert/
    duplicate-export bug upstream, not two genuinely different surfaces
    (a "sum them" interpretation would never be right here). Every
    duplicate pair differs *only* in the two columns named in
    ``_SURFACE_DUPLICATE_KEY_EXCLUDE``; dedup keeps the first occurrence
    per unique combination of every other column.
    """
    key_cols = [c for c in df.columns if c not in _SURFACE_DUPLICATE_KEY_EXCLUDE]
    before = len(df)
    deduped = df.drop_duplicates(subset=key_cols, keep="first").reset_index(drop=True)
    dropped = before - len(deduped)
    if dropped:
        logger.warning(
            "CsvBuildingSource: dropped %d/%d (%.1f%%) exact-attribute-"
            "duplicate surface rows (see .claude/residential/resolved.md's "
            "2026-08-15/16 Netherlands duplicate-row entry) -- %d rows remain.",
            dropped, before, 100 * dropped / before, len(deduped),
        )
    return deduped


def _recompute_building_aggregates(bdf: pd.DataFrame, surfaces_df: pd.DataFrame) -> pd.DataFrame:
    """Overwrite ``area_total_*``/``surface_count_*`` from deduped surfaces.

    These are pre-computed aggregates stored directly on each building
    row, not derived from ``surfaces`` at read time -- so ``_dedup_surfaces``
    alone does not fix them; they carry the identical ~2x duplication bug
    independently (confirmed dataset-wide: e.g. ``surface_count_wall`` is
    exactly ``2x`` the deduped wall count for the large majority of
    buildings). This matters concretely because ``LOD2Mapper.map_building()``
    reads ``area_total_floor`` directly for ``A_ref``
    (``buem.buildings.mapping.lod2_mapper``) -- left uncorrected, ``A_ref``
    would still come out ~2x too large even after the surface-row dedup
    above (verified: building 37206's stored ``area_total_floor`` was
    150.7 m², matching the *un-deduped* raw floor-surface sum exactly, not
    the true ~75.35 m²).
    """
    sums = surfaces_df.groupby(["building_feature_id", "classname"])["surface_area"].sum()
    counts = surfaces_df.groupby(["building_feature_id", "classname"]).size()
    bdf = bdf.copy()
    for classname, (area_col, count_col) in _AGGREGATE_COLUMNS.items():
        if classname in sums.index.get_level_values("classname"):
            area_by_bldg = sums.xs(classname, level="classname")
            count_by_bldg = counts.xs(classname, level="classname")
        else:
            area_by_bldg = pd.Series(dtype=float)
            count_by_bldg = pd.Series(dtype="int64")
        bdf[area_col] = bdf["building_feature_id"].map(area_by_bldg).astype(float).fillna(0.0)
        bdf[count_col] = bdf["building_feature_id"].map(count_by_bldg).fillna(0).astype(int)
    return bdf


def _detect_dialect(path: Path) -> tuple[str, str]:
    """Sniff (delimiter, decimal-separator) from a CSV's header line.

    Compares how many fields a comma split vs. a semicolon split of the
    header produces; whichever count is larger wins (a semicolon-only
    export's header has exactly one comma-split "field" -- the whole
    line -- since no actual commas separate columns). Semicolon files
    are paired with a decimal comma (``10,412``), matching the one real
    export this was built against -- see the module docstring.
    """
    with open(path, encoding="utf-8") as f:
        header = f.readline()
    n_comma = header.count(",")
    n_semicolon = header.count(";")
    if n_semicolon > n_comma:
        return ";", ","
    return ",", "."


class CsvBuildingSource:
    """Load building data from a directory of CSV exports.

    Parameters
    ----------
    data_dir : str or Path
        Directory containing ``lod2_building_feature.csv``,
        ``lod2_child_feature_surface.csv``, and ``tabula.csv``.

    Raises
    ------
    FileNotFoundError
        If any of the three expected files is missing.

    Examples
    --------
    >>> src = CsvBuildingSource("data/buildings/netherlands/Loenen")
    >>> print(f"Buildings: {len(src.buildings)}")
    """

    def __init__(self, data_dir: str | Path):
        self.path = Path(data_dir)
        missing = [
            f for f in (FILE_BUILDINGS, FILE_SURFACES, FILE_TABULA)
            if not (self.path / f).exists()
        ]
        if missing:
            raise FileNotFoundError(
                f"CsvBuildingSource: missing file(s) {missing} under {self.path}. "
                f"Expected all three: {FILE_BUILDINGS}, {FILE_SURFACES}, {FILE_TABULA}."
            )
        self._cache: dict[str, pd.DataFrame] = {}

    def _load_csv(self, filename: str) -> pd.DataFrame:
        if filename not in self._cache:
            path = self.path / filename
            sep, decimal = _detect_dialect(path)
            logger.info(
                "Loading %s from %s (sep=%r, decimal=%r)",
                filename, self.path, sep, decimal,
            )
            df = pd.read_csv(
                path,
                sep=sep,
                decimal=decimal,
                na_values=["NULL"],
                keep_default_na=True,
                low_memory=False,
            )
            for col in _ID_COLUMNS:
                if col in df.columns:
                    df[col] = df[col].astype("Int64")
            if filename == FILE_SURFACES:
                df = _dedup_surfaces(df)
            elif filename == FILE_BUILDINGS:
                df = _recompute_building_aggregates(df, self.surfaces)
            self._cache[filename] = df
        return self._cache[filename]

    # ── primary accessors (same interface as ExcelBuildingSource) ────────────

    @property
    def buildings(self) -> pd.DataFrame:
        """``lod2_building_feature`` table -- one row per building."""
        return self._load_csv(FILE_BUILDINGS)

    @property
    def surfaces(self) -> pd.DataFrame:
        """``lod2_child_feature_surface`` table -- one row per LOD2 surface."""
        return self._load_csv(FILE_SURFACES)

    @property
    def tabula(self) -> pd.DataFrame:
        """TABULA typology table -- one row per building archetype."""
        return self._load_csv(FILE_TABULA)

    # ── filtered accessors ───────────────────────────────────────────────────

    def get_building_ids(self, limit: int | None = None) -> list[int]:
        """Return a list of ``building_feature_id`` values."""
        ids = self.buildings["building_feature_id"].tolist()
        if limit is not None:
            ids = ids[:limit]
        return ids

    def get_surfaces_for_building(self, building_feature_id: int) -> pd.DataFrame:
        """Return all child surfaces for a single building."""
        return self.surfaces[
            self.surfaces["building_feature_id"] == building_feature_id
        ]

    def get_tabula_row(self, tabula_id: float) -> pd.Series | None:
        """Look up a single TABULA row by ``id``."""
        if pd.isna(tabula_id):
            return None
        matches = self.tabula[self.tabula["id"] == int(tabula_id)]
        if matches.empty:
            return None
        return matches.iloc[0]


__all__ = ["CsvBuildingSource"]
