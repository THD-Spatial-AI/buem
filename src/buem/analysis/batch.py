"""
Many-building batch runner: single-provider heating/cooling/electricity
demand for every (or a filtered subset of) building in the bundled Excel
source, written incrementally to a single Parquet file.

Deliberately single-provider (unlike ``provider_comparison.py``, which
runs one building through all providers) -- per the user's own
simplification ("we do not need to run all 3 weather data" for a
full-scale batch). One weather DataFrame is fetched once in the main
process and shared read-only across every worker/building, rather than
re-fetched per building: buem's own thermal properties, not the weather
feed, are what's under study at batch scale.

Mirrors ``buem.parallelization.parallel_run.ParallelBuildingProcessor``'s
``ProcessPoolExecutor`` + per-worker heavy-import pre-warm pattern, but
doesn't reuse that class directly -- its own pre-warm step assumes one
building file per building and re-derives lat/lon/provider per file via
``_extract_building_attrs()``, neither of which applies here (buildings
come from ``ExcelBuildingSource`` by feature id, and every building in
one batch run shares the single weather fetch made up front).

No hardcoded paths: the workbook path and ``WEATHER_DATA_DIR`` come from
``DEFAULT_WORKBOOK``/environment variables exactly as everywhere else in
this codebase, so this module runs unchanged on a bigger machine (e.g.
sd26) later -- submitting/running it there is the user's own operational
step, not something this module does.

CLI
---
    python -m buem.analysis.batch --limit 20 --provider merra-2 --output results.parquet

See ``tests/test_analysis.py`` for a small (2-3 building) smoke test of
this same path.
"""
from __future__ import annotations

import argparse
import logging
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from buem.buildings.pipeline import DEFAULT_WORKBOOK
from buem.config.building_registry import (
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_WEATHER_PROVIDER,
    DEFAULT_YEAR,
)

logger = logging.getLogger(__name__)

# Errors an individual building's mapping/attribute-build/solve step can
# raise without this being a bug in the batch runner itself -- caught per
# building so one bad row doesn't abort the whole run. Mirrors
# parallel_run.py's own exception tuple, with RuntimeError added (CVXPY's
# own input-validation failures, e.g. "Problem data contains NaN", raise
# this -- see CLAUDE.md's weather data-quality notes).
_PER_BUILDING_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, RuntimeError)

_RESULT_COLUMNS = [
    "building_feature_id",
    "status",
    "building_type",
    "construction_period",
    "A_ref",
    "n_walls",
    "n_exposed",
    "heating_kWh",
    "cooling_kWh",
    "elec_kWh",
    "error",
]

# Module-level, set once per worker process by _worker_init -- avoids both
# re-opening the (multi-MB) Excel workbook / re-instantiating LOD2Mapper
# for every single building (matching parallel_run.py's own "heavy setup
# once per worker, not once per task" convention), and re-pickling the
# shared weather DataFrame once per *building* rather than once per
# *worker* -- at full 5,236-building scale that's the difference between
# ~dozens of serializations and thousands.
_WORKER_MAPPER = None
_WORKER_WEATHER: pd.DataFrame | None = None


def _worker_init(workbook_path: str, country: str, weather_df: pd.DataFrame) -> None:
    """Runs once per spawned worker process (see module docstring)."""
    global _WORKER_MAPPER, _WORKER_WEATHER

    import cvxpy  # noqa: F401
    import numpy  # noqa: F401
    import pandas  # noqa: F401

    from buem.buildings.datasources.excel_source import ExcelBuildingSource
    from buem.buildings.mapping.lod2_mapper import LOD2Mapper

    source = ExcelBuildingSource(workbook_path)
    _WORKER_MAPPER = LOD2Mapper(source, country=country)
    _WORKER_WEATHER = weather_df


