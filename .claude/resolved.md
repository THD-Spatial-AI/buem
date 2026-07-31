# Resolved issues / decisions — cross-cutting

Fixed bugs and settled/BY-DESIGN decisions land here once closed out.
See `open.md` for active items.

## RESOLVED

- [bug] **Two hardcoded validation bounds in `ModelBUEM` silently rejected
  valid non-residential input — fixed (2026-07-31)** —
  `src/buem/thermal/model_buem.py`: `_initEnvelop` capped `h_room` at
  5.0 m (raised to 20.0 m — blocked tall spaces like warehouses/sports
  halls/industrial halls); `_init5R1C` restricted `comfortT_lb`/
  `comfortT_ub` to [15, 30] °C (widened to [5, 35] °C — blocked
  frost-protection-only setpoints for lightly-conditioned industrial/
  warehouse space). Neither bound was residential-specific by design;
  both were just never widened when non-residential use was considered.
- [confirmed] **`occ_nothome`/`occ_sleeping`/`sleeping_factor` in
  `ModelBUEM._addConstraints_sequential` do NOT need generalizing
  (2026-07-31)** — `occupancy.core.buem_adapter.to_buem_profiles()` was
  confirmed to already compute both generically from `n_present`/
  `n_asleep` vs. `num_persons` for any `OccupancyResult`, household or
  service building; most service types simply carry `n_asleep == 0`
  throughout (see `services/resolved.md` for what this unblocked instead:
  routing non-residential buildings through `ServiceBuildingProfile` at
  all, and time-varying comfort bounds as the real fix for irregular
  service-building schedules).
- [confirmed] **`AttributeBuilder.generate_electricity_profile` was
  already wired to per-request `num_persons`/`capacity`/`building_type`/
  `seed` via `self.merged_attrs` (2026-07-31)** — a suggestion to make
  `cfg_attribute.py`'s module-level default-profile block dynamic was
  checked and found unnecessary: that block only seeds `ATTRIBUTE_SPECS`
  defaults at import time, it's never called per-request. The real
  per-request call is `generate_electricity_profile` itself, which
  already reads real values from `self.merged_attrs` (built fresh per
  `AttributeBuilder(payload_attrs=...)` instance). The one real bug found
  in that area — `capacity` (unlike `num_persons`) had no `int()` cast, so
  a string capacity from a JSON payload would reach
  `ServiceBuildingProfile`'s `self.capacity <= 0` check and raise an
  unrelated-looking `TypeError` — is fixed. `capacity` is also still not
  reachable through the real v3 GeoJSON path (missing from both the
  marshmallow schema and `_convert_v3_to_v2`'s metadata-copy loop, unlike
  `building_type`) — an attempt to add it there was made and then
  **reverted** (see `services/resolved.md` and `CLAUDE.md` "Guardrails"):
  those files are the EnerPlanET API contract, not a routine code change.
  A draft lives at `json_schema/versions/v4/` pending agreement;
  `capacity` only works today via `payload_attrs` supplied directly
  (bypassing schema validation), e.g. in tests.
- [decision] **Tightened several silent "fall back to generic/zero" paths
  in `AttributeBuilder` to raise instead (2026-07-31)** — prompted by a
  general review of fallback behavior: falling back to *0* or to a
  generic substitute value when a specific building's real data is
  missing/misaligned can silently produce a plausible-looking but wrong
  result, which is worse than a clear error. Four changes, one still
  configurable:
  1. `latitude`/`longitude`/`components`/`A_ref` are now required to be
     explicitly supplied via `payload_attrs` or `db_fetcher` output —
     `AttributeBuilder.build()` raises `ValueError` if any are missing,
     rather than silently modeling `ATTRIBUTE_SPECS`' generic ~100 m²
     example house at the wrong coordinates. Everything else (thermal
     class, comfort setpoints, ventilation rates, `num_persons`/`seed`)
     keeps its config default — those are legitimate "unknown, assume
     standard" assumptions (same convention as TABULA/EPCs), not
     building-identity data.
  2. `db_fetcher` failures now raise (wrapped `RuntimeError`) instead of
     logging a warning and silently continuing with generic defaults —
     a `db_fetcher` wired for a specific `building_id` failing means that
     building's real data is missing, not "use a placeholder."
  3. `generate_weather_profile`'s except now splits `ImportError` (the
     `weather` package's own optional extras, e.g. xarray/netcdf4, being
     absent — same "extra not installed" case as `weather_available()`,
     kept as a lenient warn+fallback) from `FileNotFoundError`/
     `KeyError`/`OSError`/`ValueError` (a real fetch failure for the
     *specific requested* location/year — since `weather_available()`
     already gated "package missing," these mean the package works but
     this request's data doesn't exist). The latter now raises by
     default; `AttributeBuilder(..., allow_weather_fallback=True)` opts
     back into the old lenient bundled-CSV substitution, for offline/dev
     use.
  4. The three `series.reindex(weather_df.index, method='nearest',
     fill_value=0.0)` calls (profile/weather-index alignment) are
     replaced by a shared `_reindex_or_raise` helper that adds a
     30-minute `tolerance` and raises if any timestep can't align within
     it — plain `method="nearest"` never produces NaN (it always finds
     *some* label), so `fill_value=0.0` was silently matching e.g. a
     wrong-year profile onto the weather index instead of catching the
     mismatch. Covered by `tests/test_attribute_builder_strictness.py`.
- [docs] **Sphinx/ReadTheDocs `docs/` reintegrated and content brought
  current (2026-07-31)** — `docs/source/conf.py` and the `pyproject.toml`
  `docs` extra were removed during the `v1.1` submodule-extraction
  refactor and never recreated (readme.md's own former note); the user
  had preserved the removed content standalone. Reintegrated at `docs/`
  (matching what `.readthedocs.yaml`/`.gitignore` already expected),
  `docs` extra added to `pyproject.toml`
  (`sphinx>=9.0.0`,`sphinx-rtd-theme>=3.0.0`). Content updated for drift
  accumulated since removal: `modules/occupancy.rst` and the 6-file
  `modules/weather/` subtree (collapsed to one `modules/weather.rst`)
  described buem-internal implementations that moved to the external
  `occupancy`/`weather` packages; `api_integration/request_format.rst`/
  `response_format.rst` described the old flat v1/v2 payload shape, not
  v3's nested/unit-wrapped one; `modules/results.rst`/`technology.rst`
  documented modules that don't exist in the current codebase at all
  (flagged clearly rather than presented as working, cross-referencing
  this file's `buem.results` entry above). `make html` builds clean, zero
  warnings.
