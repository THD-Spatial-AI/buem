"""
buem-vs-CBS validation: run real Netherlands buildings through the full
simulation pipeline, grouped by housing type, and compare simulated
heating demand against CBS's real regional gas-consumption statistics
(``cbs_reference``, converted via ``gas_conversion``).

Mirrors ``buem.analysis.batch``'s own simulation pattern (one weather
fetch shared across all buildings, ``AttributeBuilder``/``CfgBuilding``/
``ModelBUEM`` per building) adapted to a ``CsvBuildingSource`` region
instead of the German Excel workbook, and grouped by
(building_type, neighbour_status) -- the dimension CBS's own housing-type
categories key on (``cbs_reference.BUEM_TYPE_TO_CBS_KEY``) -- rather than
run flat across every building.

**Known, deliberate scope limits, not oversights**:

- One weather fetch for the whole region (its buildings' own mean real
  lat/lon), not per building -- reasonable for a single village/small
  town spanning a few km (matches ``batch.py``'s own single-location
  convention), would need reconsidering for a larger/more spread-out
  region.
- CBS's reference year (2024, the most recent available) is compared
  against simulated weather for ``DEFAULT_YEAR`` (2018, the year this
  whole project's weather-archive access has been verified working for)
  -- a real year mismatch, not resolved here. A closer comparison would
  need either a 2024 weather archive or averaging CBS across several
  years near 2018.
- The gas -> useful-heat conversion (``gas_conversion``) rests on a
  national-average space-heating share and a round boiler-efficiency
  assumption -- see that module's own docstring for exactly which parts
  are solid vs. which are the most worth revisiting.

CLI
---
    python -m buem.analysis.netherlands.validation \\
        --data-dir src/buem/data/buildings/netherlands \\
        --region-code GM0200 --period 2024JJ00 --samples-per-type 3
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from buem.analysis.netherlands.cbs_reference import BUEM_TYPE_TO_CBS_KEY, fetch_consumption
from buem.analysis.netherlands.gas_conversion import GasToHeatBreakdown, gas_m3_to_useful_heat_kwh
from buem.analysis.provider_comparison import building_attrs_from
from buem.analysis.weather_providers import extract_provider_weather
from buem.buildings.building import Building
from buem.buildings.datasources.csv_source import CsvBuildingSource
from buem.buildings.mapping.lod2_mapper import LOD2Mapper
from buem.config.building_registry import DEFAULT_WEATHER_PROVIDER, DEFAULT_YEAR
from buem.config.cfg_building import CfgBuilding

logger = logging.getLogger(__name__)

_PER_BUILDING_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, RuntimeError)


@dataclass
class TypeGroupResult:
    """Simulated + real-reference comparison for one (building_type,
    neighbour_status) group -- one row of the final report."""

    building_type: str
    neighbour_status: str
    cbs_key: str | None
    n_simulated: int
    mean_simulated_heating_kwh: float | None
    cbs_gas_m3_per_year: float | None
    cbs_conversion: GasToHeatBreakdown | None
    building_ids: list[str] = field(default_factory=list)

    @property
    def ratio_simulated_to_cbs(self) -> float | None:
        """simulated / CBS-implied useful heat -- 1.0 means exact
        agreement; >1 means buem simulates more heating than the
        CBS-derived estimate, <1 means less. ``None`` if either side is
        missing."""
        if self.mean_simulated_heating_kwh is None or self.cbs_conversion is None:
            return None
        if self.cbs_conversion.useful_heat_kwh <= 0:
            return None
        return self.mean_simulated_heating_kwh / self.cbs_conversion.useful_heat_kwh


def _select_buildings_by_group(
    source: CsvBuildingSource, samples_per_group: int,
) -> dict[tuple[str, str], list[int]]:
    """Group residential buildings' real ids by (building_type,
    neighbour_status), capped at ``samples_per_group`` ids per group --
    picked in file order (deterministic, not random), matching
    ``building_selection``'s own "first N that qualify" convention."""
    bdf = source.buildings
    if "is_residential" not in bdf.columns:
        raise ValueError(
            "buildings table has no 'is_residential' column -- run "
            "nl_archetype_mapper.map_buildings() on this data_dir first."
        )
    residential = bdf[bdf["is_residential"] == True]  # noqa: E712
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for _, row in residential.iterrows():
        btype, nstatus = row.get("building_type"), row.get("neighbour_status")
        if pd.isna(btype) or pd.isna(nstatus):
            continue
        key = (str(btype), str(nstatus))
        if len(groups[key]) >= samples_per_group:
            continue
        groups[key].append(int(row["building_feature_id"]))
    return groups


