# Changelog

All notable changes to BuEM are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/UU-BUEM/buem/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/UU-BUEM/buem/compare/v1.1...v1.2.0
[1.1]: https://github.com/UU-BUEM/buem/compare/v1.0.2...v1.1
[1.0.2]: https://github.com/UU-BUEM/buem/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/UU-BUEM/buem/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/UU-BUEM/buem/releases/tag/v1.0.0