def _process_one_building(building_feature_id: int, use_milp: bool) -> dict[str, Any]:
    """Map, build, and simulate one building against the worker-shared
    weather DataFrame set by ``_worker_init``."""
    from buem.analysis.building_selection import wall_exposure
    from buem.analysis.provider_comparison import building_attrs_from
    from buem.config.cfg_building import CfgBuilding
    from buem.integration.scripts.attribute_builder import AttributeBuilder
    from buem.thermal.model_buem import ModelBUEM

    row: dict[str, Any] = {col: None for col in _RESULT_COLUMNS}
    row["building_feature_id"] = building_feature_id

    try:
        assert _WORKER_MAPPER is not None, "_worker_init() must run before _process_one_building() (pool initializer)"
        building = _WORKER_MAPPER.map_building(building_feature_id)
        if building is None:
            row["status"] = "skipped"
            row["error"] = "LOD2Mapper.map_building() returned None (no TABULA match or unmappable geometry)"
            return row

        exposure = wall_exposure(building)
        row["building_type"] = building.identity.building_type
        row["construction_period"] = building.identity.construction_period
        row["A_ref"] = round(building.computed_A_ref(), 2)
        row["n_walls"] = exposure.n_walls
        row["n_exposed"] = exposure.n_exposed

        attrs = dict(building_attrs_from(building))
        attrs["weather"] = _WORKER_WEATHER
        attrs["use_provided_weather"] = True

        merged = AttributeBuilder(payload_attrs=attrs).build()
        cfg = CfgBuilding(merged).to_cfg_dict()
        model = ModelBUEM(cfg)
        model.sim_model(use_milp=use_milp)

        row["heating_kWh"] = round(float(pd.Series(model.heating_load).sum()), 2)
        row["cooling_kWh"] = round(float(pd.Series(model.cooling_load).abs().sum()), 2)
        row["elec_kWh"] = round(float(merged["elecLoad"].sum()), 2)
        row["status"] = "ok"

    except _PER_BUILDING_ERRORS as exc:
        row["status"] = "error"
        row["error"] = f"{type(exc).__name__}: {exc}"

    return row


@dataclass
class BatchConfig:
    """Configuration for one ``run_batch()`` call."""

    workbook_path: str | Path = DEFAULT_WORKBOOK
    country: str = "DE"
    latitude: float = DEFAULT_LATITUDE
    longitude: float = DEFAULT_LONGITUDE
    year: int = DEFAULT_YEAR
    provider: str = DEFAULT_WEATHER_PROVIDER
    limit: int | None = None
    workers: int | None = None
    use_milp: bool = False
    flush_every: int = 200
    building_ids: list[int] | None = None