def _region_center(source: CsvBuildingSource) -> tuple[float, float]:
    """Mean real (lat, lon) across every building with real geometry --
    a single representative point for the region's one shared weather
    fetch (see module docstring)."""
    from buem.buildings.mapping.geometry_utils import building_lat_lon

    lats, lons = [], []
    for _, row in source.buildings.iterrows():
        result = building_lat_lon(row)
        if result is not None:
            lats.append(result[0])
            lons.append(result[1])
    if not lats:
        raise ValueError("No building in this source has real geometry to derive a region center from.")
    return sum(lats) / len(lats), sum(lons) / len(lons)


def run_validation(
    data_dir: str | Path,
    *,
    u_value_overrides_path: str | Path | None = None,
    region_code: str,
    period: str,
    samples_per_group: int = 3,
    weather_year: int = DEFAULT_YEAR,
    weather_provider: str = DEFAULT_WEATHER_PROVIDER,
    use_milp: bool = False,
) -> list[TypeGroupResult]:
    """Run the full buem-vs-CBS comparison for one region.

    Parameters
    ----------
    data_dir : str or Path
        A ``CsvBuildingSource`` directory (e.g.
        ``src/buem/data/buildings/netherlands``) already run through
        ``nl_archetype_mapper`` (real ``building_type``/
        ``tabula_variant_code_id`` populated).
    u_value_overrides_path : str or Path, optional
        Path to ``u_value_reference.csv`` (default: ``u_value_reference
        .csv`` inside ``data_dir``, if present).
    region_code, period : str
        CBS ``RegioS``/``Perioden`` codes, e.g. ``"GM0200"``/``"2024JJ00"``.
    samples_per_group : int
        How many buildings to simulate per (building_type,
        neighbour_status) group -- keeps this a smoke-scale comparison,
        not a full-population run (a real compute cost, see module
        docstring).

    Returns
    -------
    list of TypeGroupResult
        One entry per (building_type, neighbour_status) group that had
        at least one successfully-simulated building.
    """
    source = CsvBuildingSource(data_dir)
    overrides_path = Path(u_value_overrides_path) if u_value_overrides_path else Path(data_dir) / "u_value_reference.csv"
    u_value_overrides = pd.read_csv(overrides_path) if overrides_path.exists() else None
    if u_value_overrides is None:
        logger.warning("No u_value_reference.csv found at %s -- LOD2Mapper will use raw TABULA U-values.", overrides_path)

    mapper = LOD2Mapper(source, country="NL", u_value_overrides=u_value_overrides)

    lat, lon = _region_center(source)
    logger.info("Region center for shared weather fetch: (%.4f, %.4f)", lat, lon)
    weather_df = extract_provider_weather(lat, lon, weather_year, providers=(weather_provider,))[weather_provider]

    groups = _select_buildings_by_group(source, samples_per_group)
    logger.info("Selected %d (building_type, neighbour_status) groups, up to %d building(s) each",
                len(groups), samples_per_group)

    cbs_keys_needed = {BUEM_TYPE_TO_CBS_KEY[k] for k in groups if k in BUEM_TYPE_TO_CBS_KEY}
    cbs_data = fetch_consumption(region_code, period, list(cbs_keys_needed)) if cbs_keys_needed else {}

    results: list[TypeGroupResult] = []
    for (btype, nstatus), building_ids in sorted(groups.items()):
        heating_values: list[float] = []
        simulated_ids: list[str] = []
        for bid in building_ids:
            building = mapper.map_building(bid)
            if building is None:
                continue
            heating = _simulate_heating_kwh(building, weather_df, use_milp=use_milp)
            if heating is not None:
                # CBS's own figures are per *dwelling* -- an MFH/AB
                # building_feature_id is a whole multi-unit *building*
                # (confirmed on real Loenen data, 2026-08-18: AB rows
                # have 257-756 m2 footprints, clearly whole apartment
                # buildings, not single units), so the raw simulated
                # total must be divided by the real dwelling-unit count
                # for a fair like-for-like comparison. 1.0 for SFH/TH
                # (already one dwelling per building_feature_id) is a
                # no-op division.
                units = source.buildings.loc[
                    source.buildings["building_feature_id"] == bid, "residential_units",
                ]
                units_value = float(units.iloc[0]) if len(units) and pd.notna(units.iloc[0]) else 1.0
                heating_values.append(heating / units_value)
                simulated_ids.append(str(bid))

        cbs_key = BUEM_TYPE_TO_CBS_KEY.get((btype, nstatus))
        cbs_figure = cbs_data.get(cbs_key) if cbs_key else None
        conversion = (
            gas_m3_to_useful_heat_kwh(cbs_figure.gas_m3_per_year)
            if cbs_figure is not None and cbs_figure.gas_m3_per_year is not None
            else None
        )

        results.append(TypeGroupResult(
            building_type=btype,
            neighbour_status=nstatus,
            cbs_key=cbs_key,
            n_simulated=len(heating_values),
            mean_simulated_heating_kwh=(sum(heating_values) / len(heating_values)) if heating_values else None,
            cbs_gas_m3_per_year=cbs_figure.gas_m3_per_year if cbs_figure else None,
            cbs_conversion=conversion,
            building_ids=simulated_ids,
        ))

    return results


