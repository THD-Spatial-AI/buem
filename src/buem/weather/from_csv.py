import os
from pathlib import Path
import pandas as pd
import numpy as np

class CsvWeatherData:
    def __init__(self, csv_relative_path=None, cache_path=None):
        buem_root = Path(__file__).parent.parent
        self.csv_path = buem_root / csv_relative_path
        self.cache_path = buem_root / cache_path if cache_path else None
        self.df = self._load_and_prepare()

    def _load_and_prepare(self):
        if self.cache_path and os.path.exists(self.cache_path):
            return pd.read_feather(self.cache_path)
        df = pd.read_csv(self.csv_path)
        df.set_index(df.columns[0], inplace=True)
        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = 'datetime'
        if self.cache_path:
            df.reset_index().to_feather(self.cache_path)
        return df       
    
    def extract_weather_columns(self):
        """Extracts required weather columns and renames them."""
        if self.df is None:
            raise ValueError("CSV data not loaded. Call read_csv() first.")
        # Map CSV columns to desired names
        columns_map = {
            "T": "T",
            "GHI": "GHI",
            "DNI": "DNI",
            "DHI": "DHI"
        }
        self.df = self.df[list(columns_map.keys())]
        self.df.rename(columns=columns_map, inplace=True)
        return self.df
    
    def get_hourly(self, method='mean'):
        """Return hourly resampled data."""
        if method == 'mean':
            return self.df.resample('H').mean()
        elif method == 'interpolate':
            return self.df.resample('H').interpolate()
        else:
            raise ValueError("Unknown method")

    def get_daily(self, method='mean'):
        """Return daily resampled data."""
        if method == 'mean':
            return self.df.resample('D').mean()
        else:
            raise ValueError("Unknown method")

    def reconstruct_dni_from_ghi(self, latitude: float, longitude: float) -> pd.DataFrame:
        """Reconstruct physically-consistent DNI and DHI from GHI using pvlib DISC model.

        COSMO-REA6 (and most NWP models) store DNI computed as
        ``(GHI - DHI) / cos(zenith)``.  Near the horizon cos(zenith) -> 0, so
        the stored DNI diverges wildly (>4000 W/m2 observed).

        pvlib's DISC decomposition model estimates DNI directly from GHI without
        this singularity, giving physically bounded values (0..~1000 W/m2 for NL).
        DHI is then back-computed as ``DHI = GHI - DNI * cos(zenith)``.

        The GHI column is **not modified** — only DNI and DHI are replaced.

        Parameters
        ----------
        latitude, longitude : float
            Site coordinates in decimal degrees (positive North / East).

        Returns
        -------
        pd.DataFrame
            Copy of self.df with DNI and DHI columns replaced by DISC-derived values.
        """
        import pvlib

        if self.df is None:
            raise ValueError("Data not loaded. Call _load_and_prepare first.")
        if "GHI" not in self.df.columns:
            raise ValueError("GHI column required for DNI reconstruction.")

        solpos = pvlib.solarposition.get_solarposition(
            self.df.index, latitude, longitude
        )
        dni_extra = pvlib.irradiance.get_extra_radiation(self.df.index.dayofyear)

        # DISC: empirical decomposition of GHI into DNI (Iqbal 1983, pvlib implementation)
        disc_result = pvlib.irradiance.disc(
            ghi=self.df["GHI"],
            solar_zenith=solpos["apparent_zenith"],
            datetime_or_doy=self.df.index,
        )
        # Hard physical upper-bound: DNI cannot exceed extraterrestrial irradiance
        dni_disc = disc_result["dni"].clip(lower=0, upper=dni_extra).fillna(0)

        # Back-compute DHI = GHI - DNI * cos(zenith), bounded to [0, GHI]
        cos_z = np.cos(np.radians(solpos["apparent_zenith"].clip(upper=90))).clip(lower=0)
        dhi_derived = (self.df["GHI"] - dni_disc * cos_z).clip(lower=0, upper=self.df["GHI"]).fillna(0)

        df_out = self.df.copy()
        df_out["DNI"] = dni_disc
        df_out["DHI"] = dhi_derived
        return df_out

if __name__=="__main__":
    import time
    start_time = time.time()
    loader = CsvWeatherData("data\\COSMO_Year__ix_389_660.csv")
    df = loader.extract_weather_columns()
    print(f"total time taken: {time.time() - start_time}")
    print(f"df: {df}")