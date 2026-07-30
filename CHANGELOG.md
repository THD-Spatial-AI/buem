# Changelog

All notable changes to BuEM are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
