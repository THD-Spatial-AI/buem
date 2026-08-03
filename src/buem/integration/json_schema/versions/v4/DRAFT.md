# v4 — DRAFT, not yet an agreed API version

This folder is a **staging area**, not a released contract version. The
authoritative, agreed schemas live at
[enerplanet/buem-gateway](https://github.com/enerplanet/buem-gateway/tree/main/schemas)
and are mirrored here for buem's own development — v3 there is current.

## What's in this draft

Three changes so far. The first two are additive/services-building
related, accumulated while wiring up `ServiceBuildingProfile` support in
buem. The third (2026-08-03) is part of making the `weather` package a
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