def run_batch(config: BatchConfig, output_path: str | Path) -> Path:
    """Run every (or the first ``config.limit``) building id in
    ``config.workbook_path`` through a single-provider simulation,
    writing one row per building to *output_path* (Parquet) incrementally
    as results complete -- so a long run's progress survives even if it's
    interrupted partway through.

    If ``config.building_ids`` is set, those ids are used verbatim instead
    of ``source.get_building_ids(limit=...)`` -- e.g. a caller-filtered
    subset from ``building_selection.select_household_buildings()``, or a
    resume list with already-processed ids excluded. ``config.limit`` is
    ignored when ``building_ids`` is set.

    Returns
    -------
    Path
        *output_path*, resolved.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from buem.analysis.weather_providers import extract_provider_weather
    from buem.buildings.datasources.excel_source import ExcelBuildingSource

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # One weather fetch, shared read-only across every building/worker --
    # see module docstring for why this is single-location/single-provider
    # rather than resolved per building.
    logger.info(
        "Fetching %s weather for (%.4f, %.4f), %d -- shared across the whole batch.",
        config.provider, config.latitude, config.longitude, config.year,
    )
    weather_df = extract_provider_weather(
        config.latitude, config.longitude, config.year, providers=(config.provider,)
    )[config.provider]

    source = ExcelBuildingSource(config.workbook_path)
    if config.building_ids is not None:
        building_ids = list(config.building_ids)
        logger.info("Batch: %d caller-supplied building id(s)", len(building_ids))
    else:
        building_ids = source.get_building_ids(limit=config.limit)
        logger.info("Batch: %d building id(s) from %s", len(building_ids), config.workbook_path)
    total = len(building_ids)

    workers = config.workers
    schema = pa.schema([
        ("building_feature_id", pa.int64()),
        ("status", pa.string()),
        ("building_type", pa.string()),
        ("construction_period", pa.string()),
        ("A_ref", pa.float64()),
        ("n_walls", pa.int64()),
        ("n_exposed", pa.int64()),
        ("heating_kWh", pa.float64()),
        ("cooling_kWh", pa.float64()),
        ("elec_kWh", pa.float64()),
        ("error", pa.string()),
    ])

    start = time.time()
    n_ok = n_skipped = n_error = 0
    pending_rows: list[dict[str, Any]] = []

    def _flush(writer: pq.ParquetWriter) -> None:
        nonlocal pending_rows
        if not pending_rows:
            return
        table = pa.Table.from_pylist(pending_rows, schema=schema)
        writer.write_table(table)
        pending_rows = []

    with pq.ParquetWriter(str(output_path), schema) as writer, ProcessPoolExecutor(
        max_workers=workers,
        initializer=_worker_init,
        initargs=(str(config.workbook_path), config.country, weather_df),
    ) as executor:
        future_to_id = {
            executor.submit(_process_one_building, bid, config.use_milp): bid
            for bid in building_ids
        }
        for completed, future in enumerate(as_completed(future_to_id), start=1):
            bid = future_to_id[future]
            try:
                row = future.result()
            except _PER_BUILDING_ERRORS as exc:
                row = {col: None for col in _RESULT_COLUMNS}
                row["building_feature_id"] = bid
                row["status"] = "error"
                row["error"] = f"worker raised {type(exc).__name__}: {exc}"

            pending_rows.append(row)
            if row["status"] == "ok":
                n_ok += 1
            elif row["status"] == "skipped":
                n_skipped += 1
            else:
                n_error += 1

            if completed % max(1, config.flush_every) == 0 or completed == total:
                _flush(writer)
                elapsed = time.time() - start
                logger.info(
                    "%d/%d done (ok=%d skipped=%d error=%d) -- %.1fs elapsed, %.2f buildings/s",
                    completed, total, n_ok, n_skipped, n_error, elapsed,
                    completed / elapsed if elapsed > 0 else 0.0,
                )

    logger.info(
        "Batch complete: %d ok, %d skipped, %d error -- wrote %s",
        n_ok, n_skipped, n_error, output_path,
    )
    return output_path


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run buem's thermal model across many buildings for one weather provider."
    )
    parser.add_argument("--workbook", type=str, default=str(DEFAULT_WORKBOOK), help="TABULA/city2tabula workbook path.")
    parser.add_argument("--country", type=str, default="DE", help="TABULA country code for archetype matching.")
    parser.add_argument("--latitude", type=float, default=DEFAULT_LATITUDE)
    parser.add_argument("--longitude", type=float, default=DEFAULT_LONGITUDE)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--provider", type=str, default=DEFAULT_WEATHER_PROVIDER, choices=["merra-2", "cosmo-rea6", "era5-land"])
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N building ids (omit for all). Ignored if --building-ids is set.")
    parser.add_argument("--building-ids", type=str, default=None, help="Comma-separated explicit building_feature_id list, e.g. '52203,44100'. Overrides --limit.")
    parser.add_argument("--workers", type=int, default=None, help="Worker process count (default: auto).")
    parser.add_argument("--use-milp", action="store_true", help="Pass use_milp=True to ModelBUEM.sim_model().")
    parser.add_argument("--flush-every", type=int, default=200, help="Write to Parquet every N completed buildings.")
    parser.add_argument("--output", type=str, default="batch_results.parquet")
    return parser


def main(argv: list[str] | None = None) -> Path:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    args = _build_arg_parser().parse_args(argv)
    config = BatchConfig(
        workbook_path=args.workbook,
        country=args.country,
        latitude=args.latitude,
        longitude=args.longitude,
        year=args.year,
        provider=args.provider,
        limit=args.limit,
        building_ids=[int(x) for x in args.building_ids.split(",")] if args.building_ids else None,
        workers=args.workers,
        use_milp=args.use_milp,
        flush_every=args.flush_every,
    )
    return run_batch(config, args.output)


if __name__ == "__main__":
    main()


__all__ = ["BatchConfig", "main", "run_batch"]
