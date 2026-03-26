"""
PostgreSQL-based building data source.

Connects to the ``city2tabula_germany`` database and loads the same three tables
available in the Excel workbook:

  - ``city2tabula.lod2_building_feature``
  - ``city2tabula.lod2_child_feature_surface``
  - ``tabula.tabula``

The resulting DataFrames are column-compatible with ``ExcelBuildingSource`` so
all downstream mapping code works identically regardless of data origin.

Requirements
------------
- ``psycopg2`` (or ``psycopg2-binary``) must be installed.
- A running PostgreSQL instance with the ``city2tabula_germany`` database.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import psycopg2
except ImportError:
    psycopg2 = None  # type: ignore[assignment]
    logger.warning(
        "psycopg2 not installed — PostgresBuildingSource will not work. "
        "Install with: conda install psycopg2"
    )


class PostgresBuildingSource:
    """Load building data from a PostgreSQL database.

    Parameters
    ----------
    host : str
        Database host (default ``"localhost"``).
    port : int
        Database port (default ``5432``).
    database : str
        Database name (default ``"city2tabula_germany"``).
    user : str
        Database user (default ``"postgres"``).
    password : str
        Database password (default ``"postgres"``).

    Raises
    ------
    ImportError
        If psycopg2 is not installed.
    """

    # SQL statements (parameterised — no user-injected values)
    SQL_BUILDINGS = "SELECT * FROM city2tabula.lod2_building_feature"
    SQL_SURFACES = "SELECT * FROM city2tabula.lod2_child_feature_surface"
    SQL_TABULA = "SELECT * FROM tabula.tabula"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "city2tabula_germany",
        user: str = "postgres",
        password: str = "postgres",
    ):
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is required for PostgresBuildingSource. "
                "Install with: conda install psycopg2-binary"
            )
        self._conn_params = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }
        self._cache: Dict[str, pd.DataFrame] = {}

    def _get_connection(self):
        """Create a new database connection."""
        return psycopg2.connect(**self._conn_params)

    def _load_query(self, key: str, sql: str) -> pd.DataFrame:
        """Execute a query and cache the result as a DataFrame."""
        if key not in self._cache:
            logger.info("Executing SQL: %s", sql[:80])
            conn = self._get_connection()
            try:
                self._cache[key] = pd.read_sql_query(sql, conn)
            finally:
                conn.close()
        return self._cache[key]

    # ── primary accessors (same interface as ExcelBuildingSource) ────────────

    @property
    def buildings(self) -> pd.DataFrame:
        """``lod2_building_feature`` — one row per building."""
        return self._load_query("buildings", self.SQL_BUILDINGS)

    @property
    def surfaces(self) -> pd.DataFrame:
        """``lod2_child_feature_surface`` — one row per LOD2 surface."""
        return self._load_query("surfaces", self.SQL_SURFACES)

    @property
    def tabula(self) -> pd.DataFrame:
        """TABULA typology — one row per building archetype."""
        return self._load_query("tabula", self.SQL_TABULA)

    # ── filtered accessors ───────────────────────────────────────────────────

    def get_building_ids(self, limit: Optional[int] = None) -> List[int]:
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

    def get_tabula_row(self, tabula_id: float) -> Optional[pd.Series]:
        """Look up a single TABULA row by ``id``."""
        if pd.isna(tabula_id):
            return None
        matches = self.tabula[self.tabula["id"] == int(tabula_id)]
        if matches.empty:
            return None
        return matches.iloc[0]
