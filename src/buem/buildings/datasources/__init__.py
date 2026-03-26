"""Data source loaders for building data (Excel and PostgreSQL)."""

from buem.buildings.datasources.excel_source import ExcelBuildingSource

__all__ = ["ExcelBuildingSource"]

# PostgresBuildingSource is available when psycopg2 is installed:
try:
    from buem.buildings.datasources.pg_source import PostgresBuildingSource
    __all__.append("PostgresBuildingSource")
except ImportError:
    pass
