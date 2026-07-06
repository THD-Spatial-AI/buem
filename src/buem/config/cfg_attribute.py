import pandas as pd
import numpy as np
import os
from pathlib import Path
from typing import Any, Dict

from .attribute_types import AttributeCategory, AttrType, AttributeSpec
from buem.weather.from_merra import MerraWeatherData, _nc_years_in_dir, _COUNTRY_PRIORITY

import logging as _logging
_log = _logging.getLogger(__name__)

# ── Optional external sub-package (now an independent repo in UU-BUEM org) ────
# occupancy: https://github.com/UU-BUEM/occupancy — not published to PyPI,
# install with: pip install git+https://github.com/UU-BUEM/occupancy.git
try:
    from occupancy.internal_gains.occupancy_profile import OccupancyProfile  # type: ignore[import]
    from occupancy.electricity.electricity_consumption import ElectricityConsumptionProfile  # type: ignore[import]
    _OCCUPANCY_AVAILABLE = True
except ImportError:
    _OCCUPANCY_AVAILABLE = False
    OccupancyProfile = None  # type: ignore[assignment,misc]
    ElectricityConsumptionProfile = None  # type: ignore[assignment,misc]

# --- changed code: make weather CSV path configurable via BUEM_WEATHER_DIR env var ---
# Default to package-local data/weather folder if env var is not set so behavior is backwards-compatible.
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "weather"))
WEATHER_DIR = os.environ.get("BUEM_WEATHER_DIR", DEFAULT_DATA_DIR)
WEATHER_CSV = os.path.join(WEATHER_DIR, "COSMO_Year__ix_390_650.csv")
WEATHER_CACHE = os.path.join(WEATHER_DIR, "COSMO_Year__ix_390_650_processed.feather")

# Default location used only for the module-level representative weather sample
# below; individual API requests override this with their actual lat/lon.
_DEFAULT_LAT = 51.5   # Central Germany
_DEFAULT_LON = 10.0
_DEFAULT_YEAR = 2018


def _has_merra_data(weather_dir: str) -> bool:
    """True if MERRA-2 combined_merra_{year}.nc files exist directly in weather_dir or a country subdir."""
    merra_dir = Path(weather_dir)
    return bool(_nc_years_in_dir(merra_dir)) or any(
        (merra_dir / c).is_dir() and bool(_nc_years_in_dir(merra_dir / c))
        for c in _COUNTRY_PRIORITY
    )


def _load_default_weather() -> pd.DataFrame:
    """Load a representative yearly weather dataset at module import time.

    Priority:
    1. MERRA-2 NetCDF (``combined_merra_{year}.nc``) if present in BUEM_WEATHER_DIR
    2. COSMO CSV (``COSMO_Year__ix_390_650.csv``), with pvlib DISC-reconstructed DNI/DHI
    3. Synthetic zero-filled fallback so the module can still be imported
    """
    if _has_merra_data(WEATHER_DIR):
        _log.info("Loading default MERRA-2 weather (%d) from %s", _DEFAULT_YEAR, WEATHER_DIR)
        loader = MerraWeatherData(WEATHER_DIR, lat=_DEFAULT_LAT, lon=_DEFAULT_LON)
        return loader.get_weather_df(year=_DEFAULT_YEAR)

    if os.path.exists(WEATHER_CSV):
        # Try loading the already-processed feather cache (includes DISC-reconstructed DNI/DHI).
        # This avoids the ~2-3s pvlib DISC computation on every module import (critical for
        # multiprocessing workers that each re-import this module).
        if os.path.exists(WEATHER_CACHE):
            df = pd.read_feather(WEATHER_CACHE)
            df.set_index(df.columns[0], inplace=True)
            df.index = pd.to_datetime(df.index)
            return df

        # Inline CSV loading with pvlib DISC reconstruction (replaces buem.weather.from_csv).
        # pvlib is a core buem dependency; no external weather package required for this step.
        import pvlib  # type: ignore[import-untyped]

        _log.info("Loading default COSMO weather from %s", WEATHER_CSV)
        _df = pd.read_csv(WEATHER_CSV)
        _df.set_index(_df.columns[0], inplace=True)
        _df.index = pd.to_datetime(_df.index, utc=True)
        _df = _df[["T", "GHI", "DNI", "DHI"]].copy()

        # Reconstruct DNI and DHI from GHI using pvlib DISC decomposition.
        # COSMO-REA6 stores DNI = (GHI-DHI)/cos(zenith), which diverges near the horizon
        # (observed max: 4951 W/m2, physically impossible).  DISC gives bounded 0..~1000 W/m2.
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

        df = _df.copy()
        df.index = df.index.tz_convert(None)

        # Save processed weather to feather cache for fast reloading by worker processes
        try:
            df.reset_index().to_feather(WEATHER_CACHE)
        except Exception:
            pass  # Non-critical: caching failure should not block model execution

        return df

    _log.warning(
        "No weather data found in BUEM_WEATHER_DIR=%s. "
        "Using synthetic zero-filled fallback. "
        "Set BUEM_WEATHER_DIR to a directory containing MERRA-2 .nc files or "
        "COSMO_Year__ix_390_650.csv.",
        WEATHER_DIR,
    )
    idx = pd.date_range(f"{_DEFAULT_YEAR}-01-01", periods=8760, freq="h")
    return pd.DataFrame({"T": 10.0, "GHI": 0.0, "DNI": 0.0, "DHI": 0.0}, index=idx)


