# CLAUDE.md — buem

Persistent context for Claude Code. This file is new (2026-07-30) — buem
had no CLAUDE.md before; kept intentionally minimal rather than backfilling
the full structure occupancy/weather use. Extend as needed.

## What this repo is

`buem` is the building thermal-demand module (ISO 52019-1:2017, 5R1C) —
integration layer for [UU-BUEM/occupancy](https://github.com/UU-BUEM/occupancy)
(occupancy/internal-gains/electricity input) and
[UU-BUEM/weather](https://github.com/UU-BUEM/weather) (per-location weather
input), both optional extras (`pip install buem[occupancy,weather]`) with
synthetic/bundled fallbacks when not installed.

## Cross-repo (UU-BUEM)

buem ‖ occupancy ‖ weather share dependency pins, `infrastructure/env/`
layout, CI (`.github/workflows/ci.yml`), and `pip install -e . --no-deps`
packaging. A change to shared conventions in one usually needs the
parallel change in the sibling repos — see occupancy's/weather's own
CLAUDE.md and `.github/agents/uu-buem-align.agent.md` (lives in the
weather repo).

## Open follow-ups

- [harmonization] **Idea, not started (2026-07-30)**: a small shared
  "harmonization" package (env.yml/pyproject.toml/CI-workflow scaffolding)
  that buem/occupancy/weather would each conda-install from, instead of
  today's approach — every shared pin or fix gets hand-copied across all
  three repos' own env files and the alignment agent's table by hand each
  time, which is exactly how buem's/occupancy's/weather's numpy/pandas
  caps drifted out of sync in the first place (fixed 2026-07-30, see
  CHANGELOG's `[Unreleased]`). Would live in its own repo under UU-BUEM.
  Not designed or scoped yet — user is considering it; ask before acting
  if this comes up again.
- `infrastructure/env/buem_env.yml` intentionally omits `gunicorn` (Unix-only,
  no win-64 conda-forge build); it's installed instead in
  `infrastructure/container/Dockerfile`'s builder stage, Linux-only.
- `tests/test_energy.py`, `tests/test_geojson_integration.py`,
  `tests/test_scaling.py`, `tests/test_worker_debug.py` currently fail to
  collect: `ModuleNotFoundError: No module named 'buem.results'`
  (`src/buem/main.py` imports `buem.results.standard_plots`, which doesn't
  exist — likely fallout from the pending "major refactoring" commit).
  Pre-existing, not investigated as part of the numpy/pandas pin work.

## Environment

conda env `buem_env`; prefer conda. See `infrastructure/env/buem_env.yml`.
