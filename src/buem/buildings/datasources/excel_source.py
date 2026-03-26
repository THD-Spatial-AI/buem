"""
Excel-based building data source.

Loads building data from a country Excel workbook where each sheet corresponds
to one database table:

  - ``city2tabula lod2_building_featu``  → building-level aggregates (5,236 rows for DE)
  - ``city2tabula lod2_child_feature_``  → per-surface geometry (87,815 rows for DE)
  - ``tabula tabula``                    → TABULA typology (232 rows for DE)

The DataFrames produced are column-compatible with ``PostgresBuildingSource``
so downstream mapping code works identically regardless of data origin.

Performance
-----------
On first load the workbook sheets are cached in memory.  For repeated batch runs
(especially with multiprocessing) call ``to_parquet()`` once to convert to Parquet
format, then use ``from_parquet()`` — Parquet reads are ~10-50× faster than Excel.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


# Map human-readable names to the actual (truncated) sheet names in the workbook
SHEET_BUILDINGS = "city2tabula lod2_building_featu"
SHEET_SURFACES = "city2tabula lod2_child_feature_"
SHEET_TABULA = "tabula tabula"


class ExcelBuildingSource:
    """Load building data from a country Excel workbook.

    Parameters
    ----------
    workbook_path : str or Path
        Path to the ``.xlsx`` file (e.g. ``tabula_building_child_features.xlsx``).

    Raises
    ------
    FileNotFoundError
        If the workbook file does not exist.

    Examples
    --------
    >>> src = ExcelBuildingSource("data/buildings/tabula_building_child_features.xlsx")
    >>> print(f"Buildings: {len(src.buildings)}")
    Buildings: 5236
    >>> print(f"Surfaces: {len(src.surfaces)}")
    Surfaces: 87815
    """

    def __init__(self, workbook_path: str | Path):
        self.path = Path(workbook_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Workbook not found: {self.path}")
        self._cache: Dict[str, pd.DataFrame] = {}

    def _load_sheet(self, sheet_name: str) -> pd.DataFrame:
        """Load and cache a single sheet from the workbook."""
        if sheet_name not in self._cache:
            logger.info("Loading sheet '%s' from %s", sheet_name, self.path.name)
            self._cache[sheet_name] = pd.read_excel(
                self.path, sheet_name=sheet_name
            )
        return self._cache[sheet_name]

    # ── primary accessors ────────────────────────────────────────────────────

    @property
    def buildings(self) -> pd.DataFrame:
        """``lod2_building_feature`` table — one row per building.

        Key columns: ``building_feature_id``, ``tabula_variant_code_id``,
        ``tabula_variant_code``, ``room_height``, ``number_of_storeys``,
        ``area_total_roof``, ``area_total_wall``, ``area_total_floor``,
        ``surface_count_floor``, ``surface_count_roof``, ``surface_count_wall``.
        """
        return self._load_sheet(SHEET_BUILDINGS)

    @property
    def surfaces(self) -> pd.DataFrame:
        """``lod2_child_feature_surface`` table — one row per LOD2 surface.

        Key columns: ``building_feature_id``, ``surface_feature_id``,
        ``objectclass_id``, ``classname``, ``height``, ``surface_area``,
        ``tilt``, ``azimuth``.
        """
        return self._load_sheet(SHEET_SURFACES)

    @property
    def tabula(self) -> pd.DataFrame:
        """TABULA typology table — one row per building variant.

        Indexed by ``id``.  Contains U-values, areas, thermal parameters,
        shading factors, and air change rates for every TABULA archetype.
        """
        return self._load_sheet(SHEET_TABULA)

    # ── filtered accessors ───────────────────────────────────────────────────

    def get_building_ids(self, limit: Optional[int] = None) -> List[int]:
        """Return a list of ``building_feature_id`` values.

        Parameters
        ----------
        limit : int or None
            Maximum number of IDs to return.  ``None`` returns all.
        """
        ids = self.buildings["building_feature_id"].tolist()
        if limit is not None:
            ids = ids[:limit]
        return ids

    def get_surfaces_for_building(self, building_feature_id: int) -> pd.DataFrame:
        """Return all child surfaces for a single building.

        Parameters
        ----------
        building_feature_id : int
            The building identifier.

        Returns
        -------
        pd.DataFrame
            Filtered rows from the surfaces table.
        """
        return self.surfaces[
            self.surfaces["building_feature_id"] == building_feature_id
        ]

    def get_tabula_row(self, tabula_id: float) -> Optional[pd.Series]:
        """Look up a single TABULA row by ``id``.

        Parameters
        ----------
        tabula_id : float
            The ``id`` column value (= ``tabula_variant_code_id`` from buildings).

        Returns
        -------
        pd.Series or None
            The TABULA row, or ``None`` if not found.
        """
        if pd.isna(tabula_id):
            return None
        matches = self.tabula[self.tabula["id"] == int(tabula_id)]
        if matches.empty:
            return None
        return matches.iloc[0]

    # ── Parquet conversion for performance ───────────────────────────────────

    def to_parquet(self, output_dir: str | Path) -> None:
        """Convert all sheets to Parquet files for faster repeated loading.

        Parquet reads are ~10-50× faster than Excel for large tables.  Call
        this once, then use ``from_parquet()`` for subsequent runs.

        Parameters
        ----------
        output_dir : str or Path
            Directory where ``.parquet`` files will be written.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for name, prop_name in [
            ("buildings", SHEET_BUILDINGS),
            ("surfaces", SHEET_SURFACES),
            ("tabula", SHEET_TABULA),
        ]:
            df = self._load_sheet(prop_name)
            pq_path = out / f"{name}.parquet"
            df.to_parquet(pq_path, index=False)
            logger.info("Saved %s → %s (%d rows)", name, pq_path, len(df))

    @classmethod
    def from_parquet(cls, parquet_dir: str | Path) -> "ExcelBuildingSource":
        """Load from pre-converted Parquet files instead of Excel.

        Parameters
        ----------
        parquet_dir : str or Path
            Directory containing ``buildings.parquet``, ``surfaces.parquet``,
            ``tabula.parquet``.

        Returns
        -------
        ExcelBuildingSource
            An instance with data already loaded into the internal cache.
        """
        d = Path(parquet_dir)
        # Create with a dummy path — we override the cache directly
        instance = object.__new__(cls)
        instance.path = d
        instance._cache = {}

        for name, sheet_name in [
            ("buildings", SHEET_BUILDINGS),
            ("surfaces", SHEET_SURFACES),
            ("tabula", SHEET_TABULA),
        ]:
            pq = d / f"{name}.parquet"
            if not pq.exists():
                raise FileNotFoundError(f"Parquet file not found: {pq}")
            instance._cache[sheet_name] = pd.read_parquet(pq)
            logger.info("Loaded %s from %s (%d rows)", name, pq, len(instance._cache[sheet_name]))

        return instance
