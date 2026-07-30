"""
Build complete building attributes by merging payload, database, and defaults.
Generate weather and electricity profiles, and align timeseries indices.
"""
import warnings
from typing import Dict, Any, Optional, Callable
import pandas as pd

from buem.config.cfg_attribute import ATTRIBUTE_SPECS
from buem.config.validator import validate_cfg
from buem.config.weather_cache import get_or_fetch_weather, weather_available

# occupancy is an optional independent package (https://github.com/UU-BUEM/occupancy)
# Install with: pip install buem[occupancy]  (or `pip install occupancy` directly)
try:
    from occupancy import ElectricityConsumptionProfile, HouseholdProfile, to_buem_profiles  # type: ignore[import]
    _OCCUPANCY_AVAILABLE = True
except ImportError:
    _OCCUPANCY_AVAILABLE = False


class AttributeBuilder:
    """
    Merge building attributes from multiple sources and generate derived profiles.
    
    Precedence: payload > database > defaults (cfg_attribute.py)
    """
    
    def __init__(
        self,
        payload_attrs: Dict[str, Any],
        building_id: Optional[str] = None,
        db_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None
    ):
        """
        Initialize attribute builder.
        
        Parameters
        ----------
        payload_attrs : Dict[str, Any]
            Attributes from incoming API payload (building_attributes section).
        building_id : str, optional
            Building identifier for database lookup.
        db_fetcher : Callable, optional
            Function to fetch additional attributes by building_id.
        """
        self.payload_attrs = payload_attrs
        self.building_id = building_id
        self.db_fetcher = db_fetcher
        self.merged_attrs = {}
        
    def build(self) -> Dict[str, Any]:
        """
        Build complete attribute dictionary.
        
        Returns
        -------
        Dict[str, Any]
            Complete building attributes ready for CfgBuilding.
            
        Raises
        ------
        ValueError
            If required attributes missing or validation fails.
        """
        # Step 1: Merge sources (payload > db > defaults)
        self.merge_sources()

        # Step 2: Fetch a location-specific weather DataFrame (unless opted out)
        self.generate_weather_profile()

        # Step 3: Generate electricity profile (unless opted out)
        self.generate_electricity_profile()

        # Step 4: Align timeseries indices to weather year
        self.align_timeseries()

        # Step 5: Validate complete config
        issues = validate_cfg(self.merged_attrs)
        if issues:
            raise ValueError(f"Attribute validation failed: {'; '.join(issues)}")
        
        return self.merged_attrs
    
    def merge_sources(self):
        """Merge payload, database, and defaults with correct precedence."""
        # Start with defaults
        self.merged_attrs = {
            spec.name: spec.default 
            for spec in ATTRIBUTE_SPECS.values()
        }
        
        # Overlay database values (if available)
        if self.db_fetcher and self.building_id:
            try:
                db_attrs = self.db_fetcher(self.building_id) or {}
                self.merged_attrs.update(db_attrs)
            except Exception:
                pass  # Continue with defaults
        
        # Overlay payload (highest priority)
        self.merged_attrs.update(self.payload_attrs)
    
    def generate_weather_profile(self):
        """Fetch a location-specific weather DataFrame via the optional
        weather package, unless opted out. Falls back to whatever default
        is already in merged_attrs["weather"] (the bundled CSV, see
        cfg_attribute.py) if weather isn't installed or the fetch fails
        (e.g. no processed archive for this location/year/provider)."""
        if bool(self.merged_attrs.get("use_provided_weather", False)):
            return  # Keep the provided/merged weather DataFrame as-is

        if not weather_available():
            return  # Keep the bundled-CSV default already in merged_attrs["weather"]

        lat = float(self.merged_attrs.get("latitude", ATTRIBUTE_SPECS["latitude"].default))
        lon = float(self.merged_attrs.get("longitude", ATTRIBUTE_SPECS["longitude"].default))
        year = int(self.merged_attrs.get("year", ATTRIBUTE_SPECS["year"].default))
        provider = self.merged_attrs.get("weather_provider", ATTRIBUTE_SPECS["weather_provider"].default)

        try:
            self.merged_attrs["weather"] = get_or_fetch_weather(lat, lon, year, provider)
        except Exception as exc:
            warnings.warn(
                f"Dynamic weather fetch failed for (lat={lat}, lon={lon}, "
                f"year={year}, provider={provider!r}); falling back to "
                f"bundled default weather. ({exc})",
                stacklevel=2,
            )

    def generate_electricity_profile(self):
        """Generate Q_ig/elecLoad/occ_nothome/occ_sleeping via occupancy, unless opted out."""
        use_provided = bool(self.merged_attrs.get("use_provided_elecLoad", False))

        if use_provided:
            return  # Keep provided elecLoad (and any provided Q_ig/occ_nothome/occ_sleeping)

        # Extract weather to determine year
        weather_df = self.merged_attrs.get("weather", ATTRIBUTE_SPECS["weather"].default)
        if isinstance(weather_df, pd.DataFrame) and not weather_df.empty:
            weather_year = int(weather_df.index[0].year)
        else:
            weather_year = int(ATTRIBUTE_SPECS["year"].default)

        # Get generation parameters
        num_persons = int(self.merged_attrs.get("num_persons", ATTRIBUTE_SPECS["num_persons"].default))
        seed = self.merged_attrs.get("seed", ATTRIBUTE_SPECS["seed"].default)

        try:
            # Generate profile
            if not _OCCUPANCY_AVAILABLE:
                raise ImportError(
                    "occupancy package is required for electricity profile generation. "
                    "Install it with: pip install buem[occupancy]"
                )
            household = HouseholdProfile(num_persons=num_persons, year=weather_year, seed=seed)
            elec_gen = ElectricityConsumptionProfile(household, seed=seed)
            buem_inputs = to_buem_profiles(elec_gen.to_result())

            # Align index with weather (8760 hourly points)
            if isinstance(weather_df, pd.DataFrame) and not weather_df.empty:
                buem_inputs = {
                    key: series.reindex(weather_df.index, method='nearest', fill_value=0.0)
                    for key, series in buem_inputs.items()
                }

            self.merged_attrs["elecLoad"] = buem_inputs["elecLoad"]
            self.merged_attrs["Q_ig"] = buem_inputs["Q_ig"]
            self.merged_attrs["occ_nothome"] = buem_inputs["occ_nothome"]
            self.merged_attrs["occ_sleeping"] = buem_inputs["occ_sleeping"]
            self.merged_attrs["year"] = weather_year  # Force year consistency

        except Exception as exc:
            raise RuntimeError(f"Electricity profile generation failed: {exc}") from exc
    
    def align_timeseries(self):
        """Ensure all timeseries share weather data year/index."""
        weather_df = self.merged_attrs.get("weather")
        if not isinstance(weather_df, pd.DataFrame) or weather_df.empty:
            return
        
        weather_index = weather_df.index
        
        # Align elecLoad (already done in generate_electricity_profile, but verify)
        if "elecLoad" in self.merged_attrs and isinstance(self.merged_attrs["elecLoad"], pd.Series):
            if not self.merged_attrs["elecLoad"].index.equals(weather_index):
                self.merged_attrs["elecLoad"] = self.merged_attrs["elecLoad"].reindex(
                    weather_index, method='nearest', fill_value=0.0
                )
        
        # Align other profiles (Q_ig, occ_nothome, etc.) if needed
        for key in ("Q_ig", "occ_nothome", "occ_sleeping"):
            if key in self.merged_attrs and isinstance(self.merged_attrs[key], pd.Series):
                if not self.merged_attrs[key].index.equals(weather_index):
                    self.merged_attrs[key] = self.merged_attrs[key].reindex(
                        weather_index, method='nearest', fill_value=0.0
                    )