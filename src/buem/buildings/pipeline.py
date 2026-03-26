"""
Pipeline runner — end-to-end: Excel → LOD2 Mapper → v3 GeoJSON files.

Usage
-----
From the project root::

    python -m buem.buildings.pipeline

Or with arguments::

    python -m buem.buildings.pipeline --limit 10 --output data/buildings/germany/mainkopen

The pipeline:
1. Loads the Excel workbook (or Parquet cache)
2. Maps LOD2 geometry + TABULA typology into Building objects
3. Writes v3-schema-compliant GeoJSON files to the output directory
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Resolve project paths
_MODULE_DIR = Path(__file__).resolve().parent          # src/buem/buildings/
_SRC_DIR = _MODULE_DIR.parent                          # src/buem/
_DATA_DIR = _SRC_DIR / "data"

# Default paths
DEFAULT_WORKBOOK = _DATA_DIR / "buildings" / "tabula_building_child_features.xlsx"
DEFAULT_OUTPUT = _DATA_DIR / "buildings" / "germany" / "mainkopen"
DEFAULT_PARQUET_CACHE = _DATA_DIR / "buildings" / "_parquet_cache"


def main(
    workbook: str | Path = DEFAULT_WORKBOOK,
    output_dir: str | Path = DEFAULT_OUTPUT,
    limit: int | None = None,
    use_parquet: bool = False,
    create_parquet: bool = False,
    country: str = "DE",
) -> None:
    """Run the full Excel → Building → GeoJSON pipeline.

    Parameters
    ----------
    workbook : str or Path
        Path to the Excel workbook.
    output_dir : str or Path
        Directory for output GeoJSON files.
    limit : int or None
        Maximum number of buildings to process (``None`` = all).
    use_parquet : bool
        If ``True``, load from Parquet cache instead of Excel.
    create_parquet : bool
        If ``True``, convert Excel to Parquet and exit.
    country : str
        ISO country code (default ``"DE"``).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("buem.buildings.pipeline")

    # ── 1. Load data ─────────────────────────────────────────────────────────
    from buem.buildings.datasources.excel_source import ExcelBuildingSource

    t0 = time.perf_counter()

    if use_parquet:
        log.info("Loading from Parquet cache: %s", DEFAULT_PARQUET_CACHE)
        source = ExcelBuildingSource.from_parquet(DEFAULT_PARQUET_CACHE)
    else:
        log.info("Loading Excel workbook: %s", workbook)
        source = ExcelBuildingSource(workbook)

    if create_parquet:
        log.info("Creating Parquet cache at %s", DEFAULT_PARQUET_CACHE)
        source.to_parquet(DEFAULT_PARQUET_CACHE)
        log.info("Parquet cache created. Re-run with --use-parquet for faster loading.")
        return

    # Touch all sheets to trigger loading
    n_bldg = len(source.buildings)
    n_surf = len(source.surfaces)
    n_tab = len(source.tabula)
    t_load = time.perf_counter() - t0
    log.info(
        "Loaded %d buildings, %d surfaces, %d TABULA rows in %.1fs",
        n_bldg, n_surf, n_tab, t_load,
    )

    # ── 2. Map buildings ─────────────────────────────────────────────────────
    from buem.buildings.mapping.lod2_mapper import LOD2Mapper

    t1 = time.perf_counter()
    mapper = LOD2Mapper(source, country=country)
    buildings = mapper.map_all(limit=limit)
    t_map = time.perf_counter() - t1
    log.info("Mapped %d buildings in %.1fs", len(buildings), t_map)

    if not buildings:
        log.error("No buildings mapped — check data and logs above.")
        sys.exit(1)

    # ── 3. Write GeoJSON files ───────────────────────────────────────────────
    from buem.buildings.generator.json_generator import GeoJsonBuildingWriter

    t2 = time.perf_counter()
    writer = GeoJsonBuildingWriter(output_dir)
    paths = writer.write_batch(buildings, mode="individual")
    t_write = time.perf_counter() - t2
    log.info("Wrote %d GeoJSON files to %s in %.1fs", len(paths), output_dir, t_write)

    # ── 4. Summary ───────────────────────────────────────────────────────────
    total_time = time.perf_counter() - t0
    log.info("Pipeline complete in %.1fs", total_time)

    # Print a sample building for verification
    if buildings:
        sample = buildings[0]
        log.info(
            "Sample — building_id=%s, type=%s, elements=%d, A_ref=%.1f m²",
            sample.identity.building_feature_id,
            sample.identity.building_type,
            len(sample.elements),
            sample.computed_A_ref(),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="BUEM Buildings Pipeline — Excel → v3 GeoJSON",
    )
    parser.add_argument(
        "--workbook", type=str, default=str(DEFAULT_WORKBOOK),
        help="Path to the Excel workbook",
    )
    parser.add_argument(
        "--output", type=str, default=str(DEFAULT_OUTPUT),
        help="Output directory for GeoJSON files",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximum number of buildings to process",
    )
    parser.add_argument(
        "--country", type=str, default="DE",
        help="ISO country code (default: DE)",
    )
    parser.add_argument(
        "--use-parquet", action="store_true",
        help="Load from Parquet cache instead of Excel",
    )
    parser.add_argument(
        "--create-parquet", action="store_true",
        help="Convert Excel to Parquet cache and exit",
    )

    args = parser.parse_args()
    main(
        workbook=args.workbook,
        output_dir=args.output,
        limit=args.limit,
        country=args.country,
        use_parquet=args.use_parquet,
        create_parquet=args.create_parquet,
    )
