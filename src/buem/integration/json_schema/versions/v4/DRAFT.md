# v4 — DRAFT, not yet an agreed API version

This folder is a **staging area**, not a released contract version. The
authoritative, agreed schemas live at
[enerplanet/buem-gateway](https://github.com/enerplanet/buem-gateway/tree/main/schemas).

**Correction (2026-08-06): this note previously said "v3 there is current" —
that's now known stale.** EnerPlanET's repo has its own real `schemas/v4/`
today (confirmed by fetching the actual raw JSON, not just browsing).
Whether that means v4 is *live* on their end, or is their own
not-yet-deployed draft mirroring this folder's own status, is not known
from here — only the user's direct conversation with the EnerPlanET
developer can settle that (same tier-3 promotion gate as below). Treat
"which version EnerPlanET actually runs in production" as an open question,
not settled by this file.

## What's in this draft

Four changes so far. The first two are additive/services-building
related, accumulated while wiring up `ServiceBuildingProfile` support in
buem. The third and fourth are part of making the `weather` package a
compulsory, real-fetch-only data source (buem has no bundled/local-file
weather fallback anymore -- see buem's own `CLAUDE.md`):

- `building.building_type` gets an `enum` (previously free-text): the 4
  TABULA residential codes (`SFH`/`MFH`/`TH`/`AB`) plus 8 occupancy
  service-building type ids (`supermarket`/`office`/`restaurant`/`school`/
  `hotel`/`bakery`/`warehouse`/`clinic`). Per `VERSIONING.md`'s own semver
  rules this is a **MAJOR** change ("validation constraints become
  stricter"), not a MINOR addition — a client sending a `building_type`
  value outside this set, which previously passed, would now be rejected.
- `building.capacity` (new optional integer field, service-building
  occupancy sizing) — this one alone would be MINOR (backward-compatible
  addition).
- New `buem.weather` object (sibling to `building`/`solver`): optional
  `provider` (`era5-land`/`cosmo-rea6`/`merra-2`, default `merra-2` as of
  2026-08-04 -- era5-land was the original default but currently fails at
  buem's own default test cell, see CLAUDE.md) and `year` (defaults to
  `start_time`'s calendar year) selecting the real per-location weather-
  module fetch. Additive/MINOR. The equivalent v2-format fields
  (`building_attributes.year`/`weather_provider`) are already live in
  `geojson_validator.py`'s `BuildingAttributesSchema` (not gated behind this
  draft — that schema isn't part of the versioned contract). **Not yet
  reachable from a real v3 (live) request**: `geojson_validator.py`'s
  `_convert_v3_to_v2()` doesn't read any `weather`-equivalent block from
  v3 input yet, so today only true v2-format requests (or direct
  `AttributeBuilder` calls) can set `year`/`weather_provider` -- see
  CLAUDE.md "Weather is compulsory" for what extending that would need.
- `buem.weather` gains `use_percentile` (boolean, default `false`) and
  `percentile` (enum `P10`/`P50`/`P90`, default `P50`) (2026-08-06).
  Alternative to `year`: instead of a specific calendar year, select a
  percentile climate year -- ranked across the provider's available
  archive years at this location -- computed via `weather`'s existing
  per-provider percentile infrastructure (`percentile_index.py`, already
  present for all three providers, unrelated to this schema change).
  `year` is ignored when `use_percentile` is true. Both optional with
  defaults, so additive/MINOR. **Schema-only, same starting point as
  `buem.weather` itself**: not read by `_convert_v3_to_v2()`, not wired
  through `AttributeBuilder`/the weather fetch itself, and not exposed by
  the point-query HTTP API scaffold (`UU-BUEM/weather`'s
  `src/weather/api/`, GET `/v1/weather/point` takes a specific `year`
  only, no percentile parameter yet) -- three separate, unstarted wiring
  steps, each its own later task.
- `building.num_persons`, `building.archetype` (new optional fields, both
  additive/MINOR) (2026-08-07), alongside the existing `building.capacity`
  -- part of making `occupancy` a compulsory dependency (buem's own
  `CLAUDE.md`, "Occupancy is compulsory"). `num_persons` mirrors
  `AttributeBuilder`'s existing runtime support; `archetype` is new,
  selecting one of occupancy's registered household archetypes as an
  explicit override of `cfg_attribute.DEFAULT_ARCHETYPE_BY_BUILDING_TYPE`'s
  first-pass `building_type`-based default. **Deliberately excludes
  `seed`**: an internal RNG-reproducibility knob, not a modeling input a
  client should set -- see `.claude/occupancy_gains_handoff.md`'s
  seed-ownership note for the reasoning and the proposal that `occupancy`
  itself own a deterministic default instead. **`num_persons`/`archetype`
  now reach a real v3 (live) request too** (2026-08-07):
  `_convert_v3_to_v2()` forwards `capacity`/`num_persons`/`archetype`
  (not `seed`) from `building` into `building_attributes` -- see
  `.claude/occupancy_gains_handoff.md` for the full writeup. This does
  *not* mean EnerPlanET's actual v3 contract documents or has agreed to
  these fields (it hasn't) -- only that buem's own runtime happens to
  read them if a v3-format client sends them, same caveat as `year`/
  `weather_provider` before it.

## Reconciliation against EnerPlanET's real v4 (2026-08-06)

Fetched the actual raw JSON from
[enerplanet/buem-gateway/schemas/v4](https://github.com/enerplanet/buem-gateway/tree/main/schemas/v4)
(all four files: both schemas, both examples) and diffed against this
folder. They'd diverged in both directions. **All of buem's own
pre-existing additions below were kept as-is, not removed** — reconciling
means adding what EnerPlanET has that we didn't, and fixing one real bug,
not discarding buem-side proposals:

**Added here, from EnerPlanET's real v4** (previously missing entirely):

- `building.name` / `envelope_element.name` — display-only labels.
- `building.envelope` is no longer `required` — when omitted, the model
  derives surfaces/U-values from the TABULA variant identified by
  `building_type` + `construction_period` + `country`.
- `construction_period`'s description corrected: it's a TABULA
  construction-year *class code* (e.g. `"04"`), not a literal year range
  — buem's own example data still uses the older `"1965-1974"`-style
  range pending a check of what buem's actual TABULA lookup code parses;
  not changed, since guessing at internal engine behavior here would risk
  a wrong-but-plausible example. Flagged, not fixed.
- `solver.compute_cooling` (bool, default `false`) — makes the cooling
  constraint/output conditional. Response side updated to match:
  `load_summary`/`load_timeseries` now only require `cooling` when this
  was true (previously unconditionally required in both request and
  response); `model_metadata` gained `simulations_run` and
  `electricity_source`.
- New `buem.inputs.electricity_load_profile` object (client-supplied
  electricity timeseries override, with `path`/`unit`) — request and
  response (echoed) both updated.
- Defaults added to `phi_int` (3.0 W/m2) and `q_w_nd` (12.5 kWh/(m2.a)),
  matching EnerPlanET's real values.

**A real bug fixed, not just a gap**: `q_w_nd`'s unit enum was
`"kWh/(m2a)"` (no dot) — EnerPlanET's real v4 uses `"kWh/(m2.a)"` (with a
dot). A genuine EnerPlanET request using their own documented unit string
would have failed validation against this draft. Now matches theirs
exactly.

**Kept, still buem-side-only proposals** (confirmed absent from
EnerPlanET's real v4 as of this check — each field's own description now
says so explicitly): `building_type`'s `enum` (theirs is still free-text
— per `VERSIONING.md` this remains the one MAJOR/breaking change in this
draft), `building.capacity`, and the entire `buem.weather` object
(`provider`/`year`/`use_percentile`/`percentile` — EnerPlanET's v4
resolves weather from `geometry.coordinates` alone, no client-specified
provider/year/percentile at all). None of these were proposed to
EnerPlanET before this draft existed, so their absence there is expected,
not a discovered gap — nothing to "fix" here, just now documented
precisely rather than asserted.

All four files (`request_schema.json`, `response_schema.json`,
`example_request.json`, `example_response.json`) still validate
internally (`jsonschema.validate()` against their own examples) after
this pass.

## Status

Not proposed to EnerPlanET yet, and **nothing here is cast in stone** —
freely edit/extend this draft as good ideas come up, no need to check in
per change (see `CLAUDE.md` "Guardrails", tier 2). It's inert by
construction: `geojson_validator.py` doesn't load `json_schema/` at all,
so nothing here takes live effect just by existing or changing.

Keep accumulating here until the diff is substantial enough to be worth a
real new contract version. Promoting it to live is a separate, later,
two-part step (tier 3): the buem maintainer personally negotiates a new
agreement with the EnerPlanET developer first, and only after that,
`geojson_validator.py` + the retired old version get updated together,
following `VERSIONING.md`'s release process (CHANGELOG entry, validation
against examples, semver-tagged release). Until both have happened, this
folder stays draft-only — do not wire it into `geojson_validator.py` or
any live request-handling path.
