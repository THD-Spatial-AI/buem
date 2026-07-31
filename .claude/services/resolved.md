# Resolved issues / decisions — services (non-residential) buildings

Fixed bugs and settled/BY-DESIGN decisions land here once closed out.
See `open.md` for active items.

## RESOLVED

- [integration] **Services buildings were completely unwired — fixed
  (2026-07-31)** — `AttributeBuilder.generate_electricity_profile`
  (`src/buem/integration/scripts/attribute_builder.py`) previously forced
  every building through `occupancy.HouseholdProfile` regardless of
  `building_type`. It now branches: TABULA residential codes
  (`RESIDENTIAL_BUILDING_TYPES` in `src/buem/config/cfg_attribute.py`) use
  the existing household path; any of occupancy's 8 service-building ids
  (supermarket/office/restaurant/school/hotel/bakery/warehouse/clinic)
  construct `occupancy.ServiceBuildingProfile(building_type=..., year=...,
  capacity=..., seed=...)` instead — both converge on the same
  `to_buem_profiles()` call (confirmed already use-type-agnostic, see
  `../open.md`). New `capacity` `AttributeSpec` added alongside
  `building_type` (defaults to occupancy's own `capacity_default` when
  unset). Added `building_type`/`capacity` as real `ATTRIBUTE_SPECS`
  entries (previously `building_type` wasn't a spec at all).
- [validation] **`building_type` enum validation attempted, then reverted
  — this is EnerPlanET API contract territory, not a routine code change
  (2026-07-31)** — `versions/v2/request_schema.json`,
  `versions/v3/request_schema.json`, and `geojson_validator.py`'s
  `BuildingAttributesSchema.building_type` were briefly given an enum
  (TABULA codes + occupancy's 8 service ids) in the same pass as the
  routing fix above, without checking in first. Per
  `src/buem/integration/json_schema/VERSIONING.md`'s own semver rules,
  "validation constraints become stricter" is a MAJOR breaking change to
  an *agreed, EnerPlanET-owned* contract (authoritative copy at
  [enerplanet/buem-gateway](https://github.com/enerplanet/buem-gateway/tree/main/schemas)),
  not something to edit in place. **Reverted** — v2/v3 and
  `geojson_validator.py` are back to their agreed state (free-text
  `building_type`, no `capacity` field). The proposed change instead
  lives as a draft in `src/buem/integration/json_schema/versions/v4/`
  (see that folder's `DRAFT.md`) — accumulate there until the diff is
  substantial enough to raise as a real new contract version with
  EnerPlanET. See `CLAUDE.md` "Guardrails" for the durable rule this
  incident produced. Note: `building_type` itself was *already* a
  free-text field the v3 contract's `_convert_v3_to_v2` already copied
  through (that part predates this session) — so the routing fix above
  (household vs. `ServiceBuildingProfile`) is fully live against the real
  v3 contract as-is; only the *enum* (stricter validation) and the new
  `capacity` field are gated behind v4 agreement.
- [data] **Non-residential dummy fixtures updated to real occupancy type
  ids (2026-07-31)** — `_02_medium_office`→`office`, `_08_school`→
  `school`, `_14_restaurant`→`restaurant`, `_10_warehouse`→`warehouse`,
  `_09_retail_shop`/`_03_large_commercial`→`supermarket` (approximated).
  `_04_industrial`, `_13_daycare_center`, `_15_sports_hall` intentionally
  left with their old placeholder codes (`IND`/`EDU`/`SPO`) — no
  occupancy service type is a good match. Since the schema-level enum
  above was reverted, these three currently still validate (free-text
  `building_type`) but would fail at generation time in
  `AttributeBuilder.generate_electricity_profile` (unrecognized service
  type, clear `ValueError`) if actually run — known-unsupported until
  occupancy adds matching types (occupancy's own
  `.claude/services/open.md` already lists gym/hospital/factory as
  roadmap candidates — sports hall/industrial/daycare fall in the same
  bucket).
- [envelope] **`F_red_htr` was the only way to express setback, and it's
  residential-shaped — addressed via time-varying comfort bounds instead
  (2026-07-31)** — `ModelBUEM._init5R1C`
  (`src/buem/thermal/model_buem.py`) now accepts `comfortT_lb`/
  `comfortT_ub` as either a scalar (unchanged default behaviour) or a
  `pd.Series` aligned to the weather index, normalized internally to a
  length-n array so every downstream consumer (LP/MILP constraints,
  big-M bounds, `T_set`) needs no further branching. This lets a
  service building with irregular occupancy (e.g. a school: closed
  evenings/weekends/summer) express real per-hour setpoint setback
  directly, instead of approximating it with `F_red_htr`'s single annual
  scalar (which was designed for — and remains unchanged for —
  residential night/weekend setback). Verified with a new test
  (`tests/test_building_types.py::
  test_time_varying_comfort_bounds_change_heating_shape`) showing a
  night-setback `comfortT_lb` series shifts heating load away from the
  setback hours, unlike a flat scalar.
- [tests] **Added real pytest coverage for the services path
  (2026-07-31)** — `tests/test_building_types.py` runs both a residential
  and a service-building dummy fixture through the full
  `AttributeBuilder`→`ModelBUEM` pipeline (calling `ModelBUEM.sim_model()`
  directly rather than `buem.main.run_model()`, to avoid that module's
  pre-existing unrelated `buem.results.standard_plots` import gap — see
  root `CLAUDE.md` "Open follow-ups"). Existing `test_scaling.py` (which
  globs the dummy directory but isn't pytest-collected — all its logic
  sits under `if __name__ == "__main__":`) was left as-is per the plan.
