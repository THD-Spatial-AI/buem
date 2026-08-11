"""
Build complete building attributes by merging payload, database, and defaults.
Generate weather and electricity profiles, and align timeseries indices.
"""
import logging
from collections.abc import Callable
from typing import Any

import pandas as pd

from buem.config.cfg_attribute import (
    ATTRIBUTE_SPECS,
    DEFAULT_ARCHETYPE_BY_BUILDING_TYPE,
    RESIDENTIAL_BUILDING_TYPES,
)
from buem.config.validator import validate_cfg
from buem.config.weather_cache import get_or_fetch_weather

# occupancy (https://github.com/UU-BUEM/occupancy) is compulsory (2026-08-07),
# same treatment as weather -- imported unconditionally like pandas/pvlib.
from occupancy import (  # type: ignore[import]
    ElectricityConsumptionProfile,
    HouseholdProfile,
    ServiceBuildingProfile,
    to_buem_profiles,
)

logger = logging.getLogger(__name__)


def _reindex_or_raise(series: pd.Series, target_index: pd.DatetimeIndex, name: str) -> pd.Series:
    """Reindex a profile onto the weather index without silently zero-filling
    gaps -- a real misalignment (e.g. a year/timezone mismatch between the
    occupancy profile and weather) should surface as an error, not a
    plausible-looking zero internal-gains/electricity result for those hours.

    ``method="nearest"`` alone would happily match e.g. a 2019 profile onto a
    2018 index (nearest always finds *some* label), which is exactly the
    silent-wrong-data failure mode this guards against -- a ``tolerance`` is
    required so a genuinely out-of-range timestamp reindexes to NaN instead.
    Half an hour assumes this repo's consistently-hourly resolution.
    """
    aligned = series.reindex(target_index, method="nearest", tolerance=pd.Timedelta(minutes=30))
    if aligned.isna().any():
        n_missing = int(aligned.isna().sum())
        raise ValueError(
            f"{name} could not be aligned to the weather timeseries at "
            f"{n_missing} of {len(target_index)} timestep(s) -- refusing to "
            "silently zero-fill. Check that the occupancy profile covers the "
            "same year/timezone as the weather data."
        )
    return aligned

# Attributes that identify *which building* is being modeled -- there is no
# safe generic default for these (unlike thermal-class-type assumptions), so
# they must be explicitly supplied via payload_attrs or db_fetcher rather than
# silently falling back to ATTRIBUTE_SPECS' generic example-house defaults.
REQUIRED_FROM_CALLER: tuple[str, ...] = ("latitude", "longitude", "components", "A_ref")


