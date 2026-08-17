"""
Build complete building attributes by merging payload, database, and defaults.
Generate weather and electricity profiles, and align timeseries indices.
"""
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pandas as pd

# occupancy (https://github.com/UU-BUEM/occupancy) is compulsory (2026-08-07),
# same treatment as weather -- imported unconditionally like pandas/pvlib.
from occupancy import (  # type: ignore[import]
    ElectricityConsumptionProfile,
    HouseholdProfile,
    ServiceBuildingProfile,
    to_buem_profiles,
)

from buem.config.cfg_attribute import (
    ATTRIBUTE_SPECS,
    DEFAULT_ARCHETYPE_BY_BUILDING_TYPE,
    HOUSEHOLD_EQUIPMENT_TYPES,
    RESIDENTIAL_BUILDING_TYPES,
)
from buem.config.validator import validate_cfg
from buem.config.weather_cache import get_or_fetch_weather

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

def _resolve_equipment_table(
    household: HouseholdProfile, seed: int | None, equipment_spec: Any
) -> dict[str, Any] | None:
    """Build a filtered occupancy equipment table from the optional
    ``equipment`` attribute: a per-item boolean map, e.g.
    ``{"washing_machine": True, "oven": False}``.

    ``True`` forces that item to be treated as owned -- sets its
    ``ownership_probability`` to 1.0, guaranteeing inclusion rather than
    just making it more likely (occupancy still gates on ``probability >=
    1.0`` in ``_owned_by_name()``, confirmed against occupancy's real
    source). ``False`` omits the item from the returned table entirely,
    guaranteeing exclusion regardless of ``enabled``/``ownership_probability``
    (an item absent from the dict never reaches
    ``ElectricityConsumptionProfile.generate()``'s iteration at all). An id
    not mentioned in ``equipment_spec`` is left exactly as occupancy's own
    default produces it for this household.

    Deliberately reads the *archetype-adjusted* base table via a throwaway
    ``ElectricityConsumptionProfile(household, seed=seed)
    .get_equipment_table()`` (a real public method) rather than the raw
    ``occupancy.households.electricity.default_equipment_table()`` --
    ``ElectricityConsumptionProfile.__post_init__`` applies the household's
    ``archetype.equipment_overrides`` on top of the raw default table, and
    reaching for the raw table directly would silently lose that per-archetype
    tuning for every unmentioned item.

    Returns ``None`` (occupancy's own default equipment set, unchanged) when
    no selector is supplied. Raises ``ValueError`` for a malformed selector
    or an unrecognized/non-boolean item value, naming the offending value(s),
    rather than failing inside occupancy with a less legible error.
    """
    if not equipment_spec:
        return None
    if not isinstance(equipment_spec, dict):
        # ValueError deliberately, matching the other two malformed-input
        # branches below (unrecognized id / non-bool value) -- a consistent
        # exception type across all three lets callers catch one type for
        # "malformed equipment input", not three. TRY004 would suggest
        # TypeError here; tests/test_equipment_selection.py::
        # test_resolve_equipment_table_non_dict_raises asserts ValueError.
        raise ValueError(  # noqa: TRY004
            "equipment must be a dict of {equipment_id: bool}, "
            f"got {type(equipment_spec).__name__}."
        )
    unknown = sorted(set(equipment_spec) - HOUSEHOLD_EQUIPMENT_TYPES)
    if unknown:
        raise ValueError(
            f"equipment contains unrecognized id(s) {unknown} -- expected "
            f"a subset of {sorted(HOUSEHOLD_EQUIPMENT_TYPES)}."
        )
    non_bool = {k: v for k, v in equipment_spec.items() if not isinstance(v, bool)}
    if non_bool:
        raise ValueError(f"equipment values must be true/false, got {non_bool!r}.")

    base_table = ElectricityConsumptionProfile(household, seed=seed).get_equipment_table()
    result: dict[str, Any] = {}
    for key, spec in base_table.items():
        if key not in equipment_spec:
            result[key] = spec
            continue
        if equipment_spec[key]:
            result[key] = replace(spec, ownership_probability=1.0)
        # False -> forced exclusion: simply omit from the returned table.
    return result


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
        """Generate Q_ig/elecLoad/occ_nothome/occ_sleeping via occupancy.

        elecLoad can be overridden with a caller-supplied series
        (use_provided_elecLoad) -- Q_ig/occ_nothome/occ_sleeping still come
        from a real occupancy generation in that case, via
        occupancy.to_buem_profiles(elec_load=...); this no longer skips
        calling occupancy entirely (pre-2026-08-14 behavior, which also lost
        Q_ig/occ_nothome/occ_sleeping). Household equipment can optionally be
        filtered via the "equipment" attribute (residential building_type
        only).
        """
        use_provided_elec = bool(self.merged_attrs.get("use_provided_elecLoad", False))
        provided_elec_load: pd.Series | None = None
        if use_provided_elec:
            # Captured before generation below overwrites merged_attrs["elecLoad"].
            provided_elec_load = self.merged_attrs.get("elecLoad")
            if not isinstance(provided_elec_load, pd.Series):
                raise ValueError(
                    "use_provided_elecLoad=True requires elecLoad to be a "
                    f"pandas Series; got {type(provided_elec_load).__name__}."
                )

        # Extract weather to determine year
        weather_df = self.merged_attrs.get("weather", ATTRIBUTE_SPECS["weather"].default)
        if isinstance(weather_df, pd.DataFrame) and not weather_df.empty:
            weather_year = int(weather_df.index[0].year)
        else:
            weather_year = int(ATTRIBUTE_SPECS["year"].default)

        # Get generation parameters
        building_type = self.merged_attrs.get("building_type", ATTRIBUTE_SPECS["building_type"].default)
        seed = self.merged_attrs.get("seed", ATTRIBUTE_SPECS["seed"].default)
        equipment_spec = self.merged_attrs.get("equipment", ATTRIBUTE_SPECS["equipment"].default)

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
                equipment_table = _resolve_equipment_table(household, seed, equipment_spec)
                elec_gen = ElectricityConsumptionProfile(household, equipment=equipment_table, seed=seed)
                result = elec_gen.to_result()
            else:
                # Non-residential: route through occupancy's ServiceBuildingProfile
                # instead of forcing every building through HouseholdProfile.
                # ServiceBuildingProfile has no per-item equipment selection yet
                # (see .claude/occupancy_module_activities.md) -- a supplied
                # equipment selector is a no-op here, not an error.
                if equipment_spec:
                    logger.warning(
                        "equipment inclusion/exclusion was supplied for "
                        "service-building building_type %r, but "
                        "occupancy.ServiceBuildingProfile has no per-item "
                        "equipment selection yet -- ignoring (see "
                        ".claude/occupancy_module_activities.md).",
                        building_type,
                    )
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

            if provided_elec_load is not None:
                # occupancy's own result.profile.index is on-the-hour
                # (00:00, 01:00, ...), while a caller-supplied series aligned
                # to buem's weather index is typically half-hour-offset
                # (00:30, 01:30, ... -- interval-midpoint timestamps). to_buem_
                # profiles()'s internal elec_load reindex is exact-match only,
                # so realign here first with the same nearest+tolerance
                # approach already used to align buem_inputs onto weather_df
                # below, rather than have a realistically-timestamped caller
                # series fail with a confusing "does not cover the index"
                # error from inside occupancy.
                provided_elec_load = _reindex_or_raise(
                    provided_elec_load, result.profile.index, "elecLoad"
                )

            buem_inputs = to_buem_profiles(
                result, floor_area_m2=floor_area_m2, elec_load=provided_elec_load
            )

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