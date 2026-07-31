import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from .attribute_types import AttributeCategory, AttributeSpec, AttrType

logger = logging.getLogger(__name__)

# ── Optional external sub-packages (now independent repos in UU-BUEM org) ─────
# occupancy: https://github.com/UU-BUEM/occupancy
# weather:   https://github.com/UU-BUEM/weather
# Install via: pip install buem[occupancy,weather]  (or `pip install occupancy` / `pip install weather` directly)
try:
    from occupancy import ElectricityConsumptionProfile, HouseholdProfile, to_buem_profiles  # type: ignore[import]
    _OCCUPANCY_AVAILABLE = True
except ImportError:
    _OCCUPANCY_AVAILABLE = False
    ElectricityConsumptionProfile = None  # type: ignore[assignment,misc]
    HouseholdProfile = None  # type: ignore[assignment,misc]
    to_buem_profiles = None  # type: ignore[assignment,misc]

# Defaults for the built-in household electricity/internal-gains profile below;
# also used as the "num_persons"/"year"/"seed" AttributeSpec defaults further down.
DEFAULT_NUM_PERSONS = 4
DEFAULT_YEAR = 2018
DEFAULT_SEED = 42

# TABULA residential building-size classes (see BuildingIdentity.building_type,
# src/buem/buildings/building.py). Anything outside this set is routed to
# occupancy's ServiceBuildingProfile instead of HouseholdProfile -- see
# AttributeBuilder.generate_electricity_profile(). occupancy's own 8 service
# types (supermarket/office/restaurant/school/hotel/bakery/warehouse/clinic)
# are deliberately not hand-copied here; occupancy.services_buildings.
# SERVICE_BUILDING_TYPES / get_building_type() is the single source of truth
# for that side, kept up to date independently in the occupancy repo.
RESIDENTIAL_BUILDING_TYPES = frozenset({"SFH", "MFH", "TH", "AB"})
DEFAULT_BUILDING_TYPE = "MFH"

# --- changed code: make weather CSV path configurable via BUEM_WEATHER_DIR env var ---
# Default to package-local data/weather folder if env var is not set so behavior is backwards-compatible.
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "weather"))
WEATHER_DIR = os.environ.get("BUEM_WEATHER_DIR", DEFAULT_DATA_DIR)
WEATHER_CSV = os.path.join(WEATHER_DIR, "COSMO_Year__ix_390_650.csv")
WEATHER_CACHE = os.path.join(WEATHER_DIR, "COSMO_Year__ix_390_650_processed.feather")

if not os.path.exists(WEATHER_CSV):
    raise FileNotFoundError(
        f"Weather CSV not found at {WEATHER_CSV}. "
        "Provide the file there or set BUEM_WEATHER_DIR to a folder containing "
        "COSMO_Year__ix_390_650.csv (e.g. mount ./data/weather and set env var accordingly)."
    )

# Try loading the already-processed feather cache (includes DISC-reconstructed DNI/DHI).
# This avoids the ~2-3s pvlib DISC computation on every module import (critical for
# multiprocessing workers that each re-import this module).
if os.path.exists(WEATHER_CACHE):
    df_weather = pd.read_feather(WEATHER_CACHE)
    df_weather.set_index(df_weather.columns[0], inplace=True)
    df_weather.index = pd.to_datetime(df_weather.index)
else:
    # Inline CSV loading with pvlib DISC reconstruction (replaces buem.weather.from_csv).
    # pvlib is a core buem dependency; no external weather package required for this step.
    import pvlib  # type: ignore[import-untyped]

    _df = pd.read_csv(WEATHER_CSV)
    _df.set_index(_df.columns[0], inplace=True)
    _df.index = pd.to_datetime(_df.index, utc=True)
    _df = _df[["T", "GHI", "DNI", "DHI"]].copy()

    # Reconstruct DNI and DHI from GHI using pvlib DISC decomposition.
    # COSMO-REA6 stores DNI = (GHI-DHI)/cos(zenith), which diverges near the horizon
    # (observed max: 4951 W/m2, physically impossible).  DISC gives bounded 0..~1000 W/m2.
    # NOTE: these coordinates are the fixed COSMO-REA6 grid cell this CSV was extracted for
    # (encoded in the filename's ix_390_650 grid indices), not the "latitude"/"longitude"
    # AttributeSpec defaults below (52.0/5.0) which describe the building's own location for
    # solar-gain/shading calculations. They are intentionally independent: swapping in a
    # different building location does not change which weather-station grid cell this file
    # represents.
    _solpos = pvlib.solarposition.get_solarposition(_df.index, latitude=52.07, longitude=5.07)
    _dni_extra = pvlib.irradiance.get_extra_radiation(_df.index.dayofyear)
    _disc = pvlib.irradiance.disc(
        ghi=_df["GHI"],
        solar_zenith=_solpos["apparent_zenith"],
        datetime_or_doy=_df.index,
    )
    _df["DNI"] = _disc["dni"].clip(lower=0, upper=_dni_extra).fillna(0)
    _cos_z = np.cos(np.radians(_solpos["apparent_zenith"].clip(upper=90))).clip(lower=0)
    _df["DHI"] = (_df["GHI"] - _df["DNI"] * _cos_z).clip(lower=0, upper=_df["GHI"]).fillna(0)

    df_weather = _df.copy()
    df_weather.index = df_weather.index.tz_convert(None)

    # Save processed weather to feather cache for fast reloading by worker processes
    try:
        df_weather.reset_index().to_feather(WEATHER_CACHE)
    except (OSError, ValueError) as exc:
        # Non-critical: caching failure should not block model execution.
        logger.warning("Could not write weather feather cache %s: %s", WEATHER_CACHE, exc)

