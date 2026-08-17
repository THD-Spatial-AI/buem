# Changelog

All notable changes to BuEM are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.2.0] - 2026-08-18

### Added

- **`buem.analysis.netherlands`**: a buem-vs-CBS validation script,
  built and run for real. `cbs_reference.py` queries CBS's real
  regional gas/electricity consumption statistics (table 81528NED) live
  via stdlib `urllib` (no new dependency); `gas_conversion.py` converts
  gas m³ to useful heat kWh via three separately-documented factors
  (official 9.769 kWh/m³ calorific value; a 78% space-heating share,
  since CBS's figure also includes hot water/cooking and `ModelBUEM`
  simulates space heating only; a 90% boiler-efficiency assumption);
  `validation.py` runs real buildings through the full simulation
  pipeline grouped by housing type and reports the comparison. The
  first real run immediately found and fixed a real bug in the
  comparison itself (not a buem heating-model error): apartment-
  building groups compared a whole multi-unit *building*'s simulated
  total against CBS's *per-dwelling* figure. Fixed by carrying RIVM's
  real dwelling-unit count through as a new `residential_units` column
  and normalizing before comparing — dropped those groups' ratios from
  10-80× off to 2.4-9.8×. Round 2: `--period` now defaults to matching
  `--weather-year` (verified real CBS 2018 data exists via the same live
  API, resolving the 2024-CBS-vs-2018-weather mismatch without needing
  new weather-archive access); re-ran with matched years and a
  5×-larger sample specifically to test whether small-sample noise
  explained the remaining gap — it didn't (TH's two `neighbour_status`
  subgroups agree to within 0.2% across 5 different buildings each).
  AB/MFH/TH settled into a persistent ~2-7× too-high band that survived
  both fixes — genuinely still open, see `.claude/residential/open.md`.
