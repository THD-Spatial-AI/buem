# v4 — DRAFT, not yet an agreed API version

This folder is a **staging area**, not a released contract version. The
authoritative, agreed schemas live at
[enerplanet/buem-gateway](https://github.com/enerplanet/buem-gateway/tree/main/schemas)
and are mirrored here for buem's own development — v3 there is current.

## What's in this draft

Both changes are additive/services-building related, accumulated while
wiring up `ServiceBuildingProfile` support in buem:

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
