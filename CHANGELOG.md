# Changelog

All notable changes to BuEM are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/SomadSahoo/buem/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/SomadSahoo/buem/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/SomadSahoo/buem/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/SomadSahoo/buem/releases/tag/v1.0.0