class AttributeBuilder:
    """
    Merge building attributes from multiple sources and generate derived profiles.

    Precedence: payload > database > defaults (cfg_attribute.py)
    """

    def __init__(
        self,
        payload_attrs: dict[str, Any],
        building_id: str | None = None,
        db_fetcher: Callable[[str], dict[str, Any]] | None = None,
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
        self.merged_attrs: dict[str, Any] = {}
        self._provided_keys: set[str] = set()

    def build(self) -> dict[str, Any]:
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

        # Step 2: Refuse to silently model the generic example house in place
        # of a real building the caller forgot to fully specify.
        missing_required = [k for k in REQUIRED_FROM_CALLER if k not in self._provided_keys]
        if missing_required:
            raise ValueError(
                f"Missing required building attributes (not supplied via payload "
                f"or database): {missing_required}. These identify the specific "
                "building being modeled and are not safe to default silently."
            )

        # Step 3: Fetch a location-specific weather DataFrame (unless opted out)
        self.generate_weather_profile()

        # Step 4: Generate electricity profile (unless opted out)
        self.generate_electricity_profile()

        # Step 5: Align timeseries indices to weather year
        self.align_timeseries()

        # Step 6: Validate complete config
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
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                # A db_fetcher was explicitly wired for a specific building_id --
                # if it fails, that building's real data is missing. Silently
                # continuing with the generic example-house defaults would model
                # the wrong building without any signal that anything went
                # wrong, so raise instead.
                raise RuntimeError(
                    f"db_fetcher failed for building_id={self.building_id!r}; "
                    "refusing to silently continue with generic building "
                    "defaults for a specific building lookup."
                ) from exc
            self.merged_attrs.update(db_attrs)
            self._provided_keys.update(db_attrs.keys())

        # Overlay payload (highest priority)
        self.merged_attrs.update(self.payload_attrs)
        self._provided_keys.update(self.payload_attrs.keys())
    
    def generate_weather_profile(self):
        """Fetch a location-specific weather DataFrame via the (compulsory)
        weather package, unless opted out. A fetch that fails for the
        requested location/year (no processed archive, bad response, etc.)
        always raises -- there is no fallback, since substituting any other
        location's weather (real or not) would silently model the wrong
        building."""
        if bool(self.merged_attrs.get("use_provided_weather", False)):
            return  # Keep the provided/merged weather DataFrame as-is

        lat = float(self.merged_attrs.get("latitude", ATTRIBUTE_SPECS["latitude"].default))
        lon = float(self.merged_attrs.get("longitude", ATTRIBUTE_SPECS["longitude"].default))
        year = int(self.merged_attrs.get("year", ATTRIBUTE_SPECS["year"].default))
        provider = self.merged_attrs.get("weather_provider", ATTRIBUTE_SPECS["weather_provider"].default)

        try:
            self.merged_attrs["weather"] = get_or_fetch_weather(lat, lon, year, provider)
        except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
            raise RuntimeError(
                f"Weather fetch failed for the requested building location "
                f"(lat={lat}, lon={lon}, year={year}, provider={provider!r})."
            ) from exc

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
        building_type = self.merged_attrs.get("building_type", ATTRIBUTE_SPECS["building_type"].default)
        seed = self.merged_attrs.get("seed", ATTRIBUTE_SPECS["seed"].default)

        try:
            # floor_area_m2 for occupancy's area-normalized gain component
            # (occupancy_gains_handoff.md Gap 1) -- residential only stays
            # None: household archetypes deliberately carry no gain_w_per_m2
            # (occupancy's own CHANGELOG), so passing a floor area there
            # would just raise. Non-residential resolves it below.
            floor_area_m2: float | None = None

            if building_type in RESIDENTIAL_BUILDING_TYPES:
                num_persons = int(self.merged_attrs.get("num_persons", ATTRIBUTE_SPECS["num_persons"].default))
                # Archetype: explicit caller value wins; otherwise a first-pass
                # building_type-based default (see DEFAULT_ARCHETYPE_BY_BUILDING_TYPE's
                # docstring in cfg_attribute.py for the caveats), falling back to
                # occupancy's own "generic" for anything unmapped.
                archetype = self.merged_attrs.get("archetype") or DEFAULT_ARCHETYPE_BY_BUILDING_TYPE.get(
                    building_type, "generic"
                )
                household = HouseholdProfile(num_persons=num_persons, year=weather_year, seed=seed, archetype=archetype)
                elec_gen = ElectricityConsumptionProfile(household, seed=seed)
                result = elec_gen.to_result()
            else:
                # Non-residential: route through occupancy's ServiceBuildingProfile
                # instead of forcing every building through HouseholdProfile.
                capacity_raw = self.merged_attrs.get("capacity", ATTRIBUTE_SPECS["capacity"].default)
                # Explicit cast (mirrors num_persons above) -- a string capacity from
                # a JSON payload would otherwise reach ServiceBuildingProfile's
                # `self.capacity <= 0` check and raise an unrelated-looking TypeError
                # instead of a clear int-conversion error here.
                capacity = int(capacity_raw) if capacity_raw is not None else None
                try:
                    service = ServiceBuildingProfile(
                        building_type=building_type,
                        year=weather_year,
                        capacity=capacity,
                        seed=seed,
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"building_type {building_type!r} is neither a residential TABULA "
                        f"code ({sorted(RESIDENTIAL_BUILDING_TYPES)}) nor a registered "
                        "occupancy service-building type."
                    ) from exc
                result = service.to_result()
                # A_ref is in REQUIRED_FROM_CALLER, so merged_attrs always has a
                # real value here -- but it may still be the flat 100.0
                # placeholder `_convert_v3_to_v2` substitutes when a v3 client
                # omits A_ref (see .claude/open.md's "A_ref fallback" bug note),
                # not the true geometry-derived floor area CfgBuilding computes
                # afterwards. All 8 service-building types now carry a
                # gain_w_per_m2 (occupancy CHANGELOG [Unreleased]), so this is
                # safe to pass unconditionally for the service-building branch.
                floor_area_m2 = float(self.merged_attrs.get("A_ref", ATTRIBUTE_SPECS["A_ref"].default))

            buem_inputs = to_buem_profiles(result, floor_area_m2=floor_area_m2)

            # Align index with weather (8760 hourly points)
            if isinstance(weather_df, pd.DataFrame) and not weather_df.empty:
                buem_inputs = {
                    key: _reindex_or_raise(series, weather_df.index, key)
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
        if (
            "elecLoad" in self.merged_attrs
            and isinstance(self.merged_attrs["elecLoad"], pd.Series)
            and not self.merged_attrs["elecLoad"].index.equals(weather_index)
        ):
            self.merged_attrs["elecLoad"] = _reindex_or_raise(
                self.merged_attrs["elecLoad"], weather_index, "elecLoad"
            )

        # Align other profiles (Q_ig, occ_nothome, etc.) if needed
        for key in ("Q_ig", "occ_nothome", "occ_sleeping"):
            if (
                key in self.merged_attrs
                and isinstance(self.merged_attrs[key], pd.Series)
                and not self.merged_attrs[key].index.equals(weather_index)
            ):
                self.merged_attrs[key] = _reindex_or_raise(self.merged_attrs[key], weather_index, key)