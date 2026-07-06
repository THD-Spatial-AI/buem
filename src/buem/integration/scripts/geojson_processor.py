"""
Process GeoJSON payloads: extract attributes, run thermal model, return results.
"""
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
import time
import uuid
import json
import gzip
import logging
import numpy as np
import pandas as pd
from flask import current_app

from buem.integration.scripts.attribute_builder import AttributeBuilder
from buem.integration.scripts.geojson_validator import (
    validate_geojson_request,
    create_validation_report,
    ValidationLevel
)
from buem.config.cfg_building import CfgBuilding
from buem.main import run_model
from buem.weather.from_merra import MerraWeatherData

logger = logging.getLogger(__name__)


class GeoJsonProcessor:
    """
    Process GeoJSON FeatureCollection with building energy model specifications.
    
    Workflow:
    1. Extract building attributes from GeoJSON feature
    2. Merge with database/defaults via AttributeBuilder
    3. Run thermal model (heating/cooling loads)
    4. Compute summary statistics
    5. Save timeseries .gz file (optional)
    6. Return results in GeoJSON format
    
    Parameters
    ----------
    payload : Dict[str, Any]
        GeoJSON FeatureCollection or single Feature.
    include_timeseries : bool, optional
        Save hourly timeseries to .gz file (default: False).
    db_fetcher : Callable, optional
        Function(building_id) -> Dict of additional attributes.
    result_save_dir : str or Path, optional
        Directory for saving .gz files (default: env BUEM_RESULTS_DIR).
    """
    
    def __init__(
        self,
        payload: Dict[str, Any],
        include_timeseries: bool = False,
        db_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        result_save_dir: Optional[str] = None,
    ):
        self.payload = payload
        self.include_timeseries = include_timeseries
        self.db_fetcher = db_fetcher
        
        # Result save directory
        if result_save_dir:
            self.result_save_dir = Path(result_save_dir)
        else:
            import os
            default_dir = Path(__file__).resolve().parents[1] / "results"
            self.result_save_dir = Path(os.environ.get("BUEM_RESULTS_DIR", str(default_dir)))
    
    def process(self) -> Dict[str, Any]:
        """
        Process all features and return GeoJSON FeatureCollection with results.
        
        Returns
        -------
        Dict[str, Any]
            GeoJSON FeatureCollection with thermal_load_profile added to each feature.
            
        Raises
        ------
        ValueError
            If payload validation fails with critical errors.
        """
        start_time = time.time()
        
        # Step 1: Validate payload structure and format
        validation_result = validate_geojson_request(self.payload)
        
        if not validation_result.is_valid:
            errors = validation_result.get_errors()
            error_msgs = [issue.message for issue in errors]
            validation_report = create_validation_report(validation_result)
            logger.error(f"Payload validation failed:\n{validation_report}")
            raise ValueError(f"Invalid GeoJSON payload: {'; '.join(error_msgs[:3])}")
        
        # Log validation warnings if any
        warnings = validation_result.get_warnings()
        if warnings:
            warning_msgs = [issue.message for issue in warnings]
            logger.warning(f"Validation warnings: {'; '.join(warning_msgs)}")
        
        # Use validated data (with any format conversions applied)
        validated_payload = validation_result.validated_data or self.payload
        
        # Extract features from validated payload
        if validated_payload.get("type") == "Feature":
            features = [validated_payload]
        elif validated_payload.get("type") == "FeatureCollection":
            features = validated_payload.get("features", [])
        else:
            raise ValueError("Validated payload has unexpected structure")
        
        # Process each feature
        out_features = []
        processing_errors = []
        
        for i, feat in enumerate(features):
            try:
                processed = self._process_single_feature(feat, validation_result)
                out_features.append(processed)
            except Exception as exc:
                error_msg = f"Feature {feat.get('id', f'index_{i}')} failed: {exc}"
                logger.exception(error_msg)
                processing_errors.append(error_msg)
                
                # Include error in feature response
                feat.setdefault("properties", {}).setdefault("buem", {})
                feat["properties"]["buem"]["error"] = {
                    "type": "processing_error",
                    "message": str(exc),
                    "feature_id": feat.get('id'),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                out_features.append(feat)
        
        # Build response with metadata
        response = {
            "type": "FeatureCollection",
            "features": out_features,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "processing_elapsed_s": round(time.time() - start_time, 3),
            "metadata": {
                "total_features": len(features),
                "successful_features": len(features) - len(processing_errors),
                "failed_features": len(processing_errors),
                "validation_warnings": len(warnings)
            }
        }
        
        # Include validation issues in response if any
        if warnings or processing_errors:
            response["validation_report"] = {
                "warnings": [{"path": w.path, "message": w.message} for w in warnings],
                "processing_errors": processing_errors
            }
        
        return response
    
    @staticmethod
    def _v3_to_internal(
        building: Optional[Dict[str, Any]],
        envelope: Optional[Dict[str, Any]],
        thermal: Optional[Dict[str, Any]],
        coords: list,
    ) -> Dict[str, Any]:
        """
        Transform v3 schema sections into the internal attribute dict expected by
        AttributeBuilder / CfgBuilding / ModelBUEM.

        v3 schema structure (as of corrected v3.0.0):
          - building: classification fields + nested envelope + nested thermal
          - envelope.elements[]: each element carries both geometry (area, azimuth,
            tilt) and its own thermal properties (U, g_gl, b_transmission,
            air_changes) — no separate element_properties list
          - thermal: building-wide parameters only (air change rates, comfort
            setpoints, shading factors, thermal mass)
          - parent_id on window/door elements references their parent wall id

        The internal format uses plain floats and a grouped components tree
        (Walls/Roof/Floor/Windows/Doors/Ventilation).
        """
        def scalar(obj, default=None):
            """Extract plain float from a measurement object or a bare number."""
            if isinstance(obj, dict) and "value" in obj:
                return float(obj["value"])
            if isinstance(obj, (int, float)):
                return float(obj)
            return default

        building = building or {}
        thermal = thermal or {}
        envelope = envelope or {}

        attrs: Dict[str, Any] = {}

        # --- Location: authoritative from geometry.coordinates [lon, lat, elev?] ---
        attrs["longitude"] = float(coords[0]) if len(coords) > 0 else 5.0
        attrs["latitude"] = float(coords[1]) if len(coords) > 1 else 52.0

        # --- building classification fields ---
        attrs["A_ref"] = scalar(building.get("A_ref"), 100.0)
        attrs["h_room"] = scalar(building.get("h_room"), 2.5)
        for k in ("n_storeys", "building_type", "construction_period", "country",
                  "attic_condition", "cellar_condition", "neighbour_status"):
            if k in building:
                attrs[k] = building[k]

        # --- building.thermal: building-wide thermal parameters ---
        attrs["n_air_infiltration"] = scalar(thermal.get("n_air_infiltration"), 0.5)
        attrs["n_air_use"] = scalar(thermal.get("n_air_use"), 0.5)
        attrs["c_m"] = scalar(thermal.get("c_m"), 165.0)
        attrs["thermalClass"] = thermal.get("thermal_class", "medium")
        attrs["comfortT_lb"] = scalar(thermal.get("comfortT_lb"), 21.0)
        attrs["comfortT_ub"] = scalar(thermal.get("comfortT_ub"), 24.0)
        attrs["design_T_min"] = scalar(thermal.get("design_T_min"), -12.0)
        attrs["F_sh_hor"] = scalar(thermal.get("F_sh_hor"), 0.80)
        attrs["F_sh_vert"] = scalar(thermal.get("F_sh_vert"), 0.75)
        attrs["F_f"] = scalar(thermal.get("F_f"), 0.20)
        attrs["F_w"] = scalar(thermal.get("F_w"), 1.0)

        # --- building.envelope: flat elements[] → internal components tree ---
        # Thermal properties (U, g_gl, b_transmission, air_changes) are now
        # defined directly on each element — no separate lookup table needed.
        TYPE_TO_COMP = {
            "wall": "Walls",
            "roof": "Roof",
            "floor": "Floor",
            "window": "Windows",
            "door": "Doors",
            "ventilation": "Ventilation",
        }

        components: Dict[str, Any] = {
            k: {"elements": []} for k in TYPE_TO_COMP.values()
        }
        # Track first b_transmission seen per component type (model reads it at component level)
        comp_b_trans: Dict[str, float] = {}

        for elem in envelope.get("elements", []):
            eid = elem.get("id", "")
            etype = elem.get("type", "")
            comp_key = TYPE_TO_COMP.get(etype)
            if not comp_key:
                continue

            if etype == "ventilation":
                internal_elem = {
                    "id": eid,
                    "area": 0.0,
                    "air_changes": scalar(elem.get("air_changes"), 0.5),
                }
                components["Ventilation"]["elements"].append(internal_elem)
                continue

            internal_elem: Dict[str, Any] = {
                "id": eid,
                "area": scalar(elem.get("area"), 0.0),
                "azimuth": scalar(elem.get("azimuth"), 0.0),
                "tilt": scalar(elem.get("tilt"), 90.0),
            }
            if "parent_id" in elem:
                internal_elem["parent_id"] = elem["parent_id"]

            # Per-element thermal properties — read directly from the element
            if "U" in elem:
                internal_elem["U"] = scalar(elem["U"])

            if "g_gl" in elem:
                internal_elem["g_gl"] = scalar(elem["g_gl"])

            # b_transmission: record first value per component type
            if "b_transmission" in elem and comp_key not in comp_b_trans:
                comp_b_trans[comp_key] = scalar(elem["b_transmission"], 1.0)

            components[comp_key]["elements"].append(internal_elem)

        # Attach component-level b_transmission where found
        for comp_key, b_val in comp_b_trans.items():
            components[comp_key]["b_transmission"] = b_val

        # Compute area-weighted average U per component and set it at component level.
        # The model reads bU[comp] (a single float) for opaque solar absorption calculations
        # (model_buem._init5R1C), so a component-level U is always required.
        for comp_key, comp_data in components.items():
            if comp_key == "Ventilation":
                continue
            elems = comp_data["elements"]
            u_values = [(e["U"], e["area"]) for e in elems if "U" in e and e["area"] > 0]
            if u_values:
                total_area = sum(a for _, a in u_values)
                weighted_u = sum(u * a for u, a in u_values) / total_area if total_area > 0 else u_values[0][0]
                comp_data["U"] = round(weighted_u, 4)

        attrs["components"] = components
        return attrs

    def _process_single_feature(self, feature: Dict[str, Any], validation_result) -> Dict[str, Any]:
        """
        Process single GeoJSON feature: build attributes, run model, add results.

        Parameters
        ----------
        feature : Dict[str, Any]
            GeoJSON v3 Feature with properties.buem.building.{envelope,thermal} and
            properties.buem.solver.
        validation_result : ValidationResult
            Validation result from input validation.

        Returns
        -------
        Dict[str, Any]
            Feature with added thermal_load_profile and model_metadata in properties.buem.
        """
        props = feature.setdefault("properties", {})
        buem = props.setdefault("buem", {})
        building_id = feature.get("id")

        logger.info(f"Processing feature {building_id}")

        # Extract location from geometry.coordinates [lon, lat, elev?]
        coords = feature.get("geometry", {}).get("coordinates", [5.0, 52.0])

        # v3 schema: envelope and thermal are nested inside building
        building = buem.get("building", {})

        # Transform v3 schema into internal attribute dict
        internal_attrs = self._v3_to_internal(
            building=building,
            envelope=building.get("envelope"),
            thermal=building.get("thermal"),
            coords=coords,
        )

        # Inject location-specific MERRA-2 weather when available.
        # This overrides the module-level default weather with data matched to
        # the actual building location and simulation year.
        feature_weather = self._load_feature_weather(
            lat=internal_attrs.get("latitude"),
            lon=internal_attrs.get("longitude"),
            start_time=props.get("start_time"),
        )
        if feature_weather is not None:
            internal_attrs["weather"] = feature_weather

        # Build complete attributes (merge with defaults + optional DB lookup)
        builder = AttributeBuilder(
            payload_attrs=internal_attrs,
            building_id=building_id,
            db_fetcher=self.db_fetcher,
        )
        merged_attrs = builder.build()

        # Convert to model config
        cfg = CfgBuilding(merged_attrs).to_cfg_dict()

        # Solver flags from buem.solver
        solver = buem.get("solver", {})
        use_milp = bool(solver.get("use_milp", False))
        parallel_thermal = bool(solver.get("parallel_thermal", True))
        use_chunked_processing = bool(solver.get("use_chunked_processing", True))

        start = time.time()
        res = run_model(cfg, plot=False, use_milp=use_milp)
        elapsed = time.time() - start

        # Extract results
        times = res.get("times", [])
        heating = self._validate_array(res.get("heating", []), "heating")
        cooling = self._validate_array(res.get("cooling", []), "cooling")

        if "electricity" in res:
            electricity = self._validate_array(res["electricity"], "electricity")
        else:
            elec_cfg = cfg.get("elecLoad")
            if isinstance(elec_cfg, pd.Series):
                electricity = self._validate_array(elec_cfg.values, "electricity")
            else:
                electricity = self._validate_array(elec_cfg or [], "electricity")

        # Build thermal load profile (summary ± timeseries)
        a_ref = internal_attrs.get("A_ref", 100.0)
        profile = self._build_thermal_load_profile(
            times, heating, cooling, electricity, elapsed,
            props.get("start_time"), props.get("end_time"),
            props.get("resolution", "60"), props.get("resolution_unit", "minutes"),
            a_ref=a_ref,
        )

        # Save timeseries .gz file if requested
        if self.include_timeseries and len(times):
            try:
                fname = self._save_timeseries(times, heating, cooling, electricity)
                profile["timeseries_file"] = f"/api/files/{fname}"
            except Exception as exc:
                logger.exception(f"Timeseries save failed for {building_id}: {exc}")

        # Determine weather year from cfg
        weather_df = cfg.get("weather", pd.DataFrame())
        weather_year = 2018
        if hasattr(weather_df, "index") and hasattr(weather_df.index, "year") and len(weather_df.index):
            weather_year = int(weather_df.index[0].year)

        # Attach results — thermal_load_profile and model_metadata are siblings under buem
        buem["thermal_load_profile"] = profile
        buem["model_metadata"] = {
            "model_version": "BUEM-v2.0",
            "solver_used": "MILP" if use_milp else "scipy-sparse",
            "processing_time": {"value": round(elapsed, 3), "unit": "s"},
            "weather_year": weather_year,
            "parallel_thermal": parallel_thermal,
            "use_chunked_processing": use_chunked_processing,
            "validation_warnings": [w.message for w in validation_result.get_warnings()],
        }

        logger.info(f"Successfully processed feature {building_id} in {elapsed:.2f}s")
        return feature
    
    @staticmethod
    def _load_feature_weather(
        lat: Optional[float],
        lon: Optional[float],
        start_time: Optional[str],
    ) -> Optional[pd.DataFrame]:
        """Load MERRA-2 weather for the feature's location and year.

        Returns None when BUEM_WEATHER_DIR is not set, no matching NetCDF file
        exists, or required packages are unavailable — allowing the caller to
        fall back to the module-level default weather.

        Parameters
        ----------
        lat, lon : float or None
            Building coordinates in decimal degrees.
        start_time : str or None
            ISO 8601 timestamp string; the year is used to select the MERRA-2 file.

        Returns
        -------
        pd.DataFrame or None
            Hourly DataFrame with columns T, GHI, DNI, DHI, or None on failure.
        """
        import os

        weather_dir = os.environ.get("BUEM_WEATHER_DIR")
        if not weather_dir:
            return None

        if lat is None or lon is None:
            return None

        # Determine simulation year from start_time; default to 2018
        year = 2018
        if start_time:
            try:
                year = int(str(start_time)[:4])
            except (ValueError, IndexError):
                pass

        try:
            loader = MerraWeatherData(weather_dir, lat=lat, lon=lon)
            return loader.get_weather_df(year=year)
        except FileNotFoundError:
            logger.warning(
                "No MERRA-2 file for year %d in %s; using default weather.", year, weather_dir
            )
            return None
        except Exception as exc:
            logger.warning("MERRA-2 weather load failed (%s); using default weather.", exc)
            return None

    def _validate_array(self, data, array_name: str) -> np.ndarray:
        """
        Validate and sanitize numerical arrays for thermal loads.
        
        Parameters
        ----------
        data : Any
            Input data to be converted to array.
        array_name : str
            Name of the array for logging.
            
        Returns
        -------
        np.ndarray
            Validated and sanitized array.
        """
        try:
            arr = np.asarray(data, dtype=float)
            
            # Sanitize NaN/inf
            arr = np.nan_to_num(arr, nan=0.0, posinf=1e9, neginf=-1e9)
            
            # Check for remaining NaN
            nan_count = np.isnan(arr).sum()
            if nan_count > 0:
                logger.warning(f"Array {array_name}: {nan_count}/{arr.size} NaN values replaced with 0")
                arr = np.nan_to_num(arr, nan=0.0)
            
            return arr
            
        except Exception as e:
            logger.error(f"Failed to validate array {array_name}: {e}")
            return np.array([], dtype=float)
    
    def _build_thermal_load_profile(
        self, times, heating, cooling, electricity, elapsed,
        start_time, end_time, resolution, resolution_unit,
        a_ref: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Build thermal load profile matching the v3 response schema.

        All summary quantities are emitted as {value, unit} measurement objects.
        timeseries arrays use plain lists under a shared unit key.

        Parameters
        ----------
        times : pd.DatetimeIndex or list
            Timestamps for the simulation.
        heating, cooling, electricity : np.ndarray
            Load arrays in kW.
        elapsed : float
            Processing time in seconds.
        start_time, end_time : str
            Time range strings from request (used as fallback).
        resolution, resolution_unit : str
            Time resolution specification.
        a_ref : float
            Reference floor area in m² (for energy intensity calculation).

        Returns
        -------
        Dict[str, Any]
            Thermal load profile matching v3 response schema.
        """
        # Resolve time bounds
        has_times = False
        if isinstance(times, pd.DatetimeIndex) and not times.empty:
            has_times = True
            start_iso = times[0].isoformat()
            end_iso = times[-1].isoformat()
        elif times is not None and len(times) > 0:
            has_times = True
            start_iso = times[0].isoformat() if hasattr(times[0], "isoformat") else str(times[0])
            end_iso = times[-1].isoformat() if hasattr(times[-1], "isoformat") else str(times[-1])
        else:
            start_iso = start_time or "2018-01-01T00:00:00Z"
            end_iso = end_time or "2018-12-31T23:00:00Z"

        def energy_summary(arr: np.ndarray) -> Dict[str, Any]:
            """Build an energy_summary object with {value, unit} measurement fields."""
            if len(arr) == 0:
                zero_kwh = {"value": 0.0, "unit": "kWh"}
                zero_kw = {"value": 0.0, "unit": "kW"}
                return {"total": zero_kwh, "max": zero_kw, "min": zero_kw,
                        "mean": zero_kw, "median": zero_kw, "std": zero_kw}
            return {
                "total":  {"value": round(float(np.sum(arr)),    3), "unit": "kWh"},
                "max":    {"value": round(float(np.max(arr)),    3), "unit": "kW"},
                "min":    {"value": round(float(np.min(arr)),    3), "unit": "kW"},
                "mean":   {"value": round(float(np.mean(arr)),   3), "unit": "kW"},
                "median": {"value": round(float(np.median(arr)), 3), "unit": "kW"},
                "std":    {"value": round(float(np.std(arr)),    3), "unit": "kW"},
            }

        heating_summary = energy_summary(heating)
        cooling_summary = energy_summary(np.abs(cooling))
        elec_summary = energy_summary(electricity)

        total_energy_kwh = (
            heating_summary["total"]["value"]
            + cooling_summary["total"]["value"]
            + elec_summary["total"]["value"]
        )
        energy_intensity_kwh_m2 = round(total_energy_kwh / a_ref, 3) if a_ref > 0 else 0.0

        profile: Dict[str, Any] = {
            "start_time": start_iso,
            "end_time": end_iso,
            "resolution": resolution,
            "resolution_unit": resolution_unit,
            "summary": {
                "heating": heating_summary,
                "cooling": cooling_summary,
                "electricity": elec_summary,
                "total_energy_demand":  {"value": round(total_energy_kwh, 3), "unit": "kWh"},
                "peak_heating_load":    {"value": heating_summary["max"]["value"], "unit": "kW"},
                "peak_cooling_load":    {"value": cooling_summary["max"]["value"], "unit": "kW"},
                "energy_intensity":     {"value": energy_intensity_kwh_m2, "unit": "kWh/m2"},
            },
        }

        if self.include_timeseries and has_times:
            profile["timeseries"] = {
                "unit": "kW",
                "timestamps": (
                    [t.isoformat() for t in times]
                    if isinstance(times, pd.DatetimeIndex)
                    else [str(t) for t in times]
                ),
                "heating":     heating.tolist(),
                "cooling":     cooling.tolist(),
                "electricity": electricity.tolist(),
            }

        return profile
    
    def _save_timeseries(self, times, heating, cooling, electricity) -> str:
        """
        Save timeseries as gzipped JSON.
        
        Returns
        -------
        str
            Filename (e.g., 'buem_ts_abc123.json.gz').
        """
        self.result_save_dir.mkdir(parents=True, exist_ok=True)
        fname = f"buem_ts_{uuid.uuid4().hex}.json.gz"
        full_path = self.result_save_dir / fname

        # Convert times to list of ISO strings (handles DatetimeIndex or list)
        if isinstance(times, pd.DatetimeIndex):
            time_list = [t.isoformat() for t in times]
        else:
            time_list = [t.isoformat() for t in times]       

        payload = {
            "index": time_list,
            "heat": [float(x) for x in heating.tolist()],
            "cool": [float(x) for x in cooling.tolist()],
            "electricity": [float(x) for x in electricity.tolist()] if len(electricity) else [],
        }
        
        with gzip.open(full_path, "wt", encoding="utf-8") as gz:
            json.dump(payload, gz, indent=None)
        
        logger.info(f"Saved timeseries: {full_path}")
        return fname