df_weather = _load_default_weather()
main_index = df_weather.index
n_hours = len(main_index)
temp_profile = df_weather["T"]
ghi_profile = df_weather["GHI"]
dni_profile = df_weather["DNI"]   # DISC-reconstructed, physically bounded
dhi_profile = df_weather["DHI"]   # back-computed from GHI - DNI*cos(zenith)

# Generate electricity load profile: use buem-occupancy if available, else sinusoidal fallback.
# Install the occupancy package: pip install buem-occupancy
if _OCCUPANCY_AVAILABLE:
    _occ = OccupancyProfile(num_persons=4, year=2018, seed=42)
    _occ.generate()
    _elec_df = ElectricityConsumptionProfile(occupancy_profile=_occ, seed=42).generate()
    realistic_elec_load = _elec_df["total_power_kwh"]  # kWh per hour
else:
    # Fallback: simple sinusoidal daily pattern scaled to ~3.5 kWh/day (avg Dutch household)
    import warnings
    warnings.warn(
        "buem-occupancy package not found; using sinusoidal electricity load fallback. "
        "Install it with: pip install buem-occupancy",
        ImportWarning,
        stacklevel=1,
    )
    _t = np.linspace(0, 2 * np.pi, n_hours, endpoint=False)
    realistic_elec_load = pd.Series(
        0.15 + 0.12 * (1 - np.cos(_t)) + 0.04 * (1 - np.cos(2 * _t)),
        index=main_index,
        name="elecLoad",
    )

# Build attribute specs using realistic electricity load
ATTRIBUTE_SPECS: Dict[str, AttributeSpec] = {
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
        default=pd.Series([0.1] * n_hours, index=main_index),
        doc="Internal gains profile (pd.Series)",
    ),
    "occ_nothome": AttributeSpec("occ_nothome", AttributeCategory.FIXED, AttrType.SERIES,
                                 default=pd.Series(0.5 * (1 + np.sin(np.linspace(-np.pi/2, 3*np.pi/2, n_hours))), index=main_index),
                                 doc="Occupancy away profile"),
    "occ_sleeping": AttributeSpec("occ_sleeping", AttributeCategory.FIXED, AttrType.SERIES,
                                  default=pd.Series(0.5 * (1 - np.cos(np.linspace(0, 2*np.pi, n_hours))), index=main_index),
                                  doc="Sleeping occupancy profile"),
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
    "num_persons": AttributeSpec("num_persons", AttributeCategory.FIXED, AttrType.INT, 4, doc="Default persons for electricity profile generation"),
    "year": AttributeSpec("year", AttributeCategory.FIXED, AttrType.INT, 2018, doc="Default year for profile generation"),
    "seed": AttributeSpec("seed", AttributeCategory.FIXED, AttrType.INT, 42, doc="RNG seed for reproducible electricity profiles (default: 42)"),
    "use_provided_elecLoad": AttributeSpec("use_provided_elecLoad", AttributeCategory.BOOLEAN, AttrType.BOOL, False, doc="If true, keep provided elecLoad even when force=True"),
}

# Legacy default cfg dict (keeps existing API for other modules)
cfg: Dict[str, Any] = {spec.name: spec.default for spec in ATTRIBUTE_SPECS.values()}
# Ensure the DataFrame is the actual DataFrame object (already set in spec defaults)
cfg["weather"] = ATTRIBUTE_SPECS["weather"].default
