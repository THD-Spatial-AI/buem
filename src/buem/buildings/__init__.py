"""
BUEM Buildings Module — Data ingestion, mapping, and JSON generation for buildings.

This module provides a complete pipeline for:
1. Loading building data from PostgreSQL (city2tabula) or Excel workbooks
2. Mapping LOD2 geometry + TABULA typology into canonical Building objects
3. Generating v3-schema-compliant GeoJSON files for the thermal model

Subpackages
-----------
components/     Dataclasses for each envelope element type (wall, roof, floor, etc.)
datasources/    Data loaders for PostgreSQL and Excel
mapping/        LOD2 + TABULA → Building object mapping logic
generator/      Building → v3 GeoJSON JSON file generation
"""

from buem.buildings.building import Building, BuildingIdentity, ThermalProperties
from buem.buildings.components.base import EnvelopeElement
from buem.buildings.datasources.excel_source import ExcelBuildingSource
from buem.buildings.generator.json_generator import GeoJsonBuildingWriter
from buem.buildings.mapping.lod2_mapper import LOD2Mapper

__all__ = [
    "Building",
    "BuildingIdentity",
    "ThermalProperties",
    "EnvelopeElement",
    "ExcelBuildingSource",
    "LOD2Mapper",
    "GeoJsonBuildingWriter",
]