- **Non-residential buildings linked to occupancy's service-building
  path** instead of full exclusion — `nl_building_classifier` now checks
  a flagged building's real footprint area (`MIN_SERVICE_BUILDING_
  FOOTPRINT_M2`, 50 m²) before routing: large real structures (2,125 m²/
  1,718 m² in Loenen) link to occupancy's `"warehouse"` service type via
  a new `service_building_type` column; buildings too small to be real
  occupied structures (16 m²/5 m² — garden greenhouses, not commercial
  buildings) are excluded from both residential and service modeling
  rather than force-fit into either.
- **Netherlands pipeline verified against a second, independent
  community (Heeten, Overijssel) with zero code changes** —
  `src/buem/data/buildings/netherlands_heeten/`, 2,675 buildings, same
  real-data results as Loenen (100% RIVM match, 23.9% label coverage,
  100% TABULA archetype match, real end-to-end `LOD2Mapper` mapping).
- **PostgreSQL/3DCityDB access confirmed** and used to independently
  corroborate the Netherlands duplicate-row bug's origin: the live
  database's `city2tabula.lod2_building_feature`/`lod2_child_feature_
  surface` row counts match the old buggy CSV export exactly, confirming
  the bug lives in the database itself, not just an export step; its
  `lod3_*` tables exist but are empty, confirming no real LOD3 window/
  door geometry is available anywhere for this region.
- **Real CBS regional energy-consumption benchmark data found** (CBS
  opendata table 81528NED, freely queryable via OData) — real 2024
  average gas/electricity consumption for Apeldoorn municipality (Loenen's
  own), broken down by exactly the housing-type categories
  `nl_building_classifier` already reproduces. Documented as a ready-to-
  use validation reference in `.claude/residential/open.md`; not yet
  built into an actual comparison script.
- **Netherlands TABULA archetype linking + editable U-value table**: three
  new modules close the gap the CityJSON regeneration (below) deliberately
  left open. `nl_building_classifier` derives building type/attachment
  status by reproducing CBS's own published `woningtype` methodology
  (connected-building count from this session's geometric party-wall
  detection + residential-unit count from RIVM). `rivm_energy_labels`
  queries the real Dutch energy-labels GeoPackage (~11.35M rows, ~3.2 GB)
  via targeted `sqlite3` queries, never a full-table load. `nl_archetype_
  mapper` links each building to a real bundled TABULA archetype row
  (construction year, or a real energy label as an override where
  present — 24% of Loenen) via `tabula_helpers.lookup_tabula_archetype()`
  (now parameterized onto any TABULA sheet, not hardcoded to the German
  one). `LOD2Mapper` gained an optional `u_value_overrides` parameter so
  the new, plain-CSV `u_value_reference.csv` (year-class × building-type
  → wall/roof/floor/window/door U-values, extracted from real TABULA NL
  data and cross-validated against independently-researched Bouwbesluit/
  NTA 8800 Rc-value history) is actually consulted, not just documentation
  — and `geometry_utils.building_lat_lon()` is finally wired into
  `LOD2Mapper` itself (a pre-existing gap). Verified end-to-end: 3,101/
  3,101 residential Loenen buildings (100%) now get a real TABULA match,
  and `LOD2Mapper.map_building()` succeeds with real U-values, synthesized
  windows/doors/ventilation, and real coordinates where it previously
  returned `None` for every Netherlands building. See `docs/source/
  modules/netherlands.rst` (new page) and `.claude/residential/
  resolved.md` for the full methodology and evidence.
- **`PostgresBuildingSource` reads connection config from `.env`**
  (`BUEM_PG_HOST`/`PORT`/`DATABASE`/`USER`/`PASSWORD`) instead of only
  accepting hardcoded constructor arguments — `database`/`user`/`password`
  are now required (explicit arg or env var); previously defaulted
  silently to `localhost`/`postgres`/`postgres`/`city2tabula_germany`,
  which could attempt a connection with wrong credentials instead of
  failing clearly. See `.env.example`.
- **`CsvBuildingSource` + `geometry_utils`**: a third building-data source
  (alongside `ExcelBuildingSource`/`PostgresBuildingSource`), reading
  plain CSV exports of the same three tables — for regions with a CSV
  drop instead of an Excel workbook or a live Postgres connection (built
  for a real Netherlands/Loenen dataset). `geometry_utils.py` decodes a
  building's real `(latitude, longitude)` from its `building_centroid_geom`
  WKB geometry (hand-rolled point decoder, no new dependency for that
  part) and reprojects via `pyproj` (new dependency, added to
  `infrastructure/env/buem_env.yml`). See `.claude/residential/
  resolved.md` for the full writeup, including a real-data incident along
  the way (an initial CSV export was missing pre-computed surface
  geometry columns the pipeline needs; resolved by re-exporting the
  correct table, not by buem growing a new 3D geometry engine).
- **`buem.analysis` package**: reusable (not scratchpad) tooling for
  comparing buem's simulated heating/cooling/electricity demand — and the
  raw T/GHI/DNI/DHI weather inputs themselves — across weather providers
  for one or many buildings picked directly from the bundled TABULA Excel/
  PostgreSQL source. `weather_providers.py` (multi-provider extraction,
  reusing `weather_cache`'s feather-cache convention, with logged fallbacks
  for known archive gaps), `building_selection.py` (filtered building
  picking + a wall-exposure sanity check), `provider_comparison.py` (runs
  one building through the full `AttributeBuilder`/`CfgBuilding`/
  `ModelBUEM` pipeline once per provider), `summarize.py` (annual/monthly
  aggregation + pairwise GHI difference metrics), `report.py` (a
  self-contained HTML report, run and opened locally, no external tooling
  required), `batch.py` (multiprocessed many-building runs to Parquet,
  `python -m buem.analysis.batch`, portable to any machine with the same
  env vars — deliberately not itself wired to any specific remote host).
- **Per-provider weather year-range validation**: each weather provider's
  processed archive only covers a specific calendar-year window (tightened
  2026-08-14 per consultation — a data-availability fact about each
  archive, not a buem design choice): `era5-land` 1980-2025, `cosmo-rea6`
  1995-2018, `merra-2` 1950-2025. `weather.year` outside the resolved
  provider's range (explicit or the `merra-2` default) is now rejected at
  validation time with a clear message naming the valid range, instead of
  an opaque `FileNotFoundError` three layers deep during `AttributeBuilder`.
  Enforced both by `geojson_validator.py` (the real gate) and declaratively
  in `versions/v4/request_schema.json` via `allOf`/`if`/`then`, for any
  other consumer validating directly against the schema file.
- **`buem.weather.profile` gains a `json` format** (now the default —
  confirmed 2026-08-14 as EnerPlanET's actual format): an array of hourly
  records, each `{time, T, GHI, DHI, DNI}`. `csv`/`parquet` remain
  supported for other/internal callers.
- **Window/door azimuth and tilt now always match their parent wall/roof**:
  new `buem.buildings.mapping.live_synthesis.normalize_opening_azimuths()`,
  wired into `CfgBuilding.to_cfg_dict()` alongside `synthesize_missing_openings()`.
  A caller-supplied Window/Door element whose `azimuth`/`tilt` disagrees
  with the Wall/Roof element it declares as its `surface`/`parent_id` is
  corrected to the parent's value (logged as a warning), rather than
  silently modeling a window facing a different direction than the wall
  it's embedded in. No-op for internally-synthesized openings (already
  consistent by construction); ventilation is excluded (azimuth/tilt play
  no role in the ISO 13790 model there).

### Changed

**BREAKING: live API contract promoted from v3 to v4.**
`geojson_validator.py` now validates and converts against
`versions/v4/` instead of `versions/v3/` (2026-08-14; sign-off: this
session, see CLAUDE.md "Guardrails" — promoted on the basis that the
EnerPlanET developer told the user, 2026-08-13, they are already working
on their own v5). `versions/v3/` is retained as an archived, deprecated
snapshot. See `versions/v4/DRAFT.md`'s promotion note and
`VERSIONING.md`'s new `v4.0.0` entry for the full detail, including which
two schema-documented fields were deliberately left unwired (rejected,
not silently ignored, if sent — `weather.use_percentile`/`percentile`,
`solver.compute_cooling`).

- **BREAKING**: `building.building_type` is now validated against an
  enforced set (4 TABULA residential codes + occupancy's 8 registered
  service-building types, read live from `RESIDENTIAL_BUILDING_TYPES` and
  `occupancy.SERVICE_BUILDING_TYPES` — not a hand-copied enum). A request
  with an unrecognized `building_type` is now rejected at validation
  time, instead of failing later and less legibly inside
  `AttributeBuilder.generate_electricity_profile()`.
- New optional `building.equipment` field reaches real requests:
  per-item household-equipment inclusion/exclusion, `{equipment_id: bool}`
  (reshaped from an earlier `{mode, items}` draft to be more expressive
  and closer to the original ask — see `AttributeBuilder
  ._resolve_equipment_table()`). `true` guarantees an item is treated as
  owned; `false` guarantees exclusion; an omitted id keeps occupancy's own
  archetype-adjusted default. Residential `building_type` only — ignored,
  with a logged warning, for service-building types (`occupancy
  .ServiceBuildingProfile` has no per-item equipment selection yet, see
  `.claude/occupancy_module_activities.md`). New `buem.config
  .building_registry.HOUSEHOLD_EQUIPMENT_TYPES` (29 ids) validates
  selector keys.
- `buem.weather.provider`/`year` now reach real requests (previously only
  a genuine v2-format request or a direct `AttributeBuilder` call could
  set these). Deliberately does *not* fall back to the request's
  `start_time` calendar year despite `DRAFT.md`'s originally-documented
  intent for `year` — confirmed against real fixtures this can silently
  request a year with no local weather archive, turning a working request
  into a hard failure; `year` is forwarded only when the caller explicitly
  supplies `buem.weather.year`.
- New file-based profile inputs, both reaching real requests: **`buem
  .weather.profile`** (caller-supplied T/GHI/DHI/DNI timeseries, CSV or
  Parquet, first column as timestamp index) and **`buem.inputs
  .electricity_load_profile`** (caller-supplied hourly electricity array,
  CSV/JSON/gzipped-JSON, `kWh`/`kW`/`Wh` unit-converted, indexed against
  the request's resolved year and reconciled with buem's own half-hour-
  offset weather index via the same nearest+tolerance reindex already used
  elsewhere). New `buem.integration.scripts.profile_file_loader` module;
  new `BUEM_DATA_DIR` env var convention (`buem.env`) for where a real
  deployment mounts these files. Both raise a clear validation error (not
  a crash, not a silent fallback) for a missing/malformed file.
- New `buem.config.building_registry` module: the pure, side-effect-free
  constants (`RESIDENTIAL_BUILDING_TYPES`, `HOUSEHOLD_EQUIPMENT_TYPES`,
  etc.) split out of `cfg_attribute.py` specifically so
  `geojson_validator.py` can use them for request-structure validation
  without pulling in `cfg_attribute.py`'s own eager weather fetch as an
  import-time side effect. `cfg_attribute.py` re-exports the same names
  unchanged — no change for existing importers.
- **`use_provided_elecLoad` now preserves occupancy-generated
  `Q_ig`/`occ_nothome`/`occ_sleeping`**: previously this flag skipped
  calling `occupancy` entirely, keeping whatever was already in
  `merged_attrs` for all four profile series. It now still runs a real
  `HouseholdProfile`/`ServiceBuildingProfile` generation and substitutes
  only `elecLoad`, via `occupancy.to_buem_profiles(elec_load=...)`
  (available since occupancy v3.1.0, previously unused by buem) — a
  behavior change for anyone relying on the old total-bypass semantics.

### Added

- **`buem.buildings.datasources.cityjson_extractor`**: extracts clean LOD2
  building geometry (walls/roofs/floors with real area/tilt/azimuth,
  building-level aggregates, storeys, a real lat/lon-capable centroid, and
  geometrically-detected party walls) directly from a CityJSON (3D BAG)
  source — replacing the Netherlands/Loenen dataset's dependency on
  city2tabula's pipeline entirely, after that pipeline turned out to carry
  two independent, compounding duplicate-geometry bugs (see the `Fixed`
  entries below and `.claude/residential/resolved.md`'s "Netherlands
  (Loenen) building data" entry for the full story). Deliberately does
  **not** attempt TABULA archetype matching — every regenerated row's
  `tabula_variant_code_id` is null pending a separate, explicitly-deferred
  discussion; `LOD2Mapper.map_building()` cannot succeed for any
  Netherlands building until that lands. `src/buem/data/buildings/
  netherlands/lod2_building_feature.csv`/`lod2_child_feature_surface.csv`
  were regenerated with it; old city2tabula CSVs kept for reference under
  `netherlands/_city2tabula_backup/`. Verified exhaustively against 3D
  BAG's own aggregate attributes for all 3,105 buildings (median ratio
  1.000, one explained outlier — a real two-`BuildingPart` building). See
  the module's own docstring for the full methodology and calibration
  evidence.

### Fixed

- **Roof solar gain was silently azimuth-independent for German-path
  buildings** — `LOD2Mapper` hardcoded every roof element's azimuth to
  0.0 on a stale claim ("no role in solar calcs for roofs") that turned
  out to be false: `model_buem._calcRadiation()` passes every element's
  real tilt and azimuth through `pvlib.irradiance.get_total_irradiance()`,
  so roof solar gain genuinely depends on orientation. The real German
  LOD2 database has usable azimuth data for 64.8% of roof surfaces
  (10,732/16,558) that was being silently discarded — every non-flat
  German roof was modeled as if it faced due north. Fixed: roofs now use
  the same real-value/negative-NaN-fallback handling walls already had.
  Netherlands was unaffected (already computed real per-plane roof
  azimuth from CityJSON geometry). `docs/source/modules/buildings.rst`'s
  stale assumption-table entry corrected to match.
- **`cfg_attribute.py`'s re-export contract, regressed by an automated
  lint fix and caught before shipping** — a `ruff check --fix` pass
  deleted 3 of its 10 `building_registry.py` re-exports
  (`DEFAULT_ARCHETYPE_BY_BUILDING_TYPE`/`HOUSEHOLD_EQUIPMENT_TYPES`/
  `RESIDENTIAL_BUILDING_TYPES`) because ruff's per-file "unused import"
  check can't see them being imported *from* this module elsewhere
  (`attribute_builder.py`, several tests) — caught immediately by
  `mypy src` right after. Restored, plus an explicit `__all__` added
  (none existed before) so ruff recognizes the re-exports as
  intentional going forward. Full local CI mirror (ruff/mypy/181
  pytest/`buem validate`) clean after.
- **`cityjson_extractor` silently over-counted area for any face with a
  hole** (courtyards, light-wells) — its Newell's-method area computation
  read only the exterior ring, ignoring interior rings entirely. Found by
  re-auditing the extractor after a direct question about whether real
  geometry (not city.json attributes) was actually being used. Affects
  144 faces / 128 buildings (4.1% of 3,105) in the current Loenen
  dataset, up to ~37% over-count for one individual face. Fixed: sum
  every ring's raw Newell vector across the whole face before taking the
  magnitude (verified first, on real data, that interior rings wind
  opposite the exterior ring, so this correctly subtracts hole area via
  vector cancellation). Dataset regenerated with the fix. New unit tests
  in `tests/test_cityjson_extractor.py`. See `.claude/residential/
  open.md` for the fuller writeup, including why 3D BAG's own aggregate
  attributes turned out not to be a clean ground-truth check for the
  affected buildings (they don't subtract hole area either).
- **A wall too small to receive a window (`< MIN_WALL_AREA_FOR_WINDOWS`,
  5 m²) still had its would-be window area subtracted from its own opaque
  `net_area`** — `element_factory.synthesize_openings()` computed
  `window_area` from the TABULA ratio for every wall, then
  `create_windows()` separately skipped building an actual window element
  for small walls; `WallInfo.net_area` used the same (still nonzero)
  `window_area` regardless, so that area belonged to neither the opaque
  wall nor a window element — silently missing from the envelope
  entirely. Found while verifying window/door/ventilation area
  bookkeeping end-to-end. Fixed: `window_area` is now forced to `0.0` for
  a wall under the size cutoff, consistent with the existing
  `azimuth_known` handling in the same loop. Affects both `LOD2Mapper`
  (offline path) and `live_synthesis` (live path, full-synthesis case) —
  they share this function. New regression test in
  `tests/test_live_synthesis.py`.
- **`CsvBuildingSource` was silently loading ~2× too much wall/roof/floor
  area per Netherlands/Loenen building** (Layer 1 of a two-layer
  duplicate-row bug in the underlying export): `lod2_child_feature_surface
  .csv` rows identical in every column except `id`/`child_row_id` are now
  dropped on load (`_dedup_surfaces()`), and `lod2_building_feature.csv`'s
  own `area_total_wall`/`area_total_roof`/`area_total_floor`/
  `surface_count_wall`/`surface_count_roof` columns — which carried the
  same bug independently, as stored aggregates rather than values derived
  from `surfaces` at read time — are recomputed from the deduped surfaces
  (`_recompute_building_aggregates()`), so `LOD2Mapper`'s `A_ref`
  computation isn't fed a stale, still-inflated value even after the
  surface-row fix. Verified against building 37206: 16 walls / 4 roofs /
  4 floors / `A_ref`=150.7 m² → 8 walls / 2 roofs / 2 floors / `A_ref`=
  75.35 m². **A second, still-open duplication layer was found while
  verifying this fix against real CityJSON ground truth — see
  `.claude/residential/open.md`; Netherlands/Loenen heating-demand
  numbers are not yet trustworthy end-to-end.** See
  `.claude/residential/resolved.md`.
- **MILP big-M design-load computation silently swallowed failures**:
  `_addConstraints_sequential()` (runs on every `sim_model()` call, LP or
  MILP) wrapped `calcDesignHeatLoad()` in a bare `try/except: design =
  1000.0` — any failure was replaced with a made-up value, no log, no
  error. Found via a user-prompted audit for exactly this pattern.
  Fixed: now logs a warning and re-raises instead of substituting a
  silent fallback. See `.claude/resolved.md`.
- **Two `model_buem.py` crashes on real party-wall buildings**, both
  found via `buem.analysis.batch`'s smoke test right after the
  `validate_cfg()` fix below: (1) `_init5R1C()`'s opaque-component
  solar-gain loops read only a component-level `Walls`/`Doors`/`Roof`
  `U`, crashing with `TypeError` on any component that only has
  per-element `U` (no single component-level default — e.g. a mix of
  exposed and party walls); fixed via a new
  `_resolve_opaque_element_u()` helper that falls back to each element's
  own `U`, mirroring how `_initEnvelop()` already handled this correctly
  for the H/conductance calc a few lines earlier in the same method.
  (2) A 0-exposed-wall building (nowhere to synthesize a window) ended
  up with a configured-but-empty `Windows` component, which raised
  `ValueError: No window elements found but windows are configured`
  instead of the zero solar gain that's physically correct here —
  inconsistent with the code's own adjacent `H_windows=0.0`/Floor-gain
  handling. Fixed: zero windows now means zero window solar gain, not an
  error. Verified against the exact real buildings that originally
  crashed (44424/42868/60342/18763/30542, all now `status="ok"`). See
  `.claude/residential/resolved.md` for the fuller writeup.
- **`summarize.summarize_weather()` crashed on a single-provider run**:
  `_pairwise_ghi_diff()` builds one row per *pair* of providers, so a
  single-provider call (e.g. `report.build_html_report()` for just
  `merra-2`) produces zero rows — `pd.DataFrame([])` has no columns at
  all, so the subsequent `.set_index("pair")` raised `KeyError: "None of
  ['pair'] are in the columns"`. Found by `tests/test_analysis.py`'s new
  end-to-end report test (deliberately single-provider, to keep the real
  simulation it drives fast). Fixed: the zero-pairs case now returns an
  explicitly-shaped empty `DataFrame` (right columns, `"pair"` index
  name) instead of falling through to the crash.