main_index = df_weather.index
n_hours = len(main_index)
temp_profile = df_weather["T"]
ghi_profile = df_weather["GHI"]
dni_profile = df_weather["DNI"]   # DISC-reconstructed, physically bounded
dhi_profile = df_weather["DHI"]   # back-computed from GHI - DNI*cos(zenith)

# Generate Q_ig/elecLoad/occ_nothome/occ_sleeping: use occupancy's to_buem_profiles() if
# available, else a synthetic sinusoidal fallback for all four series.
# Install the occupancy package: pip install buem[occupancy]
if _OCCUPANCY_AVAILABLE:
    _household = HouseholdProfile(num_persons=DEFAULT_NUM_PERSONS, year=DEFAULT_YEAR, seed=DEFAULT_SEED)
    _elec = ElectricityConsumptionProfile(occupancy_profile=_household, seed=DEFAULT_SEED)
    _buem_inputs = to_buem_profiles(_elec.to_result())
    realistic_elec_load = _buem_inputs["elecLoad"].reindex(main_index, method="nearest", fill_value=0.0)
    realistic_elec_load.name = "elecLoad"
    q_ig_profile = _buem_inputs["Q_ig"].reindex(main_index, method="nearest", fill_value=0.0)
    occ_nothome_profile = _buem_inputs["occ_nothome"].reindex(main_index, method="nearest", fill_value=0.0)
    occ_sleeping_profile = _buem_inputs["occ_sleeping"].reindex(main_index, method="nearest", fill_value=0.0)