def _simulate_heating_kwh(building: Building, weather_df: pd.DataFrame, *, use_milp: bool) -> float | None:
    """Run one building through the same real
    AttributeBuilder/CfgBuilding/ModelBUEM path ``batch.py``/
    ``provider_comparison.py`` use, returning annual heating demand
    (kWh) or ``None`` on any per-building failure (logged, not raised --
    one bad building shouldn't abort the whole comparison)."""
    from buem.integration.scripts.attribute_builder import AttributeBuilder
    from buem.thermal.model_buem import ModelBUEM

    try:
        attrs = dict(building_attrs_from(building))
        attrs["weather"] = weather_df
        attrs["use_provided_weather"] = True
        merged = AttributeBuilder(payload_attrs=attrs).build()
        cfg = CfgBuilding(merged).to_cfg_dict()
        model = ModelBUEM(cfg)
        model.sim_model(use_milp=use_milp)
        return round(float(pd.Series(model.heating_load).sum()), 2)
    except _PER_BUILDING_ERRORS as exc:
        logger.warning("building_feature_id=%s: simulation failed (%s: %s)",
                        building.identity.building_feature_id, type(exc).__name__, exc)
        return None


def format_report(results: list[TypeGroupResult]) -> str:
    """Plain-text summary table -- one row per group."""
    lines = [
        (f"{'type':6s} {'neigh':8s} {'n':>3s} {'buem kWh':>10s} {'CBS m3/yr':>10s} "
        f"{'CBS->kWh':>10s} {'ratio':>7s}"),
    ]
    for r in results:
        buem_val = f"{r.mean_simulated_heating_kwh:.0f}" if r.mean_simulated_heating_kwh is not None else "—"
        cbs_gas = f"{r.cbs_gas_m3_per_year:.0f}" if r.cbs_gas_m3_per_year is not None else "—"
        cbs_kwh = f"{r.cbs_conversion.useful_heat_kwh:.0f}" if r.cbs_conversion is not None else "—"
        ratio = f"{r.ratio_simulated_to_cbs:.2f}" if r.ratio_simulated_to_cbs is not None else "—"
        lines.append(
            f"{r.building_type:6s} {r.neighbour_status:8s} {r.n_simulated:3d} "
            f"{buem_val:>10s} {cbs_gas:>10s} {cbs_kwh:>10s} {ratio:>7s}"
        )
    return "\n".join(lines)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare buem's simulated heating demand against real CBS gas statistics.")
    parser.add_argument("--data-dir", type=str, required=True)
    parser.add_argument("--u-value-overrides", type=str, default=None)
    parser.add_argument("--region-code", type=str, required=True, help='e.g. "GM0200" for Apeldoorn')
    parser.add_argument(
        "--period", type=str, default=None,
        help='CBS "Perioden" code, e.g. "2024JJ00". Defaults to "<weather-year>JJ00" -- '
             "matching CBS's real consumption year to the simulated weather year matters: "
             "confirmed 2026-08-18 that Apeldoorn's real gas consumption roughly halved "
             "2018->2024 (conservation/insulation/heat-pump trends), so comparing 2024 CBS "
             "against 2018-weather-simulated demand was a real, non-trivial mismatch, not a "
             "rounding error. Pass explicitly to compare mismatched years on purpose.",
    )
    parser.add_argument("--samples-per-type", type=int, default=3)
    parser.add_argument("--weather-year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--weather-provider", type=str, default=DEFAULT_WEATHER_PROVIDER)
    parser.add_argument("--use-milp", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> list[TypeGroupResult]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    args = _build_arg_parser().parse_args(argv)
    period = args.period if args.period is not None else f"{args.weather_year}JJ00"
    results = run_validation(
        args.data_dir,
        u_value_overrides_path=args.u_value_overrides,
        region_code=args.region_code,
        period=period,
        samples_per_group=args.samples_per_type,
        weather_year=args.weather_year,
        weather_provider=args.weather_provider,
        use_milp=args.use_milp,
    )
    print(format_report(results))
    return results


if __name__ == "__main__":
    main()


__all__ = ["TypeGroupResult", "format_report", "main", "run_validation"]
