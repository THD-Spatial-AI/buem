# Open issues / TODOs — services (non-residential) buildings

Cross-cutting items (core 5R1C model, standards choice, occupancy/weather
integration in general): `../open.md`. Household/dwelling-type items:
`../residential/open.md`.

## >>> NEXT MAJOR TASKS <<<

- [config] **No non-residential thermal defaults (thermal_class/ventilation/
  setpoint) per building-type (2026-07-31)** — the taxonomy/wiring gap
  (buem forcing every building through `HouseholdProfile` regardless of
  type, and `building_type` being unvalidated) is fixed — see
  `resolved.md`. What's still missing: occupancy's 8 service-building
  types (supermarket, office, restaurant, school, hotel, bakery,
  warehouse, clinic —
  `occupancy/src/occupancy/services_buildings/building_types.py`) have no
  buem-side equivalent of TABULA's per-type thermal defaults
  (`thermal_class`, `n_air_infiltration`/`n_air_use`, comfort setpoints)
  — every non-residential building still needs these chosen manually per
  building, unlike the TABULA-driven residential path. The 8 dummy
  fixtures under `src/buem/data/buildings/dummy/` now carry real
  occupancy type ids (see `resolved.md`) but still hand-author every
  thermal value themselves rather than inheriting a type default.
- [gains] **Internal gains are per-occupant, not floor-area-normalized,
  for services buildings on either side of the occupancy/buem contract
  (2026-07-31)** — see `../open.md`'s cross-repo note for the shared
  half of this; the services-specific angle is that floor area varies
  far more relative to occupant count for non-residential than for
  households (a warehouse: few people, huge area; a supermarket: many
  customers, moderate area), so a purely per-occupant gain figure
  generalizes worse here than for dwellings. ISO 52016-1 Annex B,
  ASHRAE 90.1, and City Energy Analyst (CEA) all use W/m² tables by
  use-type instead — worth using as the reference convention if/when
  this gets designed, but needs coordinating with occupancy (their
  `heat_gain_present_kw`/`heat_gain_active_kw` per building type is
  already flagged "illustrative" in their own `services/open.md`).
- [config] **No multi-use-building support (2026-07-31)** — dummy fixture
  `_05_mixed_use` is the only hint that buem might need to represent a
  building with more than one use; neither buem's schema nor occupancy's
  `OccupancyResult.building_type` support more than a single type per
  building. CEA supports area-weighted 1st/2nd/3rd use (`1ST_USE_R`/
  `2ND_USE_R`/`3RD_USE_R` ratios) for exactly this case. Until designed,
  mixed-use buildings need to be approximated as their dominant use type
  — worth stating explicitly in user-facing docs as a known
  simplification rather than leaving it implicit.
