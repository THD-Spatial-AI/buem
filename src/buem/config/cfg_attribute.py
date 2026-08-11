import logging
import os
from typing import Any

import pandas as pd

from buem.buildings.mapping.live_synthesis import synthesize_missing_openings
from buem.config.weather_cache import get_or_fetch_weather
from buem.env import load_env

from .attribute_types import AttributeCategory, AttributeSpec, AttrType

logger = logging.getLogger(__name__)

load_env()  # ensure BUEM_WEATHER_DATA_DIR/WEATHER_DATA_DIR are set before the fetch below

# occupancy (https://github.com/UU-BUEM/occupancy) is compulsory (2026-08-07),
# same treatment as weather (https://github.com/UU-BUEM/weather, compulsory
# 2026-08-03) -- every Q_ig/elecLoad/occ_nothome/occ_sleeping value comes from
# its real HouseholdProfile/ServiceBuildingProfile generation, so it's
# imported unconditionally like pandas/pvlib.
from occupancy import ElectricityConsumptionProfile, HouseholdProfile, to_buem_profiles  # type: ignore[import]

# Defaults for the built-in household electricity/internal-gains profile below;
# also used as the "num_persons"/"year"/"seed" AttributeSpec defaults further down.
DEFAULT_NUM_PERSONS = 4
DEFAULT_YEAR = 2018
DEFAULT_SEED = 42

# Default location/provider for the module-level weather default below and the
# "latitude"/"longitude"/"weather_provider" AttributeSpec defaults further down
# -- a single source of truth so the two can't drift apart.
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

# Real weather-module fetch for the module-level default location above (used
# by ATTRIBUTE_SPECS["weather"].default below, and by anything that imports
# this module without going through AttributeBuilder's per-building fetch --
# e.g. `buem run`'s demo path, cfg_building.WeatherConfig(None)). Cached to a
# local feather file keyed by (provider, lat, lon, year) via
# weather_cache.get_or_fetch_weather, exactly like any other building's fetch
# -- there is no bundled/shipped weather data file anymore, only this
# locally-generated cache of a real fetch. Requires BUEM_WEATHER_DATA_DIR (or
# weather's own WEATHER_DATA_DIR) to point at processed provider archives.
df_weather = get_or_fetch_weather(
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_YEAR, DEFAULT_WEATHER_PROVIDER
)

main_index = df_weather.index
n_hours = len(main_index)
temp_profile = df_weather["T"]
ghi_profile = df_weather["GHI"]
dni_profile = df_weather["DNI"]
dhi_profile = df_weather["DHI"]

# Generate Q_ig/elecLoad/occ_nothome/occ_sleeping via occupancy's real
# HouseholdProfile + ElectricityConsumptionProfile + to_buem_profiles()
# pipeline -- no fallback (occupancy is compulsory, see module-top import).
_household = HouseholdProfile(num_persons=DEFAULT_NUM_PERSONS, year=DEFAULT_YEAR, seed=DEFAULT_SEED)
_elec = ElectricityConsumptionProfile(occupancy_profile=_household, seed=DEFAULT_SEED)
_buem_inputs = to_buem_profiles(_elec.to_result())
realistic_elec_load = _buem_inputs["elecLoad"].reindex(main_index, method="nearest", fill_value=0.0)
realistic_elec_load.name = "elecLoad"
q_ig_profile = _buem_inputs["Q_ig"].reindex(main_index, method="nearest", fill_value=0.0)
occ_nothome_profile = _buem_inputs["occ_nothome"].reindex(main_index, method="nearest", fill_value=0.0)
occ_sleeping_profile = _buem_inputs["occ_sleeping"].reindex(main_index, method="nearest", fill_value=0.0)

