# Open issues / TODOs — household / dwelling types

Cross-cutting items (core 5R1C model, standards choice, occupancy/weather
integration in general): `../open.md`. Non-residential building items:
`../services/open.md`.

## >>> NEXT MAJOR TASKS <<<

- [envelope] **Adiabatic party-wall assumption doesn't cover an unheated/
  vacant/differently-set-back neighbour (2026-07-31)** — `SharedWallDetector`
  (`src/buem/buildings/mapping/wall_classifier.py`) and `lod2_mapper.py`
  set geometrically-detected shared walls to `U=0`, `b_transmission=0`
  (no heat transfer modeled through party walls), the standard ISO
  13790/52016 simplification (assumes similar indoor temperature both
  sides ⇒ no net flux) and the same convention TEASER uses for attached
  buildings. It breaks down for e.g. an end-of-terrace unit next to an
  unheated garage/stairwell, or a vacant neighbouring apartment — no
  alternative boundary-condition mode (fixed reduced neighbour
  temperature, or a configurable non-zero `b_transmission`) exists today.
  Not urgent — default assumption is standard practice and matches prior
  art — but worth an explicit opt-in mode if a use case needs it.
- [envelope] **No mutual-shading/overshadowing model between adjacent
  buildings (2026-07-31)** — `ThermalProperties.F_sh_hor`/`F_sh_vert`
  (`src/buem/buildings/building.py`, fixed per-building scalars, defaults
  0.80/0.75) are the only shading treatment; there's no geometry-derived
  horizon/obstruction calculation, even though the LOD2 adjacency data
  needed for it is already loaded for party-wall detection (same
  `SharedWallDetector` pipeline). Matters most for terraced rows and
  dense apartment blocks, where neighbouring buildings routinely shade
  each other's facades. Confirmed this can't be pushed upstream to
  `weather` — that repo only supplies horizontal-plane GHI/DHI/DNI per
  location, no surface geometry or shading concept at all (see
  `../open.md` "external" section). Would be a buem-side addition to
  `_calcRadiation` (`src/buem/thermal/model_buem.py`) using the existing
  LOD2 geometry; not scoped, potentially a sizeable change.
- [integration] **No `building_type`-aware default for household size at
  scenario assembly (2026-07-31)** — `AttributeBuilder.
  generate_electricity_profile` (`src/buem/integration/scripts/
  attribute_builder.py`) passes `num_persons` straight through to
  `occupancy.HouseholdProfile`; nothing maps `BuildingIdentity.
  building_type` (`SFH`/`MFH`/`TH`/`AB`) to a suggested occupancy
  archetype or household-size default. occupancy's own archetypes
  (`generic`/`working_couple`/`family_with_children`/`retired_single`/
  `student_shared`, `occupancy/households/archetypes.py`) already vary by
  composition — the missing link is buem-side (choosing/suggesting an
  archetype consistent with dwelling type when the caller doesn't
  specify one), not an occupancy-side gap.
- [config] **No formal "archetype defaults" input path (2026-07-31)** —
  today buem derives thermal parameters from full LOD2 envelope geometry
  (`lod2_mapper.py`). TEASER and CEA instead generate geometry+defaults
  directly from a typology+age-class+country lookup (TABULA WebTool-
  style), useful when full building-footprint data isn't available (e.g.
  quick studies, non-Germany contexts). buem's 17 dummy fixtures
  (`src/buem/data/buildings/dummy/`, including named terraced/apartment/
  detached-villa archetypes) hint at this need but aren't a formal
  system — each is a hand-authored example config, not a
  parametrized lookup. Possible future input mode; not scoped.
