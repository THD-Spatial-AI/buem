"""
Pure, side-effect-free building-type/archetype/equipment/location constants
shared across buem's config, integration, and request-validation layers.

Deliberately split out of ``cfg_attribute.py`` (2026-08-14, v3->v4
promotion): ``cfg_attribute.py`` does a real, eager
``weather.get_point_weather()`` fetch at module import time (its own
module-level ``df_weather = get_or_fetch_weather(...)`` backing the demo/
example-house default) -- importing *anything* from that module, even a
pure constant, pulls in that fetch as a side effect. This module holds
nothing that touches weather or occupancy at all, so
``geojson_validator.py`` -- which validates request *structure* and must
not require weather archives to be configured just to check a
``building_type`` value -- imports from here instead of from
``cfg_attribute.py``.

``cfg_attribute.py`` re-exports these same names unchanged (see its own
import block), so existing importers (``attribute_builder.py``,
``tests/test_building_types.py``, etc.) are unaffected by this split.
"""
from __future__ import annotations

# Defaults for the built-in household electricity/internal-gains profile
# (cfg_attribute.py's module-level demo) and the "num_persons"/"year"/"seed"
# AttributeSpec defaults.
DEFAULT_NUM_PERSONS = 4
DEFAULT_YEAR = 2018
DEFAULT_SEED = 42

# Default location/provider for cfg_attribute.py's module-level weather
# default and the "latitude"/"longitude"/"weather_provider" AttributeSpec
# defaults -- a single source of truth so the two can't drift apart.
DEFAULT_LATITUDE = 52.0
DEFAULT_LONGITUDE = 5.0
# era5-land was the original default; switched to merra-2 (2026-08-04) since
# era5-land currently fails at this cell/year -- see CLAUDE.md "Weather is
# compulsory" for the data-quality findings behind this choice.
DEFAULT_WEATHER_PROVIDER = "merra-2"

# TABULA residential building-size classes (see BuildingIdentity.building_type,
# src/buem/buildings/building.py). Anything outside this set is routed to
# occupancy's ServiceBuildingProfile instead of HouseholdProfile -- see
# AttributeBuilder.generate_electricity_profile(). occupancy's own 8 service
# types (supermarket/office/restaurant/school/hotel/bakery/warehouse/clinic)
# are deliberately not hand-copied here at runtime; occupancy.
# SERVICE_BUILDING_TYPES (top-level export since 2026-08-07, closing
# occupancy_gains_handoff.md's Gap 3) is the single source of truth for
# that side, kept up to date independently in the occupancy repo.
# tests/test_building_types.py::test_v4_building_type_enum_matches_occupancy
# is a drift guard: it fails CI if versions/v4/'s static schema enum (which,
# unlike this runtime set, genuinely is a hand-copied snapshot) falls out of
# sync with occupancy's actual registry.
RESIDENTIAL_BUILDING_TYPES = frozenset({"SFH", "MFH", "TH", "AB"})
DEFAULT_BUILDING_TYPE = "MFH"

# building_type -> occupancy household archetype, used by
# AttributeBuilder.generate_electricity_profile() as a fallback only when
# the caller doesn't supply an explicit "archetype" attribute (2026-08-07,
# closes the gap noted in .claude/residential/resolved.md). This is a
# first-pass heuristic, not a derivation: TABULA's SFH/MFH/TH/AB describe
# building *form* (attachment/size class), while occupancy's archetypes
# (occupancy.households.archetypes.HOUSEHOLD_ARCHETYPES) describe household
# *composition* -- there is no reliable 1:1 mapping between the two. The
# caller-supplied num_persons remains the dominant, more reliable signal;
# this table only picks a plausible default occupancy *schedule shape* when
# nothing more specific is known. Revisit with real occupancy-survey data
# if/when available rather than treating these as settled.
DEFAULT_ARCHETYPE_BY_BUILDING_TYPE: dict[str, str] = {
    "SFH": "family_with_children",  # detached houses skew toward families in TABULA's own survey basis
    "TH": "working_couple",  # terraced houses skew toward smaller working households
    "MFH": "generic",  # multi-family buildings house a wide mix of composition -- no single default fits
    "AB": "generic",  # apartment blocks: same reasoning as MFH
}

# Household equipment ids, hand-copied from occupancy's households/data/
# equipment.json (29 items, confirmed against the installed occupancy 3.1.0
# package, 2026-08-14). Unlike RESIDENTIAL_BUILDING_TYPES's service-type
# counterpart (occupancy.SERVICE_BUILDING_TYPES), occupancy has no top-level
# export for its equipment registry yet -- default_equipment_table() lives
# under occupancy.households.electricity, a "deep module path" occupancy's
# own CLAUDE.md flags as not guaranteed stable. This set can silently drift
# out of sync with occupancy's real registry if an item is added/renamed/
# removed there; promoting a stable top-level export is tracked as the first
# item in .claude/occupancy_module_activities.md. Used only to validate the
# optional "equipment" attribute's include/exclude item ids before they
# reach occupancy.ElectricityConsumptionProfile.
HOUSEHOLD_EQUIPMENT_TYPES = frozenset({
    "chest_freezer", "fridge_freezer", "refrigerator", "upright_freezer",
    "answer_machine", "cassette_cd_player", "clock", "cordless_telephone",
    "hi_fi", "iron", "vacuum", "fax", "personal_computer", "printer",
    "tv_1", "tv_2", "tv_3", "vcr_dvd", "tv_receiver_box", "hob", "oven",
    "microwave", "kettle", "small_cooking_group", "dish_washer",
    "tumble_dryer", "washing_machine", "washer_dryer", "lighting",
})