# Build attribute specs using realistic electricity load
ATTRIBUTE_SPECS: dict[str, AttributeSpec] = {
    "weather": AttributeSpec(
        name="weather",
        category=AttributeCategory.WEATHER,
        type=AttrType.DATAFRAME,
        default=pd.DataFrame({
            "T": temp_profile,
            "GHI": ghi_profile,
            "DNI": dni_profile,
            "DHI": dhi_profile,
        }, index=main_index),
        doc="Weather DataFrame with columns T, GHI, DNI, DHI indexed by datetimes."
    ),
    "bldg_tabula_id": AttributeSpec(
        "bldg_tabula_id",
        AttributeCategory.FIXED,
        AttrType.STR,
        "NL.N.MFH.01.Gen",
        doc=(
            "TABULA archetype code (Code_BuildingVariant, e.g. "
            "'DE.N.MFH.03.Gen.ReEx.001.001'). Explicit override for the live "
            "LOD2->LOD3 envelope synthesis (buem.buildings.mapping."
            "live_synthesis) -- tried before the building_type/"
            "construction_period/country match. This module's own default "
            "('NL.N.MFH.01.Gen') does not match any row in the bundled "
            "(Germany-only) reference sheet, so it exercises the "
            "building_type/construction_period/country fallback instead --"
            " that's expected, not a bug."
        ),
    ),
    "costdatapath": AttributeSpec(
        "costdatapath",
        AttributeCategory.FIXED,
        AttrType.STR,
        os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "data", "default_2016.xlsx")
        ),
    ),
    "refurbishment": AttributeSpec("refurbishment", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="Deprecated: refurbishment decisions not used in parameterized model"),
    "force_refurbishment": AttributeSpec("force_refurbishment", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="Deprecated"),
    "occControl": AttributeSpec("occControl", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="Deprecated"),
    "nightReduction": AttributeSpec("nightReduction", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="Deprecated"),
    "capControl": AttributeSpec("capControl", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="Deprecated"),
    "elecLoad": AttributeSpec("elecLoad", AttributeCategory.FIXED, AttrType.SERIES,
                              default=realistic_elec_load,  # Use occupancy-based calculation
                              doc="Electric internal load profile from occupancy simulation (pd.Series)"),
    "Q_ig": AttributeSpec(
        "Q_ig",
        AttributeCategory.FIXED,
        AttrType.SERIES,
        default=q_ig_profile,
        doc="Internal gains profile (pd.Series), kW. From occupancy.to_buem_profiles().",
    ),
    "occ_nothome": AttributeSpec("occ_nothome", AttributeCategory.FIXED, AttrType.SERIES,
                                 default=occ_nothome_profile,
                                 doc="Occupancy away profile (fraction not home). From occupancy.to_buem_profiles()."),
    "occ_sleeping": AttributeSpec("occ_sleeping", AttributeCategory.FIXED, AttrType.SERIES,
                                  default=occ_sleeping_profile,
                                  doc="Sleeping occupancy profile (fraction asleep). From occupancy.to_buem_profiles()."),
    "latitude": AttributeSpec("latitude", AttributeCategory.FIXED, AttrType.FLOAT, DEFAULT_LATITUDE),
    "longitude": AttributeSpec("longitude", AttributeCategory.FIXED, AttrType.FLOAT, DEFAULT_LONGITUDE),
    # New structured component tree: component-level U (same for all elements) + element list
    "components": AttributeSpec(
        "components",
        AttributeCategory.OTHER,
        AttrType.OBJECT,
        default={
            # Geometry represents a realistic ~100 m2 Dutch residential building
            # footprint (TABULA-style wall/roof/floor proportions).
            #
            # Windows/Doors/Ventilation are deliberately *absent* here -- they
            # are synthesized internally by CfgBuilding.to_cfg_dict() from this
            # Walls geometry (buem.buildings.mapping.live_synthesis), the same
            # way a real EnerPlanET request that omits LOD3 detail is handled
            # (see CLAUDE.md "LOD3 envelope synthesis is internal to buem").
            # This demo previously hand-picked Windows/Doors/Ventilation values
            # that did not follow buildings.rst's documented sizing rules;
            # letting the real synthesis path fill them in keeps this default
            # an honest example of what buem actually computes, not a
            # hand-tuned stand-in.
            #
            # Wall areas below are GROSS (full wall footprint, not yet net of
            # window/door area) -- synthesis shrinks them to net opaque area
            # itself; do not also hand-subtract window/door area here.
            # Wall_1 (south, az=180) carries most solar gain; Wall_2 (north+east+west
            # combined, modelled north-facing az=0) has near-zero solar contribution
            # but accounts for the full N/E/W envelope conductance.
            # pvlib tilt convention: 0=horizontal-up, 90=vertical, 180=horizontal-down.
            "Walls": {
                "U": 1.61,
                "b_transmission": 1.0,
                "elements": [
                    {"id": "Wall_1", "area": 53.0, "azimuth": 180.0, "tilt": 90.0},  # South facade (gross)
                    {"id": "Wall_2", "area": 80.0, "azimuth":   0.0, "tilt": 90.0},  # N+E+W combined (gross), north-facing = minimal solar
                ],
            },
            "Roof": {
                "U": 1.54,
                "elements": [
                    {"id": "Roof_1", "area": 60.0, "azimuth": 180.0, "tilt": 30.0},  # Pitched roof: 50 m2 footprint / cos(30)
                ],
            },
            "Floor": {"U": 1.72, "elements": [{"id": "Floor_1", "area": 50.0, "azimuth": 0.0, "tilt": 180.0}]},  # Ground floor footprint; tilt 180=downward, no solar
        },
        doc=(
            "Structured component tree. Component-level 'U' applies to all "
            "elements; elements list carries per-surface geometry and area. "
            "Windows/Doors/Ventilation are synthesized internally from Walls "
            "by CfgBuilding.to_cfg_dict() when the caller omits them -- see "
            "buem.buildings.mapping.live_synthesis; supply them explicitly "
            "here (non-empty 'elements') to opt out of synthesis for a "
            "given component."
        ),
    ),
    "A_ref": AttributeSpec("A_ref", AttributeCategory.FIXED, AttrType.FLOAT, 100.0),  # Realistic reference floor area
    "h_room": AttributeSpec("h_room", AttributeCategory.FIXED, AttrType.FLOAT, 2.5),
    "n_air_infiltration": AttributeSpec("n_air_infiltration", AttributeCategory.FIXED, AttrType.FLOAT, 0.5),
    "n_air_use": AttributeSpec("n_air_use", AttributeCategory.FIXED, AttrType.FLOAT, 0.5),
    "design_T_min": AttributeSpec("design_T_min", AttributeCategory.FIXED, AttrType.FLOAT, -12.0),
    "onlyEnergyInvest": AttributeSpec("onlyEnergyInvest", AttributeCategory.BOOLEAN, AttrType.BOOL, False),
    "g_gl_n_Window": AttributeSpec("g_gl_n_Window", AttributeCategory.FIXED, AttrType.FLOAT, 0.5),
    "thermalClass": AttributeSpec("thermalClass", AttributeCategory.FIXED, AttrType.STR, "medium"),
    "c_m": AttributeSpec(
        "c_m",
        AttributeCategory.FIXED,
        AttrType.FLOAT,
        175.0,
        doc="Specific thermal capacity of building mass [kJ/m²K]. ISO 13790 medium class midpoint: (137.5+212.5)/2=175.",
    ),
    "comfortT_lb": AttributeSpec("comfortT_lb", AttributeCategory.FIXED, AttrType.FLOAT, 21.0),
    "comfortT_ub": AttributeSpec("comfortT_ub", AttributeCategory.FIXED, AttrType.FLOAT, 24.0),
    "F_sh_vert": AttributeSpec("F_sh_vert", AttributeCategory.FIXED, AttrType.FLOAT, 0.75),  # Realistic shading for Netherlands
    "F_sh_hor": AttributeSpec("F_sh_hor", AttributeCategory.FIXED, AttrType.FLOAT, 0.80),  # Realistic shading for Netherlands
    "F_f": AttributeSpec("F_f", AttributeCategory.FIXED, AttrType.FLOAT, 0.2),
    "F_w": AttributeSpec("F_w", AttributeCategory.FIXED, AttrType.FLOAT, 1.0),
    "F_red_htr": AttributeSpec(
        "F_red_htr",
        AttributeCategory.FIXED,
        AttrType.FLOAT,
        1.0,
        doc="Intermittent heating reduction factor (ISO 13790 §13.2.2). TABULA F_red_htr1: 0.95 (AB/MFH), 0.90 (SFH/TH). 1.0 = no reduction.",
    ),
    "ventControl": AttributeSpec("ventControl", AttributeCategory.BOOLEAN, AttrType.BOOL, False),
    "control": AttributeSpec("control", AttributeCategory.BOOLEAN, AttrType.BOOL, False),
    "building_type": AttributeSpec(
        "building_type",
        AttributeCategory.FIXED,
        AttrType.STR,
        DEFAULT_BUILDING_TYPE,
        doc=(
            "TABULA residential size class (SFH/MFH/TH/AB, see "
            "RESIDENTIAL_BUILDING_TYPES) or one of occupancy's service-building "
            "type ids (supermarket/office/restaurant/school/hotel/bakery/"
            "warehouse/clinic). Selects HouseholdProfile vs. ServiceBuildingProfile "
            "in AttributeBuilder.generate_electricity_profile(); also one of the "
            "TABULA archetype match keys for live LOD2->LOD3 envelope synthesis "
            "(buem.buildings.mapping.live_synthesis, via CfgBuilding.to_cfg_dict())."
        ),
    ),
    "construction_period": AttributeSpec(
        "construction_period",
        AttributeCategory.FIXED,
        AttrType.STR,
        "",
        doc=(
            "TABULA construction-year class (e.g. 'DE.04', or the bare '04' "
            "form EnerPlanET's v3/v4 send -- see CLAUDE.md 'v2 vs v3/v4 "
            "request formats'). Already forwarded end-to-end from a real v3 "
            "request's building.construction_period by "
            "geojson_validator.py::_convert_v3_to_v2(); registered here so "
            "CfgBuilding retains it (attributes not in ATTRIBUTE_SPECS are "
            "dropped by CfgBuilding._build_internal_cfg). Used, together "
            "with building_type/country, to resolve a TABULA archetype for "
            "live envelope synthesis -- see bldg_tabula_id and "
            "tabula_helpers.lookup_tabula_archetype. Empty string (no "
            "match) falls back to documented safe-default ratios."
        ),
    ),
    "country": AttributeSpec(
        "country",
        AttributeCategory.FIXED,
        AttrType.STR,
        "NL",
        doc=(
            "ISO 3166-1 alpha-2 country code. Same forwarding/registration "
            "rationale as construction_period above. The bundled TABULA "
            "reference sheet (tabula_building_child_features.xlsx) "
            "currently only covers 'DE', so this module's own 'NL' default "
            "deliberately exercises live_synthesis's safe-default-ratio "
            "fallback rather than a real TABULA match -- expected, not a bug."
        ),
    ),
    "capacity": AttributeSpec(
        "capacity",
        AttributeCategory.FIXED,
        AttrType.INT,
        None,
        doc=(
            "Service-building capacity (e.g. seats, beds, staff) passed to "
            "occupancy.ServiceBuildingProfile. Ignored for residential "
            "building_type values, where num_persons applies instead. "
            "None uses the service type's own capacity_default."
        ),
    ),
    "num_persons": AttributeSpec("num_persons", AttributeCategory.FIXED, AttrType.INT, DEFAULT_NUM_PERSONS, doc="Default persons for electricity profile generation"),
    "archetype": AttributeSpec(
        "archetype",
        AttributeCategory.FIXED,
        AttrType.STR,
        None,
        doc=(
            "occupancy household archetype (generic/working_couple/"
            "family_with_children/retired_single/student_shared) passed to "
            "occupancy.HouseholdProfile. Residential only -- ignored for "
            "service-building types. None falls back to "
            "DEFAULT_ARCHETYPE_BY_BUILDING_TYPE.get(building_type, 'generic')."
        ),
    ),
    "year": AttributeSpec("year", AttributeCategory.FIXED, AttrType.INT, DEFAULT_YEAR, doc="Default year for profile generation"),
    "seed": AttributeSpec(
        "seed",
        AttributeCategory.FIXED,
        AttrType.INT,
        DEFAULT_SEED,
        doc=(
            "RNG seed for reproducible occupancy profile generation "
            "(default: 42). Internal-only -- not part of the EnerPlanET "
            "request contract (deliberately absent from the v3/v4 request "
            "schemas and not forwarded by _convert_v3_to_v2()); overridable "
            "for direct AttributeBuilder calls/tests, e.g. to vary the "
            "profile deliberately. See .claude/occupancy_gains_handoff.md's "
            "seed-ownership note for why this stays buem-internal."
        ),
    ),
    "use_provided_elecLoad": AttributeSpec("use_provided_elecLoad", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="If true, keep provided elecLoad even when force=True"),
    "weather_provider": AttributeSpec(
        "weather_provider", AttributeCategory.FIXED, AttrType.STR, DEFAULT_WEATHER_PROVIDER,
        doc="Weather source for the per-location fetch: 'merra-2' (default), 'era5-land', or 'cosmo-rea6'."
    ),
    "use_provided_weather": AttributeSpec(
        "use_provided_weather", AttributeCategory.BOOLEAN, AttrType.BOOL, False,
        doc="If true, keep the provided weather DataFrame instead of dynamically fetching one for (latitude, longitude, year)."
    ),
}

