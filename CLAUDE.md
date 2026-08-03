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

## Guardrails — read before making changes

- **`src/buem/integration/json_schema/` (all of it — `versions/v1,v2,v3/`,
  `SCHEMA_OVERVIEW.md`, `VERSIONING.md`, `README.md`) is the authoritative
  API contract with EnerPlanET** (see `VERSIONING.md`: "represents the
  authoritative contract between EnerPlanET (client) and the BUEM
  microservice (server)"). Versions are **mutually agreed with EnerPlanET**.
  `src/buem/integration/scripts/geojson_validator.py`'s runtime validation
  (`BuildingAttributesSchema` and friends) is part of the same contract —
  it *enforces* it at runtime (tightening it, e.g. adding an
  `enum`/`validate=`, has the same live effect as editing a schema file),
  but it does **not** load `json_schema/` at all, so it only ever enforces
  whichever version was last hand-wired into it (currently v3).
  - **Three-tier model — settled 2026-07-31, apply to any future vN too**:
    1. **The live/agreed version** (currently v3) **and
       `geojson_validator.py`'s enforcement — never edit either without
       checking in with the user first**, even a change that looks purely
       additive. Per `VERSIONING.md`'s own semver rules, "validation
       constraints become stricter" is a MAJOR breaking change, not a safe
       tweak.
    2. **A not-yet-agreed draft version (e.g. `versions/v4/`) — freely
       editable, no check-in needed per edit.** It's inert by construction
       (nothing loads or enforces it), so accumulating/improving it is
       safe by default. Keep iterating on it as good ideas come up; don't
       ask before each draft tweak.
    3. **Promoting a draft to live is a distinct, later action, gated on
       two things**: (a) the user has personally negotiated a new
       agreement with the EnerPlanET developer — that conversation is
       theirs to have, not something to propose or initiate; (b) explicit
       user go-ahead to then edit `geojson_validator.py` + retire the old
       version, following `VERSIONING.md`'s release process (CHANGELOG
       entry, validate against examples, semver bump). Until both, treat
       the draft as **not cast in stone** — nothing to defend or rush.
  - **Incident (2026-07-31)**: `versions/v2/request_schema.json` and
    `versions/v3/request_schema.json` (tier 1) were edited directly (added
    a `building_type` enum + `capacity` field) while adding
    services-building support, without checking in first. Reverted; the
    same change now lives safely as a tier-2 draft in `versions/v4/` (see
    its `DRAFT.md`).
- **Pushing to GitHub is a distinct, user-triggered workflow.** Don't push,
  tag, or create a GitHub release except when the user explicitly asks for
  it (e.g. "push to github" / "release this").

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

## See also

- `docs/` — Sphinx/ReadTheDocs source (reintegrated 2026-07-31; was
  removed during the `v1.1` submodule-extraction refactor along with the
  `pyproject.toml` `docs` extra, per this file's own former note — both
  restored). Build with `pip install -e .[docs]` then `cd docs && make
  html`; see `docs/README.md`.
