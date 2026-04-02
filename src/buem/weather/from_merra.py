"""Load location-specific weather from MERRA-2 NetCDF files.

MERRA-2 files follow the naming convention ``combined_merra_{year}.nc``
and contain at minimum:
  - ``T2M``   : temperature at 2 m (K), dims (lat, lon, time)
  - ``SWGDN`` : surface incoming shortwave radiation = GHI (W/m²)
  - ``lat``   : 1-D latitude coordinate (degrees North)
  - ``lon``   : 1-D longitude coordinate (degrees East)

DNI and DHI are derived from GHI via pvlib DISC decomposition.

Directory layout
----------------
``BUEM_WEATHER_DIR`` can point to:

a) A directory containing ``combined_merra_{year}.nc`` files directly —
   all available years are loaded for the given lat/lon.

b) A directory containing country sub-directories
   (``germany/``, ``netherlands/``, ``austria/``, ``czech/``), each
   holding their own ``combined_merra_{year}.nc`` files.  The best
   matching country is auto-detected from the building coordinates.

Both layouts are handled transparently — callers always get a single
DataFrame covering all available years for the location.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Kelvin → Celsius offset
_K_OFFSET = 273.15
# MERRA-2 fill value used for masked/missing grid cells
_MERRA_FILL = 9.83e31

# Approximate bounding boxes (lat_min, lat_max, lon_min, lon_max) per country.
# Used only when BUEM_WEATHER_DIR contains country sub-directories.
_COUNTRY_BOUNDS: dict[str, tuple[float, float, float, float]] = {
    "germany":     (47.0, 56.0,  5.5, 15.5),
    "netherlands": (50.5, 54.0,  3.0,  7.5),
    "austria":     (46.0, 49.5,  9.0, 17.5),
    "czech":       (48.0, 52.0, 11.5, 19.0),
}

# Fallback priority when a point sits inside multiple country bounding boxes.
_COUNTRY_PRIORITY = ["germany", "netherlands", "austria", "czech"]


def _nc_years_in_dir(directory: Path) -> list[int]:
    """Return sorted list of years found as ``combined_merra_{year}.nc`` in *directory*."""
    years = []
    for f in directory.iterdir():
        m = re.match(r"combined_merra_(\d{4})\.nc$", f.name)
        if m:
            years.append(int(m.group(1)))
    return sorted(years)


def _resolve_data_dir(base_dir: Path, lat: float, lon: float) -> Path:
    """Return the NetCDF directory best matching (lat, lon).

    If *base_dir* directly contains ``combined_merra_*.nc`` files, return it.
    Otherwise search for country sub-directories and pick the best match.

    Parameters
    ----------
    base_dir : Path
        Value of ``BUEM_WEATHER_DIR`` (or the caller-supplied directory).
    lat, lon : float
        Building coordinates in decimal degrees.

    Returns
    -------
    Path
        Directory that contains ``combined_merra_{year}.nc`` files.

    Raises
    ------
    FileNotFoundError
        If no usable NetCDF directory can be found.
    """
    # Case A: files are directly inside base_dir
    if _nc_years_in_dir(base_dir):
        return base_dir

    # Case B: country sub-directories
    # Collect all countries whose bounding box contains the point
    candidates: list[tuple[str, float]] = []
    for country, (lat_min, lat_max, lon_min, lon_max) in _COUNTRY_BOUNDS.items():
        subdir = base_dir / country
        if not subdir.is_dir():
            continue
        if not _nc_years_in_dir(subdir):
            continue
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            priority = _COUNTRY_PRIORITY.index(country) if country in _COUNTRY_PRIORITY else 99
            candidates.append((country, priority))

    if candidates:
        # Pick the highest-priority (lowest index) matching country
        best = min(candidates, key=lambda x: x[1])[0]
        logger.debug("Resolved lat=%.3f lon=%.3f → %s MERRA data", lat, lon, best)
        return base_dir / best

    # Case C: no exact match — fall back to any country whose sub-directory has files,
    # using the nearest bounding-box centre as distance metric
    nearest: Optional[tuple[str, float]] = None
    for country, (lat_min, lat_max, lon_min, lon_max) in _COUNTRY_BOUNDS.items():
        subdir = base_dir / country
        if not subdir.is_dir() or not _nc_years_in_dir(subdir):
            continue
        clat = (lat_min + lat_max) / 2
        clon = (lon_min + lon_max) / 2
        dist = (lat - clat) ** 2 + (lon - clon) ** 2
        if nearest is None or dist < nearest[1]:
            nearest = (country, dist)

    if nearest:
        logger.warning(
            "lat=%.3f lon=%.3f is outside all known country bounds; "
            "using nearest available country: %s",
            lat, lon, nearest[0],
        )
        return base_dir / nearest[0]

    raise FileNotFoundError(
        f"No MERRA-2 NetCDF files found in {base_dir} or its country sub-directories. "
        "Expected files named combined_merra_{year}.nc."
    )


class MerraWeatherData:
    """Extract hourly T, GHI, DNI, DHI for a location from MERRA-2 NetCDF files.

    Loads **all available years** from the appropriate country directory and
    concatenates them into a single DataFrame.  Use ``get_weather_df(year=...)``
    to retrieve a single-year slice for the thermal model.

    Supported countries: Germany, Netherlands, Austria, Czech Republic.

    Parameters
    ----------
    base_dir : str or Path
        ``BUEM_WEATHER_DIR`` — either a flat directory of ``.nc`` files or a
        parent directory with country sub-directories.
    lat : float
        Site latitude in decimal degrees (positive North).
    lon : float
        Site longitude in decimal degrees (positive East).
    """

    def __init__(
        self,
        base_dir: Union[str, Path],
        lat: float,
        lon: float,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.lat = lat
        self.lon = lon

        self._data_dir = _resolve_data_dir(self.base_dir, lat, lon)
        self._available_years = _nc_years_in_dir(self._data_dir)

        if not self._available_years:
            raise FileNotFoundError(
                f"No combined_merra_{{year}}.nc files found in {self._data_dir}"
            )

        self._df_all = self._load_all_years()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def available_years(self) -> list[int]:
        """Years for which MERRA-2 data was found."""
        return list(self._available_years)

    def get_weather_df(self, year: Optional[int] = None) -> pd.DataFrame:
        """Return weather DataFrame with columns T, GHI, DNI, DHI.

        Parameters
        ----------
        year : int, optional
            If given, return only rows for that calendar year (8 760 rows for
            a non-leap year).  If the year is not available, falls back to the
            nearest available year and logs a warning.
            If omitted, the full multi-year DataFrame is returned.

        Returns
        -------
        pd.DataFrame
            Hourly data with a UTC DatetimeIndex (timezone-naive).
            Columns: T (°C), GHI (W/m²), DNI (W/m²), DHI (W/m²).
        """
        if year is None:
            return self._df_all.copy()

        if year in self._available_years:
            mask = self._df_all.index.year == year
            return self._df_all.loc[mask].copy()

        # Fall back to nearest available year
        nearest = min(self._available_years, key=lambda y: abs(y - year))
        logger.warning(
            "MERRA-2 data for year %d not available in %s; "
            "using nearest available year %d instead.",
            year, self._data_dir, nearest,
        )
        mask = self._df_all.index.year == nearest
        return self._df_all.loc[mask].copy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_all_years(self) -> pd.DataFrame:
        """Load and concatenate all available yearly NetCDF files."""
        frames: list[pd.DataFrame] = []
        for year in self._available_years:
            try:
                df = self._load_one_year(year)
                frames.append(df)
            except Exception as exc:
                logger.warning("Skipping MERRA-2 year %d: %s", year, exc)

        if not frames:
            raise RuntimeError(
                f"Failed to load any MERRA-2 data from {self._data_dir}"
            )

        combined = pd.concat(frames).sort_index()
        # Derive DNI/DHI once over the full concatenated series for consistency
        combined = self._derive_dni_dhi(combined)
        return combined

    def _load_one_year(self, year: int) -> pd.DataFrame:
        """Open one NetCDF file and extract T and GHI for the nearest grid cell."""
        try:
            import xarray as xr
        except ImportError as exc:
            raise ImportError(
                "xarray is required for MERRA-2 weather loading. "
                "Install it with: pip install xarray netCDF4"
            ) from exc

        nc_path = self._data_dir / f"combined_merra_{year}.nc"
        ds = xr.open_dataset(nc_path)
        try:
            lat_arr = ds["lat"].values
            lon_arr = ds["lon"].values
            lat_idx = int(np.argmin(np.abs(lat_arr - self.lat)))
            lon_idx = int(np.argmin(np.abs(lon_arr - self.lon)))

            # Dimensions are (lat, lon, time) based on PV-simulation convention
            t2m = ds["T2M"].values[lat_idx, lon_idx, :].astype(float)
            ghi = ds["SWGDN"].values[lat_idx, lon_idx, :].astype(float)
        finally:
            ds.close()

        n_hours = len(t2m)
        index = pd.date_range(start=f"{year}-01-01", periods=n_hours, freq="h")

        # Replace MERRA-2 fill values before any arithmetic
        t2m = np.where(t2m > _MERRA_FILL / 2, 0.0, t2m)
        ghi = np.where(ghi > _MERRA_FILL / 2, 0.0, ghi).clip(min=0.0)

        return pd.DataFrame(
            {"T": t2m - _K_OFFSET, "GHI": ghi},
            index=index,
        )

    def _derive_dni_dhi(self, df: pd.DataFrame) -> pd.DataFrame:
        """Derive DNI and DHI from GHI via pvlib DISC decomposition.

        MERRA-2 stores SWGDN (GHI) but not DNI or DHI directly.  The DISC
        model (Iqbal 1983, pvlib implementation) estimates DNI from GHI
        without the horizon singularity that affects NWP-stored values.
        DHI is back-computed as ``GHI - DNI * cos(zenith)``.

        Parameters
        ----------
        df : pd.DataFrame
            Multi-year DataFrame with columns T and GHI.

        Returns
        -------
        pd.DataFrame
            Same DataFrame with DNI and DHI columns appended.
        """
        import pvlib

        solpos = pvlib.solarposition.get_solarposition(df.index, self.lat, self.lon)
        dni_extra = pvlib.irradiance.get_extra_radiation(df.index.dayofyear)

        disc = pvlib.irradiance.disc(
            ghi=df["GHI"],
            solar_zenith=solpos["apparent_zenith"],
            datetime_or_doy=df.index,
        )
        # Clip to physical bounds: DNI in [0, extraterrestrial irradiance]
        dni = disc["dni"].clip(lower=0, upper=dni_extra).fillna(0)

        # DHI = GHI − DNI × cos(zenith), bounded to [0, GHI]
        cos_z = (
            np.cos(np.radians(solpos["apparent_zenith"].clip(upper=90)))
            .clip(lower=0)
        )
        dhi = (df["GHI"] - dni * cos_z).clip(lower=0, upper=df["GHI"]).fillna(0)

        df["DNI"] = dni
        df["DHI"] = dhi
        return df