- **`validate_cfg()` rejected legitimate `U=0` party walls outright**:
  the per-component and per-element wall-U checks used `float(u) <= 0`,
  treating zero the same as a negative (physically impossible) value.
  But `U=0` is buildings.rst's own documented convention for a shared/
  party wall (`b_transmission=0`, no heat transfer modeled to an adjacent
  heated space) — confirmed physically and numerically safe throughout
  `model_buem.py`, where `U` is only ever a multiplicative factor, never
  a divisor. Since `AttributeBuilder.build()` calls `validate_cfg()` on
  every real request, this meant **any building with any party wall
  failed validation and could never be simulated at all — live API
  traffic included, not just batch/analysis tooling.** Found via
  `buem.analysis.batch`'s smoke test on real TH/MFH buildings with party
  walls. Fixed: both checks now use `float(u) < 0` (reject only negative
  U). See `.claude/residential/resolved.md` for the fuller writeup,
  including two further, distinct, deliberately-unfixed bugs this same
  investigation surfaced on the same buildings (`.claude/residential/
  open.md`).
- **`LOD2Mapper` never read the matched TABULA archetype's own indoor
  setpoint (`theta_i`)**: every offline-pipeline-mapped building silently
  used `ThermalProperties`' generic 21.0°C `comfortT_lb` default regardless
  of what its archetype actually specified — a continuous +1°C bias (no
  TABULA-equivalent night/weekend setback either) versus TABULA's own
  reference calculation. Found while investigating a large buem-vs-TABULA
  heating-demand gap (buem ~51,000-55,000 kWh/year vs. TABULA's own
  36,639 kWh for `DE.N.SFH.01.Gen`, `theta_i=20.0` for that archetype).
  Fixed: `comfortT_lb` now reads `theta_i` from the matched row (falling
  back to 21.0 unchanged when absent). `comfortT_ub` is untouched — no
  TABULA row equivalent; TABULA's residential reference calculation is
  heating-only. Real offsetting factors remain uninvestigated further
  (real vs. TABULA-reference floor/roof area for a given matched building,
  real hourly weather vs. TABULA's fixed national reference climate,
  occupancy-driven vs. TABULA's flat `phi_int` internal gains) — this fix
  addresses the one clearly-code-verified gap, not the full discrepancy.
- **`cfg_building.py` broke import on Python 3.11** (reported by the
  EnerPlanET developer, 2026-08-01, reproduced against a fresh 3.11.14
  `buem_env`): `CfgBuilding.from_json_file()` referenced its own
  enclosing class as a bare, unquoted return-type annotation with no
  `from __future__ import annotations` in the file — raises `NameError:
  name 'CfgBuilding' is not defined` at class-definition time on 3.11
  (masked on 3.14 by PEP 649/749 lazy annotation evaluation), breaking
  every import of the module and therefore the whole API server. Fixed
  by adding `from __future__ import annotations`, matching the
  convention already used elsewhere in this codebase (`live_synthesis.py`,
  `element_factory.py`, `tabula_helpers.py`). Audited the rest of the
  codebase for the same self-referencing-return-type pattern — one other
  superficially similar case (`ExcelBuildingSource.from_parquet()`) was
  already safe (that file already has the future import). Does **not**
  change `requires-python` — a separate, still-open cross-repo Python
  version alignment question, not decided here.
- **`h_room` (room height) hard-rejected real non-residential buildings
  above 5.0m** (reported by the EnerPlanET developer, 2026-08-01,
  reproduced against a real THD Deggendorf campus building with
  `room_height = 5.03m`, a mensa/communal space): the ISO 13790 sanity
  bound was `0 < h_room <= 5.0m`, sized for households (~3m). Widened to
  `0 < h_room <= 20.0m` (and `comfortT_lb`/`comfortT_ub` similarly widened
  to `[5, 35]°C`, was `[15, 30]`) to admit non-residential room heights —
  warehouses, gyms, lecture halls routinely exceed 5m. Already present in
  the working tree before this entry was written; documented here and in
  `docs/source/modules/thermal.rst` for the historical record.

## [3.1.0] - 2026-08-11

### Added

- **Internal LOD2 → LOD3 envelope synthesis**: windows/doors/ventilation
  are now computed internally by buem whenever a caller supplies wall/
  roof/floor geometry without them, instead of silently defaulting to
  zero — via new `buem.buildings.mapping.live_synthesis
  .synthesize_missing_openings()`, wired into `CfgBuilding.to_cfg_dict()`
  so both the live API path (`AttributeBuilder` → `CfgBuilding`) and the
  config-only/demo path are covered by one change. Reuses the same
  TABULA-ratio window/door/ventilation sizing rules
  `LOD2Mapper`'s offline Excel/PostgreSQL batch pipeline already
  implemented (`docs/source/modules/buildings.rst`), now shared via new
  `element_factory.synthesize_openings()`. Resolves a real TABULA
  archetype via new `tabula_helpers.lookup_tabula_archetype()` (matched
  from `building_type`/`construction_period`/`country`, or an explicit
  `bldg_tabula_id` override) against the bundled reference sheet; falls
  back to new, clearly-flagged safe-default ratios (15% window-to-wall
  per direction, 5% door-to-wall, logged as a warning) when no archetype
  matches, rather than leaving a building with zero glazing. Never
  overrides an explicitly-supplied, non-empty component. **No API
  contract or schema changes** — `building_type`/`construction_period`/
  `country` were already forwarded end-to-end by
  `geojson_validator.py::_convert_v3_to_v2()`; the only gap was that
  `CfgBuilding` silently dropped `construction_period`/`country` because
  they weren't registered `ATTRIBUTE_SPECS`, now fixed.
- `weather_cache.get_or_fetch_weather()` gained a second fetch backend:
  `_fetch_remote()` calls `weather`'s own point-query HTTP API
  (`UU-BUEM/weather`'s `GET /v1/weather/point`) instead of reading local
  processed archives directly, selected by whether `WEATHER_API_URL` is
  set (`WEATHER_API_KEY` sent as an `X-API-Key` header); unset, behavior
  is unchanged from the existing local-archive path. Answers the
  production-BUEM-microservice half of the still-open "how does buem
  reach weather's archives" question (see `CLAUDE.md`'s "Open
  follow-ups") for any deployment that can reach that HTTP API but not
  the archive filesystem directly — actually configuring
  `WEATHER_API_URL`/`WEATHER_API_KEY` for a real deployment remains
  separate, unstarted work. New `requests` dependency.
- New optional `archetype` building attribute, passed to
  `occupancy.HouseholdProfile` for residential buildings. When omitted,
  `cfg_attribute.DEFAULT_ARCHETYPE_BY_BUILDING_TYPE` maps `building_type`
  (`SFH`/`TH`/`MFH`/`AB`) to one of occupancy's registered archetypes as a
  first-pass default (a heuristic, not a derivation — `num_persons`
  remains the dominant signal).
- `num_persons`/`archetype` added to the `versions/v4/` draft schema's
  `building` object, next to the existing `capacity` field (tier 2, not
  yet reconciled with EnerPlanET). `seed` deliberately not added — see
  below.
- Floor-area-normalized internal gains for service buildings:
  `AttributeBuilder.generate_electricity_profile()` now passes `A_ref` as
  `floor_area_m2` to occupancy's `to_buem_profiles()`, which blends an
  area-normalized equipment/lighting component into `Q_ig` (all 8 service
  types now carry a `gain_w_per_m2`). Residential unaffected. Closes
  `occupancy_gains_handoff.md` Gap 1 on buem's side.
- `geojson_validator.py::_convert_v3_to_v2()` now forwards
  `capacity`/`num_persons`/`archetype` from a v3 request's `building`
  object into `building_attributes` (tier-1 file, edited with explicit
  user direction). Closes `occupancy_gains_handoff.md` Gap 2.
  Deliberately excludes `seed` — see "Changed" below.
- `tests/test_building_types.py::test_v4_building_type_enum_matches_occupancy`:
  a drift guard asserting the `versions/v4/` draft schema's
  `building_type` enum matches `occupancy.SERVICE_BUILDING_TYPES` exactly.
  Closes `occupancy_gains_handoff.md` Gap 3.
- All of the above re-verified (2026-08-10) against
  [`occupancy` v3.1.0](https://github.com/UU-BUEM/occupancy/releases/tag/v3.1.0)
  (commit `3a99029`), the real tagged/pushed release, not just the local
  working tree it was originally developed and tested against —
  `buem_env`'s `occupancy` reinstalled fresh from the `git+...@main` pin
  already declared in `pyproject.toml`/`buem_env.yml` (no pin change
  needed). Full pytest suite (21/21), `buem validate`, and manual Gap 1/2
  checks all pass identically.

### Removed

- Dead `cfg_attribute.py` attributes, never read anywhere else in the
  codebase: `A_Window_North`/`East`/`South`/`West`/`Horizontal`, `roofs`.
- `seed` removed from the `versions/v4/` draft schema (was briefly added,
  now reverted) and excluded from `_convert_v3_to_v2()`'s forwarding — an
  internal RNG-reproducibility knob, not an EnerPlanET-contract concept.
  `cfg_attribute.py`'s `ATTRIBUTE_SPECS["seed"]` documents this
  explicitly. See `.claude/occupancy_gains_handoff.md`'s "Seed ownership"
  note for the proposal that `occupancy` itself own a deterministic
  default instead of buem managing/exposing one.

### Changed

- `cfg_attribute.py`'s module-level demo `components` default now carries
  gross `Walls`/`Roof`/`Floor` geometry only (no hand-picked `Windows`/
  `Doors`/`Ventilation`) — the new internal synthesis pipeline fills the
  rest, so this example follows `buildings.rst`'s documented rules
  instead of arbitrary numbers. New `country`/`construction_period`
  `ATTRIBUTE_SPECS` (both optional, defaults `"NL"`/`""`); `bldg_tabula_id`
  (previously declared but unused) is now a real TABULA-archetype lookup
  override.
- `WallInfo` and front/back wall identification moved from
  `lod2_mapper.py` to `element_factory.py` (shared with the new live-path
  synthesis); `LOD2Mapper.map_building`'s window/door/ventilation logic
  refactored to call the new shared `synthesize_openings()` — behavior-
  preserving for the offline pipeline (covered by a new end-to-end test
  against the bundled reference workbook, `tests/test_live_synthesis.py`).
- **`occupancy` (UU-BUEM/occupancy) is now a compulsory dependency**, not
  an optional extra — moved from `[project.optional-dependencies]` to
  core `dependencies` in `pyproject.toml`/`buem_env.yml`. All `try/except
  ImportError` guards around `import occupancy` are removed; it's
  imported unconditionally like weather/pandas/pvlib. This mostly
  formalizes existing behavior: the real per-request path
  (`AttributeBuilder.generate_electricity_profile`) already had no
  fallback and raised if occupancy was missing.
- The synthetic sinusoidal fallback profile (`cfg_attribute.py`'s
  module-level example-house defaults) is retired along with the guards
  that triggered it — that was the only code path where it still fired.

### Fixed

- `tests/test_live_synthesis.py`'s 4 tests exercising the bundled TABULA
  reference workbook now skip cleanly (`requires_bundled_workbook`,
  mirroring `test_cache.py`'s existing `_skip_reason` pattern) in any
  environment without it, instead of failing — found immediately by this
  version's own CI run: the workbook is `.gitignore`d (repo-wide `*.xlsx`
  rule) and was never actually part of the git repository, only present
  on the developer machine these tests were first written against. A
  pre-existing gap (the offline `LOD2Mapper` pipeline needed this same
  file since it was written, just never had test coverage before), not
  introduced by this release — see `CLAUDE.md`'s new
  `tabula-workbook-access` open follow-up for the still-unresolved
  underlying question (real TABULA-archetype matching only works on a
  machine that happens to have this file today).

## [3.0.0] - 2026-08-04

### Added

- `latitude`/`longitude`/`year`/`weather_provider` now flow end-to-end from
  a request to the weather fetch: `year` defaults to a request's own
  `start_time` calendar year when not explicit (`geojson_processor.py`);
  `year`/`weather_provider` added as optional, validated fields on
  `geojson_validator.py`'s `BuildingAttributesSchema` (v2 request format).
  Mirrored (documentation only, not yet wired into any live request path)
  in the `versions/v4/` draft schema as a new `buem.weather: {provider,
  year}` object.

### Changed

- **`weather` (UU-BUEM/weather) is now a compulsory dependency**, not an
  optional extra — moved from `[project.optional-dependencies]` to core
  `dependencies` in `pyproject.toml`/`buem_env.yml`. All `try/except
  ImportError` guards around `import weather` are removed; it's imported
  unconditionally like pandas/pvlib. `occupancy` remains optional.
- **The bundled offline weather CSV is retired**
  (`src/buem/data/weather/COSMO_Year__ix_390_650.csv`, one static
  COSMO-REA6 grid cell) — deleted, along with every code path that read
  it. `cfg_attribute.py`'s module-level weather default is now a real
  `weather.get_point_weather()` fetch for a documented default location
  (`DEFAULT_LATITUDE`/`DEFAULT_LONGITUDE`/`DEFAULT_YEAR`/
  `DEFAULT_WEATHER_PROVIDER`), cached locally (gitignored feather file)
  exactly like any other building's fetch.
- `model_buem.py::_calcRadiation`'s defensive DNI-to-extraterrestrial clip
  and hard 1200 W/m² POA cap are removed — DNI/DHI/GHI are used as
  provided by the weather fetch, trusting it's already physically bounded,
  instead of buem re-sanitising a second time.
- `DEFAULT_WEATHER_PROVIDER` switched `era5-land` → `merra-2` (see Known
  Issues below for why).

### Removed

- **`allow_weather_fallback` removed entirely** from `AttributeBuilder`
  and `GeoJsonProcessor` (breaking: passing this keyword now raises
  `TypeError`). A failed per-building weather fetch always raises now —
  there is no fallback, since substituting any other location's weather
  (real fetch or static file) would silently model the wrong building.

### Known Issues

- **The `weather` package's real-simulation path is not fully verified
  yet.** Comparing `era5-land`/`merra-2`/`cosmo-rea6` at buem's own
  default test cell surfaced three upstream bugs in `weather`
  (`merra-2`'s `T` column NaN outside one month; `cosmo-rea6` point-query
  raising on a dataset-concat error; `era5-land` returning an implausible
  GHI spike from an unrepaired month-boundary de-accumulation issue).
  `merra-2` and `cosmo-rea6` are fixed in `weather`'s upstream working
  tree but **not yet released/installed here** — running the full test
  suite against the currently-pinned `weather` version fails 4/14 tests
  with `RuntimeError: Problem data contains NaN` (merra-2's still-present
  bug). `era5-land` remains blocked on its own unrepaired archive
  regardless. Do not treat a real thermal-model run against any
  `weather_provider` as verified until `weather` is upgraded past these
  fixes and the affected archive(s) are repaired.

## [2.0.1] - 2026-07-31

### Fixed

- `v2.0.0`'s CI run failed: several tests (`test_hash_debug.py`,
  `test_building_types.py`, two capacity tests in
  `test_attribute_builder_strictness.py`, `test_cache.py`) called
  `AttributeBuilder`/`GeoJsonProcessor` without opting into
  `allow_weather_fallback=True`. Locally this was masked because the dev
  environment lacks `weather`'s point-query extras (xarray/netcdf4),
  hitting the still-lenient `ImportError` branch; GitHub Actions' CI
  environment has those installed but no cached per-location weather
  data, hitting the new-in-`v2.0.0` strict `FileNotFoundError` branch
  instead. Added `allow_weather_fallback` as a pass-through parameter on
  `GeoJsonProcessor` (forwarded to `AttributeBuilder`) and set it
  explicitly in the affected tests, which legitimately don't need real
  per-location weather accuracy.

## [2.0.0] - 2026-07-31

### Added

- Services (non-residential) buildings are now routed through
  occupancy's `ServiceBuildingProfile` instead of being forced through
  `HouseholdProfile` — `AttributeBuilder.generate_electricity_profile`
  branches on `building_type`: TABULA residential codes
  (`RESIDENTIAL_BUILDING_TYPES`: `SFH`/`MFH`/`TH`/`AB`) use the existing
  household path; any of occupancy's 8 service-building ids
  (supermarket/office/restaurant/school/hotel/bakery/warehouse/clinic)
  use the new path. New `building_type`/`capacity` `AttributeSpec`s.
- `ModelBUEM`'s `comfortT_lb`/`comfortT_ub` now accept a per-timestep
  `pd.Series` (in addition to the existing scalar), letting a building
  express a real occupied/unoccupied setpoint schedule (e.g. a school
  closed nights/weekends/summer) instead of only the coarse annual
  `F_red_htr` reduction factor.
- `AttributeBuilder(..., allow_weather_fallback=True)` opts back into
  lenient bundled-weather substitution on a per-location fetch failure
  (see Changed, below, for the new default).
- Six non-residential dummy fixtures
  (`src/buem/data/buildings/dummy/*.json`) updated from inert placeholder
  `building_type` codes to real occupancy type ids.
- `tests/test_building_types.py`, `tests/test_attribute_builder_strictness.py`.
- `docs/` (Sphinx/ReadTheDocs source) reintegrated — removed during the
  `v1.1` submodule-extraction refactor, never recreated until now.
  `pyproject.toml` `docs` extra (`sphinx`, `sphinx-rtd-theme`) restored.
  Content updated for drift accumulated since removal (occupancy/weather
  package split, v3 API schema, this release's changes); `modules/
  results.rst`/`technology.rst` now clearly flagged as documenting
  currently-nonexistent modules rather than presented as working.
- `src/buem/integration/json_schema/versions/v4/` — draft (not agreed
  with EnerPlanET) proposal for a `building_type` enum + `capacity`
  field; inert, not wired into any live validation path. See its
  `DRAFT.md`.
- `.claude/` known-issues/decisions log (mirrors `occupancy`'s/
  `weather`'s own convention) and `.claude/release-workflow.md`.

### Changed

- **Breaking**: `AttributeBuilder.build()` now raises `ValueError` if
  `latitude`/`longitude`/`components`/`A_ref` weren't explicitly supplied
  via `payload_attrs` or `db_fetcher`, instead of silently substituting
  `ATTRIBUTE_SPECS`' generic ~100 m² example-house defaults. Does not
  affect the live GeoJSON API in practice — `geojson_validator.py`'s
  v3→v2 conversion already unconditionally populates all four keys
  (with its own fallbacks) before `AttributeBuilder` ever sees the
  payload — but is a breaking change for any code calling
  `AttributeBuilder` directly with a partial `payload_attrs`.
- **Breaking**: a `db_fetcher` that raises now propagates (wrapped
  `RuntimeError`) instead of logging a warning and silently continuing
  with generic defaults.
- **Breaking**: `generate_weather_profile`'s per-location weather fetch
  now raises by default when the `weather` package is installed but has
  no data for the specific requested location/year/provider (previously
  silently substituted the bundled reference-location CSV). Fetches that
  fail because `weather`'s own optional extras are absent (e.g. xarray/
  netcdf4) remain a lenient fallback, unchanged. See `allow_weather_fallback` above.
- Profile/weather-index reindexing (`Q_ig`/`elecLoad`/`occ_nothome`/
  `occ_sleeping`) now raises if any timestep can't align within a
  30-minute tolerance, instead of silently zero-filling — plain
  `method="nearest"` reindexing never produces `NaN`, so the previous
  `fill_value=0.0` could silently paper over a real year/timezone
  mismatch.
- `ModelBUEM._initEnvelop`'s `h_room` sanity bound widened from 5.0 m to
  20.0 m (was blocking legitimate tall non-residential spaces —
  warehouses, sports halls, industrial halls).
- `ModelBUEM._init5R1C`'s `comfortT_lb`/`comfortT_ub` sanity range
  widened from [15, 30] °C to [5, 35] °C (was blocking legitimate
  frost-protection-only setpoints for lightly-conditioned industrial/
  warehouse space).

### Fixed

- `capacity` (service-building sizing) is now explicitly cast with
  `int()`, matching `num_persons` — previously a string `capacity` from a
  JSON payload would reach `ServiceBuildingProfile`'s `self.capacity <=
  0` check and raise an unrelated-looking `TypeError`.
- `BUEM_RESULTS_DIR`/`BUEM_LOG_DIR` are now created by `load_env()`
  directly instead of only being `os.environ.setdefault`, fixing a CI
  "Smoke test CLI" failure (`buem validate` reported `BUEM_LOG_DIR
  [MISSING]`) on a genuinely fresh checkout with no leftover `results/`/
  `logs/` directories from a prior run.
- Resolved all remaining `ruff` (180) and `mypy` (74) findings repo-wide,
  no suppressions; applied `ruff --fix` repo-wide (import sorting,
  `Optional[X]` → `X | None`, unused vars/imports).

## [1.2.1] - 2026-07-30

### Changed

- Removed the `numpy<3`/`pandas<3` upper-bound caps from
  `infrastructure/env/buem_env.yml` (floors only now: `numpy>=1.26`,
  `pandas>=2.0`), matching the same change in `occupancy`'s/`weather`'s own
  `pyproject.toml`. The caps weren't protecting anything in practice — both
  sibling repos had already drifted past them — and `buem`'s test suite,
  plus occupancy's (69/69) and weather's (55 passed/2 skipped) full pytest
  suites, all pass clean on numpy 2.4-2.5/pandas 3.0.x.
- `gunicorn` removed from `infrastructure/env/buem_env.yml` — it's Unix-only
  (fork()-based), has no win-64 conda-forge build, and was breaking
  `conda env update` on Windows dev machines. Now installed directly in
  `infrastructure/container/Dockerfile`'s builder stage instead, where it's
  actually used (API server CMD); `pyproject.toml`'s `server` extra still
  declares it for anyone installing outside conda.

### Fixed

- `weather_env`'s `mkl` BLAS build was colliding with `cupy`'s bundled CUDA
  DLLs on Windows, crashing numpy on plain import (unrelated to buem's own
  code, but blocked verifying the pin change above against a real weather
  install). Fixed upstream in `weather`'s own `infrastructure/env/
  weather_env.yml` (pinned `libblas=*=*openblas`); `cupy` also removed
  there as unused.

## [1.2.0] - 2026-07-29

### Fixed

- **Occupancy integration was dead code**: `cfg_attribute.py`/`attribute_builder.py`
  imported a package/module path (`buem_occupancy.occupancy_profile.OccupancyProfile`)
  that has never existed, so the `try/except ImportError` always failed silently
  and every build used a synthetic sinusoidal electricity-load fallback —
  regardless of whether `occupancy` was actually installed. Now imports the
  real `occupancy` package (`HouseholdProfile`, `ElectricityConsumptionProfile`,
  `to_buem_profiles`) and uses `to_buem_profiles()` to derive all four series
  `ModelBUEM` requires (`Q_ig`, `elecLoad`, `occ_nothome`, `occ_sleeping`) from
  one real occupancy simulation, instead of hand-rolling three of them as
  hardcoded sine curves regardless of `occupancy`'s availability. The
  sinusoidal fallback is kept, but now only used when `occupancy` genuinely
  isn't installed.
- `readme.md`/`pyproject.toml` told users to `pip install buem-occupancy` /
  `pip install buem-weather` — packages/repos that don't exist. Now
  `pip install buem[occupancy,weather]`, matching the extras actually
  declared in `pyproject.toml`.
- Duplicate stale weather CSV/feather files at `src/buem/data/` (root),
  superseded by `src/buem/data/weather/` since an earlier reorg; two test
  scripts (`tests/run_test.py`, `tests/test_energy.py`) were still pointing
  `BUEM_WEATHER_DIR` at the stale root location, which is why the
  duplicates were never cleaned up. Both fixed to the canonical path.

### Added

- **Dynamic per-location weather**: `AttributeBuilder` now fetches a
  location-specific `T`/`GHI`/`DHI`/`DNI` DataFrame per building via the
  optional `weather` package's `get_point_weather(lat, lon, year,
  provider=...)`, instead of always using one bundled static CSV
  regardless of building location. Falls back gracefully (with a warning)
  to the bundled CSV when `weather` isn't installed or no processed
  archive exists for the requested location/year — existing zero-optional-
  dependency behaviour is unchanged. New `weather_provider` (default
  `"era5-land"`) and `use_provided_weather` attributes.
- Location-keyed weather cache (`buem.config.weather_cache`), replacing
  the old single-global-feather-cache assumption; `parallelization/
  parallel_run.py`'s pre-warm step now pre-fetches every distinct
  `(lat, lon, year, provider)` across a batch before forking workers.
- `BUEM_WEATHER_DATA_DIR` env var — points at the `weather` package's own
  pre-processed provider archive root.
- `.github/workflows/ci.yml` — conda-based CI (lint, type check, tests
  with coverage, CLI smoke test), matching the convention already used by
  `UU-BUEM/occupancy` and `UU-BUEM/weather`.

### Changed

- **Restructured environment/container files under `infrastructure/`**
  (`infrastructure/env/buem_env.yml`, `infrastructure/container/
  {Dockerfile,docker-compose.yml,entrypoint.sh}`), replacing the old flat
  root-level `environment.yml`/`environment_docker.yml`/`Dockerfile`/
  `docker-compose.yml`, matching `UU-BUEM/occupancy` and `UU-BUEM/weather`'s
  layout. `environment.yml`/`environment_docker.yml` are merged into one
  file (sibling convention). `setup.ps1`/`setup.bat` updated accordingly,
  and both gained an `env-update` command that creates-or-updates the
  conda env from `infrastructure/env/buem_env.yml` — the mechanism that
  keeps `occupancy`/`weather` current (see below).
- `occupancy`/`weather` are now installed via a direct git reference
  (PEP 508 direct URL — neither is published to PyPI/conda yet) in both
  `infrastructure/env/buem_env.yml` and `pyproject.toml`'s optional
  dependencies, tracked at `@main` rather than a pinned tag, so `setup.ps1
  env-update` / `conda env update ... --prune` always pulls in their
  latest pushed changes. Pin to a specific released tag instead if you
  need a reproducible, non-moving environment.

## [1.1] - 2026-06-25

### Changed

- **Major refactoring**: `occupancy`, `weather`, and `technology` removed
  as internal submodules (`src/buem/occupancy/`, `src/buem/weather/`,
  `src/buem/technology/`, ~8,800 deleted lines) and split into independent
  repos within the UU-BUEM organisation (`UU-BUEM/occupancy`,
  `UU-BUEM/weather`). `cfg_attribute.py`/`attribute_builder.py` switched to
  optional `try/except` imports; weather CSV loading was kept inline
  (pvlib DISC reconstruction) so buem has no hard dependency on the
  external `weather` package for basic operation. `pyproject.toml` gained
  `occupancy`/`weather` optional-dependency extras and dropped
  weather-pipeline-only deps (`cfgrib`, `dask`, `eccodes`, `netcdf4`,
  `pyproj`, `sympy`, `xarray`). The `buem weather` CLI subcommand was
  removed (the pipeline it drove now lives in `UU-BUEM/weather`).
- Building module: added `F_red_htr` (intermittent heating reduction,
  ISO 13790 §13.2.2) and `b_transmission` to `model_buem.py`/
  `cfg_attribute.py`.

## [1.0.2] - 2026-04-14

### Added

- **Weather — Documentation**: Dedicated `docs/source/modules/weather/`
  subsection with pages for pipeline steps, grid and projections (rotated
  pole vs WGS84), container deployment, CLI reference, and CSV weather data.
- `CHANGELOG.md` at project root following Keep a Changelog format.

### Changed

- Weather version history in `docs/source/modules/weather/index.rst` now
  links to `CHANGELOG.md` instead of duplicating entries.

## [1.0.1] - 2026-04-14

### Added

- **Weather — Container deployment**: Deps-only container strategy for
  Apptainer (HPC) and Docker (VMs).  Source code is bind-mounted at runtime;
  image rebuild only needed when `weather_env.yml` changes.
- **Weather — Monthly output naming**: Output files are named by month
  (`COSMO_REA6_2018_Jan.nc`) or month range (`COSMO_REA6_2018_Jan-Mar.nc`).
  Full-year runs produce `COSMO_REA6_2018.nc`.
- **Weather — Cleanup flag**: `--cleanup` option removes downloaded and
  decompressed intermediate files after a successful export.
- **Weather — Documentation**: Dedicated `docs/source/modules/weather/`
  section covering the pipeline, grid projections, containerisation, and
  CLI reference.

### Changed

- `weather.def` and `Dockerfile.weather` no longer bake source code into
  the image (deps-only).
- `run_pipeline_container.sh` bind-mounts `~/buem/src` into the container
  at `/app/src`.
- `build_container.sh` header updated for deps-only workflow.

## [1.0.0] - 2026-04-10

### Added

- **Weather module** (`buem.weather`): End-to-end COSMO-REA6 processing
  pipeline — download, decompress, transform, and export to NetCDF-4.
- Five raw attributes: SWDIFDS_RAD, SWDIRS_RAD, T_2M, U_10M, V_10M.
- Four derived fields: GHI, DHI, T (°C), WS_10M.
- Dask threaded scheduler with `time=168` chunking for memory-safe
  processing on HPC (16 cores, 28 GiB).
- CLI via `buem weather run/info/validate` and `python -m buem.weather`.
- Shell scripts for non-container SLURM jobs (`common.sh`, `run_pipeline.sh`).
- `weather_env.yml` conda environment specification.
- `CsvWeatherData.reconstruct_dni_from_ghi()` — pvlib DISC-based DNI
  reconstruction replacing the divergent `(GHI-DHI)/cos(θ)` formula.

[Unreleased]: https://github.com/UU-BUEM/buem/compare/v3.1.0...HEAD
[3.1.0]: https://github.com/UU-BUEM/buem/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/UU-BUEM/buem/compare/v2.0.1...v3.0.0
[2.0.1]: https://github.com/UU-BUEM/buem/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/UU-BUEM/buem/compare/v1.2.1...v2.0.0
[1.2.1]: https://github.com/UU-BUEM/buem/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/UU-BUEM/buem/compare/v1.1...v1.2.0
[1.1]: https://github.com/UU-BUEM/buem/compare/v1.0.2...v1.1
[1.0.2]: https://github.com/UU-BUEM/buem/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/UU-BUEM/buem/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/UU-BUEM/buem/releases/tag/v1.0.0
