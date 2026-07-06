"""
Build complete building attributes by merging payload, database, and defaults.
Generate electricity profile and align timeseries indices.
"""
from typing import Dict, Any, Optional, Callable
import pandas as pd

from buem.config.cfg_attribute import ATTRIBUTE_SPECS
from buem.config.validator import validate_cfg

# occupancy is an optional independent package (https://github.com/UU-BUEM/occupancy),
# not published to PyPI. Install with:
# pip install git+https://github.com/UU-BUEM/occupancy.git
try:
    from occupancy.internal_gains.occupancy_profile import OccupancyProfile  # type: ignore[import]
    from occupancy.electricity.electricity_consumption import ElectricityConsumptionProfile  # type: ignore[import]
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
        
        # Step 2: Generate electricity profile (unless opted out)
        self.generate_electricity_profile()
        
        # Step 3: Align timeseries indices to weather year
        self.align_timeseries()
        
        # Step 4: Validate complete config
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
    
    def generate_electricity_profile(self):
        """Generate electricity consumption profile unless explicitly opted out."""
        use_provided = bool(self.merged_attrs.get("use_provided_elecLoad", False))
        
        if use_provided:
            return  # Keep provided elecLoad
        
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
                    "Install it with: pip install git+https://github.com/UU-BUEM/occupancy.git"
                )
            occ = OccupancyProfile(num_persons=num_persons, year=weather_year, seed=seed)
            elec_gen = ElectricityConsumptionProfile(occ, seed=seed)
            profile_df = elec_gen.generate()

            if "total_power_kwh" not in profile_df:
                raise ValueError("ElectricityConsumptionProfile missing 'total_power_kwh' column")

            elec_series = profile_df["total_power_kwh"]
            
            # Align index with weather (8760 hourly points)
            if isinstance(weather_df, pd.DataFrame) and not weather_df.empty:
                elec_series = elec_series.reindex(weather_df.index, method='nearest', fill_value=0.0)
            
            self.merged_attrs["elecLoad"] = elec_series
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