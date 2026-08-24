# BUEM--EnerPlanET API Schema Versioning Policy

This document defines how schema versions are managed for the
BUEM--EnerPlanET integration.

The JSON schemas in this repository represent the authoritative contract
between EnerPlanET (client) and the BUEM microservice (server).

------------------------------------------------------------------------

## Versioning Approach

Schemas use **semantic versioning** (MAJOR.MINOR.PATCH) via Git releases.

- `versions/v1/`, `versions/v2/`, `versions/v3/`, `versions/v4/`, ... —
  every version, current or archived, lives under `versions/vN/` (this
  section previously described a flat `schemas/` directory holding "the
  current released version" separately from `versions/vN/` archives --
  corrected 2026-08-14, that directory has never existed in this repo).
  What makes a given `versions/vN/` the *live* one is
  `geojson_validator.py`'s own hand-wired runtime logic actually
  enforcing/converting that shape (see `CLAUDE.md` "Guardrails"), not the
  file's location -- check there, or this file's "Released Versions"
  section below, for which version is current.
- Git releases (`v1.0.0`, `v2.0.0`, etc.) are the authoritative version tags
- Any historical version is accessible via `git checkout <tag> -- src/buem/integration/json_schema/versions/`

------------------------------------------------------------------------

## Semantic Versioning Rules

### MAJOR — breaking change, client must update

- Required fields added or removed
- Field renamed or relocated
- Field type changes (including bare number to measurement object)
- Validation constraints become stricter
- Semantic meaning of a field changes

### MINOR — backwards compatible addition

- New optional field added
- New allowed unit added to an existing quantity type
- New optional node added (e.g. new section under `buem`)

### PATCH — no validation change

- Description or documentation text corrected
- Example values updated
- Whitespace or formatting only

------------------------------------------------------------------------

## Release Process

1. Make changes to the current live version's directory under `versions/`
   (e.g. `versions/v4/`)
2. Validate both schemas against their example files
3. Update `CHANGELOG.md`
4. Commit and create a Git release with the new version tag (a distinct,
   user-triggered step -- see `.claude/release-workflow.md`)

```bash
# Validate before releasing (run from src/buem/integration/json_schema/)
python -c "
import json
from jsonschema import Draft202012Validator
for name in ['request', 'response']:
    schema  = json.load(open(f'versions/v4/{name}_schema.json'))
    example = json.load(open(f'versions/v4/example_{name}.json'))
    errs = list(Draft202012Validator(schema).iter_errors(example))
    print(f'{name}: OK' if not errs else [e.message for e in errs])
"

# Create release
gh release create v4.0.0 --title "v4.0.0" --notes "..." \
  versions/v4/request_schema.json \
  versions/v4/response_schema.json \
  versions/v4/example_request.json \
  versions/v4/example_response.json
```

------------------------------------------------------------------------

## What Counts as a Breaking Change -- v2 to v3 Examples

- `building_attributes` replaced by four nodes: `building`, `envelope`,
  `thermal`, `solver`
- `latitude`/`longitude` removed from `buem` -- now read from
  `feature.geometry.coordinates` only
- All measurable quantities changed from bare numbers to
  `{ "value": number, "unit": string }` objects
- `components` nested object replaced by flat `envelope.elements[]`
- `child_components` legacy format removed
- Energy summary fields renamed (`total_kwh` to `total`, `max_kw` to `max`, etc.)

------------------------------------------------------------------------

## Released Versions

### v4.0.0 (2026-08-14) -- Current

Promoted from the `versions/v4/` draft with the user's explicit go-ahead
(the EnerPlanET developer told the user, 2026-08-13, that they are
already working on their own v5 -- see `versions/v4/DRAFT.md`'s
promotion note for the full reasoning and its limits). `geojson_validator.py`
now validates/converts against this shape; `versions/v3/` is retired to
an archived, deprecated snapshot below.

Migration from v3: MAJOR/breaking in one respect --
`building.building_type` gained an enforced enum (previously free-text);
a `building_type` outside the 4 TABULA residential codes or occupancy's
8 registered service-building types is now rejected at validation time.
Everything else is additive/MINOR: `building.capacity`/`num_persons`/
`archetype`/`equipment`/`name`, `buem.weather.provider`/`year`/`profile`,
`buem.inputs.electricity_load_profile`, `envelope_element.name`.
`weather.use_percentile`/`percentile` and `solver.compute_cooling` are
schema-present but explicitly rejected if sent (not yet wired to real
behavior -- see DRAFT.md's "Deliberately unwired at promotion").

Not yet tagged as a git release -- see `.claude/release-workflow.md`;
that remains a distinct, user-triggered step separate from this contract
promotion landing in code.

Archived snapshot: `versions/v4/` (its own `DRAFT.md` keeps the full
proposal/reconciliation history).

### v3.0.0 (2026-03) -- Deprecated

Migration from v2: Breaking changes. See CHANGELOG.md for full details.

Key changes:
- Separation of concerns: `building`, `envelope`, `thermal`, `solver` nodes
- Location sourced exclusively from GeoJSON geometry
- Unit-aware `{ value, unit }` measurement types throughout
- Flat `envelope.elements[]` with user-defined ids, unlimited per type
- Thermal properties decoupled from geometry via `thermal.element_properties[]`
- TABULA-aligned thermal parameters exposed as optional fields
- `metadata` formalised as required top-level response field

Archived snapshot: `versions/v3/` (corrected 2026-08-14 -- this repo has
no flat `schemas/` directory; every version, including whichever is
currently live, lives under `versions/vN/`. `geojson_validator.py`'s
hand-wired runtime logic, not a file's location, is what makes a version
"live" -- see `CLAUDE.md` "Guardrails").

### v2.0.0 (2026-02) -- Deprecated

Migration from v1: Breaking changes.

Key changes:
- Introduced structured `$defs`
- Optional elevation in geometry (3D coordinates)
- Replaced loose `building_attributes` with structured nested schema
- Added nested component model (Walls/Roof/Floor/Windows/Doors/Ventilation)
- Introduced `use_milp` control flag
- Stricter validation rules

Archived snapshot: `versions/v2/`

### v1.0.0 (2025-11) -- Deprecated

Initial schema version. Minimal structure, loose typing, flat child
component model, strictly 2D geometry.

Archived snapshot: `versions/v1/`

------------------------------------------------------------------------

## Governance

EnerPlanET maintains this contract repository.

Any proposed schema change must:

1. Be documented in CHANGELOG.md
2. Be reviewed before merging
3. Be validated using JSON Schema validation tools
4. Follow semver -- increment MAJOR for breaking, MINOR for additions,
   PATCH for documentation only

------------------------------------------------------------------------

This policy ensures stable integration and controlled evolution of the
BUEM--EnerPlanET API contract.