# Legacy default cfg dict (keeps existing API for other modules)
cfg: dict[str, Any] = {spec.name: spec.default for spec in ATTRIBUTE_SPECS.values()}
# Ensure the DataFrame is the actual DataFrame object (already set in spec defaults)
cfg["weather"] = ATTRIBUTE_SPECS["weather"].default

# ATTRIBUTE_SPECS["components"].default above deliberately carries only
# Walls/Roof/Floor (see its own comment) -- CfgBuilding.to_cfg_dict() is the
# usual place Windows/Doors/Ventilation get synthesized (buem.buildings.
# mapping.live_synthesis), but some callers (e.g. ModelBUEM in tests/
# buem.main's demo path) use this legacy `cfg` dict directly, bypassing
# CfgBuilding entirely -- model_buem.py treats "Ventilation" as a required
# component and would raise if it were simply absent. Apply the same
# synthesis here once at import time so `cfg`/DEFAULT_CFG stays a complete,
# directly-runnable config exactly like before this change, and idempotent
# to call again from CfgBuilding.to_cfg_dict() when supplied through it.
cfg["components"] = synthesize_missing_openings(
    cfg["components"],
    building_type=cfg.get("building_type"),
    construction_period=cfg.get("construction_period"),
    country=cfg.get("country"),
    bldg_tabula_id=cfg.get("bldg_tabula_id"),
)