else:
    # Fallback: simple sinusoidal patterns (no external occupancy data available)
    import warnings
    warnings.warn(
        "occupancy package not found; using synthetic sinusoidal fallback profiles for "
        "Q_ig/elecLoad/occ_nothome/occ_sleeping. Install it with: pip install buem[occupancy]",
        ImportWarning,
        stacklevel=1,
    )
    # ~3.5 kWh/day sinusoidal daily pattern (avg Dutch household)
    _t = np.linspace(0, 2 * np.pi, n_hours, endpoint=False)
    realistic_elec_load = pd.Series(
        0.15 + 0.12 * (1 - np.cos(_t)) + 0.04 * (1 - np.cos(2 * _t)),
        index=main_index,
        name="elecLoad",
    )
    q_ig_profile = pd.Series([0.1] * n_hours, index=main_index)
    occ_nothome_profile = pd.Series(
        0.5 * (1 + np.sin(np.linspace(-np.pi / 2, 3 * np.pi / 2, n_hours))), index=main_index
    )
    occ_sleeping_profile = pd.Series(
        0.5 * (1 - np.cos(np.linspace(0, 2 * np.pi, n_hours))), index=main_index
    )

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
    "bldg_tabula_id": AttributeSpec("bldg_tabula_id", AttributeCategory.FIXED, AttrType.STR, "NL.N.MFH.01.Gen"),
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
        doc="Internal gains profile (pd.Series), kW. From occupancy.to_buem_profiles() when available.",
    ),
    "occ_nothome": AttributeSpec("occ_nothome", AttributeCategory.FIXED, AttrType.SERIES,
                                 default=occ_nothome_profile,
                                 doc="Occupancy away profile (fraction not home). From occupancy.to_buem_profiles() when available."),
    "occ_sleeping": AttributeSpec("occ_sleeping", AttributeCategory.FIXED, AttrType.SERIES,
                                  default=occ_sleeping_profile,
                                  doc="Sleeping occupancy profile (fraction asleep). From occupancy.to_buem_profiles() when available."),
    "latitude": AttributeSpec("latitude", AttributeCategory.FIXED, AttrType.FLOAT, 52.0),
    "longitude": AttributeSpec("longitude", AttributeCategory.FIXED, AttrType.FLOAT, 5.0),
    # New structured component tree: component-level U (same for all elements) + element list
    "components": AttributeSpec(
        "components",
        AttributeCategory.OTHER,
        AttrType.OBJECT,
        default={
            # Geometry represents a realistic Dutch single-family house (SFH), ~100 m2 floor area.
            # Reference: TABULA NL.N.SFH.01.Gen proportions scaled to 100 m2.
            # Wall areas are NET opaque (gross wall minus window and door openings).
            # Wall_1 (south, az=180) carries most solar gain; Wall_2 (north+east+west
            # combined, modelled north-facing az=0) has near-zero solar contribution
            # but accounts for the full N/E/W envelope conductance.
            # pvlib tilt convention: 0=horizontal-up, 90=vertical, 180=horizontal-down.
            "Walls": {
                "U": 1.61,
                "b_transmission": 1.0,
                "elements": [
                    {"id": "Wall_1", "area": 40.0, "azimuth": 180.0, "tilt": 90.0},  # South facade (net): ~7m x 5m - wins - door
                    {"id": "Wall_2", "area": 75.0, "azimuth":   0.0, "tilt": 90.0},  # N+E+W combined (net), north-facing = minimal solar
                ],
            },
            "Roof": {
                "U": 1.54,
                "elements": [
                    {"id": "Roof_1", "area": 60.0, "azimuth": 180.0, "tilt": 30.0},  # Pitched roof: 50 m2 footprint / cos(30)
                ],
            },
            "Floor": {"U": 1.72, "elements": [{"id": "Floor_1", "area": 50.0, "azimuth": 0.0, "tilt": 180.0}]},  # Ground floor footprint; tilt 180=downward, no solar
            "Windows": {
                "U": 5.2,
                "g_gl": 0.5,
                "elements": [
                    {"id": "Win_1", "area": 9.0, "surface": "Wall_1", "azimuth": 180.0, "tilt": 90.0},  # South windows (~9% of A_ref)
                    {"id": "Win_2", "area": 5.0, "surface": "Wall_2", "azimuth": 270.0, "tilt": 90.0},  # West/other windows
                ],
            },
            "Doors": {
                "U": 3.5,
                "elements": [
                    {"id": "Door_1", "area": 4.0, "surface": "Wall_1", "azimuth": 180.0, "tilt": 90.0}
                ]
            },
            # Natural ventilation: H_ve is calculated from n_air_infiltration + n_air_use in cfg
            # (both below).  The Ventilation element is a placeholder; air_changes is informational.
            "Ventilation": {"elements": [{"id": "Vent_1", "area": 0.0, "air_changes": 0.5}]},
        },
        doc="Structured component tree. Component-level 'U' applies to all elements; elements list carries per-surface geometry and area."
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
    "roofs": AttributeSpec("roofs", AttributeCategory.FIXED, AttrType.LIST, [{'roofTilt': 45.0, 'roofOrientation': 135.0, 'roofArea': 30.0}], doc="List of roof dicts"),
    "A_Window_North": AttributeSpec("A_Window_North", AttributeCategory.FIXED, AttrType.FLOAT, 5.0),
    "A_Window_East": AttributeSpec("A_Window_East", AttributeCategory.FIXED, AttrType.FLOAT, 5.0),
    "A_Window_South": AttributeSpec("A_Window_South", AttributeCategory.FIXED, AttrType.FLOAT, 5.0),
    "A_Window_West": AttributeSpec("A_Window_West", AttributeCategory.FIXED, AttrType.FLOAT, 5.0),
    "A_Window_Horizontal": AttributeSpec("A_Window_Horizontal", AttributeCategory.FIXED, AttrType.FLOAT, 5.0),
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
            "in AttributeBuilder.generate_electricity_profile()."
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
    "year": AttributeSpec("year", AttributeCategory.FIXED, AttrType.INT, DEFAULT_YEAR, doc="Default year for profile generation"),
    "seed": AttributeSpec("seed", AttributeCategory.FIXED, AttrType.INT, DEFAULT_SEED, doc="RNG seed for reproducible electricity profiles (default: 42)"),
    "use_provided_elecLoad": AttributeSpec("use_provided_elecLoad", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="If true, keep provided elecLoad even when force=True"),
    "weather_provider": AttributeSpec("weather_provider", AttributeCategory.FIXED, AttrType.STR, "era5-land",
                                       doc="Weather source for the dynamic per-location fetch: 'era5-land' (default), 'cosmo-rea6', or 'merra-2'. Only used when the optional weather package is installed."),
    "use_provided_weather": AttributeSpec("use_provided_weather", AttributeCategory.BOOLEAN, AttrType.BOOL, False,
                                           doc="If true, keep the provided weather DataFrame instead of dynamically fetching one for (latitude, longitude, year)."),
}

# Legacy default cfg dict (keeps existing API for other modules)
cfg: dict[str, Any] = {spec.name: spec.default for spec in ATTRIBUTE_SPECS.values()}
# Ensure the DataFrame is the actual DataFrame object (already set in spec defaults)
cfg["weather"] = ATTRIBUTE_SPECS["weather"].default
