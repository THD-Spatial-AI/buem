# Open issues / TODOs — cross-cutting

Household/dwelling-type-specific items: `residential/open.md`.
Non-residential-building-specific items: `services/open.md`.

## >>> NEXT MAJOR TASKS <<<

- [bug] **`geojson_validator.py`'s v3→v2 `A_ref` fallback is a flat
  `100.0` literal, not actually "derived from floor element areas" as the
  v3 schema's own description claims (found 2026-07-31, not fixed —
  discovered while checking whether `AttributeBuilder.
  REQUIRED_FROM_CALLER`'s new strictness could break real traffic; it
  doesn't, since this fallback means `A_ref` is always present as a key
  by the time `AttributeBuilder` sees it)** — `_convert_v3_to_v2`
  (line ~539): `A_ref = extract_value(building.get('A_ref', 100.0))`.
  `versions/v3/request_schema.json`'s `A_ref` description says
  "Reference floor area. Derived from floor element areas if omitted" —
  `CfgBuilding.to_cfg_dict()` actually implements that real derivation
  (sums floor-element areas) but runs *after* `AttributeBuilder`, so a
  real client that omits `A_ref` and relies on the documented
  derive-from-geometry behavior silently gets 100 m² instead of its
  actual floor area. Pre-existing (predates this session's changes, not
  introduced by them) — same "silent generic fallback" class of issue as
  the ones tightened in `AttributeBuilder` this session, just one layer
  upstream in the v3 converter. Not fixed here — flagged for a future
  pass; fixing would mean either moving the real derivation earlier (into
  the converter) or having `AttributeBuilder` omit a fabricated `A_ref`
  key so its own `REQUIRED_FROM_CALLER` check can't be silently satisfied
  by a wrong value.
- [standards] **Why buem stays on lumped 5R1C, not ISO 52016-1 (2026-07-31,
  design note, not a decision to revisit lightly)**: ISO 52016-1:2017
  supersedes ISO 13790:2008's simplified hourly method with a
  disaggregated per-building-element node network (no lumping to 5
  nodes) — more accurate, especially for non-standard geometry,
  multi-zone, and non-residential buildings, at higher input/compute
  cost. `ModelBUEM` (`src/buem/thermal/model_buem.py`) deliberately keeps
  the lighter lumped 5R1C (ISO 13790 conventions + ISO 52019-1's internal
  heat-transfer-coefficient/gain-distribution factors) — this matches
  TABULA/EPISCOPE's and TEASER's (RWTH Aachen) own convention and is the
  right tradeoff for portfolio/urban-scale studies over single-building
  detailed assessment. Not recommending a switch; recorded so this
  doesn't get re-litigated from scratch each time non-residential/
  multi-zone accuracy comes up (see `services/open.md` for where the
  lumped model's limits actually bite).
- [prior-art] **Comparable open-source models reviewed (2026-07-31)** —
  for future reference when designing archetype defaults or non-
  residential typing: TABULA/EPISCOPE (origin of buem's `SFH`/`MFH`/
  `TH`/`AB` classes and `F_red_htr` values, via
  `BuildingIdentity.building_type` /
  `ThermalProperties.F_red_htr`, `src/buem/buildings/building.py`);
  TEASER (RWTH Aachen — generates geometry+params directly from a
  TABULA typology+age-class+country lookup rather than requiring full
  LOD2 geometry like buem does today, and uses the same adiabatic
  treatment of attached buildings as buem's `SharedWallDetector`); City
  Energy Analyst / CEA (ETH Zurich — per-m² internal loads/schedules by
  use-type across ~15 residential+non-residential typologies, and
  area-weighted multi-use buildings — see `services/open.md`); EUReCA
  (open-source urban building energy model, another RC-network
  implementation at city scale); `archetypal` (Python package for
  archetype collection/conversion, relevant if buem ever adds an
  archetype-defaults input path alongside its LOD2 pipeline).
- [cross-repo] See root `CLAUDE.md`'s "Open follow-ups" for the
  harmonization-package idea (shared env/CI scaffolding across buem/
  occupancy/weather) — not duplicated here, ask before acting on it.
- [cross-repo] **occupancy/buem internal-gains contract is per-occupant
  (kW), not floor-area-normalized (W/m²), on either side (2026-07-31)** —
  `occupancy.core.buem_adapter.to_buem_profiles()` produces `Q_ig` from
  `heat_gain_present_kw`/`heat_gain_active_kw` × occupant count only;
  buem's `A_ref` (`src/buem/buildings/building.py`, `Building.A_ref`/
  `computed_A_ref()`) isn't consulted. Fine for households (gains are
  legitimately absolute W, and household size is the natural driver) but
  weaker for services buildings, where floor area varies far more
  relative to occupant count than in dwellings — see `services/open.md`.
  occupancy's own `services/open.md` already flags its per-building-type
  gain values as "illustrative, not survey-calibrated"; this note is the
  buem-side half of the same gap. Raise with occupancy maintainers before
  designing a fix — this is a joint-contract change, not a buem-only one.

## external (context only)

- [weather] **Solar input is horizontal-plane only; no shading/
  overshadowing concept exists upstream (2026-07-31)** — `weather`'s
  `get_point_weather()` returns per-location `T`/`GHI`/`DHI`/`DNI` only
  (no tilt/azimuth/POA transposition, no terrain or building-to-building
  obstruction anywhere in that repo). buem's own `_calcRadiation`
  (`src/buem/thermal/model_buem.py`) already does the isotropic
  POA transposition per envelope element; any future mutual-shading
  model between adjacent buildings (relevant to terraced/dense
  typologies, see `residential/open.md`) would be buem-side work, not
  something to push upstream to `weather`.
