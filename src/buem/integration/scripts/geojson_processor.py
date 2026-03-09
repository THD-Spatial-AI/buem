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
    
    def _process_single_feature(self, feature: Dict[str, Any], validation_result) -> Dict[str, Any]:
        """
        Process single GeoJSON feature: build attributes, run model, add results.
        
        Parameters
        ----------
        feature : Dict[str, Any]
            GeoJSON Feature with properties.buem.building_attributes.
        validation_result : ValidationResult
            Validation result from input validation.
        
        Returns
        -------
        Dict[str, Any]
            Feature with added thermal_load_profile in properties.buem.
        """
        props = feature.setdefault("properties", {})
        buem = props.setdefault("buem", {})
        building_id = feature.get("id")
        payload_attrs = buem.get("building_attributes", {})
        
        # Log feature processing start
        logger.info(f"Processing feature {building_id}")
        
        # Build complete attributes
        builder = AttributeBuilder(
            payload_attrs=payload_attrs,
            building_id=building_id,
            db_fetcher=self.db_fetcher
        )
        merged_attrs = builder.build()
        
        # Convert to model config
        cfg = CfgBuilding(merged_attrs).to_cfg_dict()
        
        # Run thermal model with parallel thermal calculations and chunked processing for maximum performance
        use_milp = bool(buem.get("use_milp", False))
        parallel_thermal = bool(buem.get("parallel_thermal", True))  # Default to True for better performance
        use_chunked_processing = bool(buem.get("use_chunked_processing", True))  # Enable chunked processing for multi-core optimization
        start = time.time()
        res = run_model(cfg, plot=False, use_milp=use_milp, parallel_thermal=parallel_thermal, use_chunked_processing=use_chunked_processing)
        elapsed = time.time() - start
        
        # Extract results with validation
        times = res.get("times", [])
        heating = self._validate_array(res.get("heating", []), "heating")
        cooling = self._validate_array(res.get("cooling", []), "cooling")
        
        # Electricity: prefer model output, else use cfg elecLoad
        if "electricity" in res:
            electricity = self._validate_array(res["electricity"], "electricity")
        else:
            elec_cfg = cfg.get("elecLoad")
            if isinstance(elec_cfg, pd.Series):
                electricity = self._validate_array(elec_cfg.values, "electricity")
            else:
                electricity = self._validate_array(elec_cfg or [], "electricity")
        
        # Build comprehensive thermal load profile
        profile = self._build_thermal_load_profile(
            times, heating, cooling, electricity, elapsed, 
            props.get("start_time"), props.get("end_time"),
            props.get("resolution", "60"), props.get("resolution_unit", "minutes")
        )
        
        # Add model metadata
        profile["model_metadata"] = {
            "model_version": "BUEM-v2.0",
            "solver_used": "MILP" if use_milp else "Parameterization",
            "parallel_thermal": parallel_thermal,
            "use_chunked_processing": use_chunked_processing,
            "processing_time_s": round(elapsed, 3),
            "weather_year": int(getattr(cfg.get("weather", pd.DataFrame()).index, "year", [2018])[0]) if hasattr(cfg.get("weather", pd.DataFrame()).index, "year") else 2018,
            "validation_warnings": [w.message for w in validation_result.get_warnings()]
        }
        
        # Save timeseries if requested
        if self.include_timeseries and len(times):
            try:
                fname = self._save_timeseries(times, heating, cooling, electricity)
                profile["timeseries_file"] = f"/api/files/{fname}"
            except Exception as exc:
                logger.exception(f"Timeseries save failed for {building_id}: {exc}")
        
        # Attach results
        buem["thermal_load_profile"] = profile
        
        logger.info(f"Successfully processed feature {building_id} in {elapsed:.2f}s")
        
        return feature
    
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
        start_time, end_time, resolution, resolution_unit
    ) -> Dict[str, Any]:
        """
        Build comprehensive thermal load profile matching response schema.
        
        Parameters
        ----------
        times : pd.DatetimeIndex or list
            Timestamps for the simulation.
        heating, cooling, electricity : np.ndarray
            Load arrays in kW.
        elapsed : float
            Processing time in seconds.
        start_time, end_time : str
            Time range strings.
        resolution, resolution_unit : str
            Time resolution specification.
            
        Returns
        -------
        Dict[str, Any]
            Thermal load profile matching response schema.
        """
        # Handle time arrays
        has_times = False
        if isinstance(times, pd.DatetimeIndex) and not times.empty:
            has_times = True
            start_iso = times[0].isoformat()
            end_iso = times[-1].isoformat()
        elif times is not None and len(times) > 0:
            has_times = True
            if hasattr(times[0], 'isoformat'):
                start_iso = times[0].isoformat()
                end_iso = times[-1].isoformat()
            else:
                start_iso = str(times[0])
                end_iso = str(times[-1])
        else:
            start_iso = start_time or "2018-01-01T00:00:00Z"
            end_iso = end_time or "2018-12-31T23:00:00Z"
        
        # Calculate summary statistics
        def safe_stats(arr):
            """Calculate safe statistics for array."""
            if len(arr) == 0:
                return {"total_kwh": 0.0, "max_kw": 0.0, "min_kw": 0.0, "mean_kw": 0.0, "median_kw": 0.0, "std_kw": 0.0}
            
            return {
                "total_kwh": float(np.sum(arr)),
                "max_kw": float(np.max(arr)),
                "min_kw": float(np.min(arr)),
                "mean_kw": float(np.mean(arr)),
                "median_kw": float(np.median(arr)),
                "std_kw": float(np.std(arr))
            }
        
        heating_stats = safe_stats(heating)
        cooling_stats = safe_stats(np.abs(cooling))  # Ensure positive for cooling
        electricity_stats = safe_stats(electricity)
        
        # Calculate overall metrics
        total_energy = heating_stats["total_kwh"] + cooling_stats["total_kwh"] + electricity_stats["total_kwh"]
        peak_heating = heating_stats["max_kw"]
        peak_cooling = cooling_stats["max_kw"]
        
        # Estimate floor area for energy intensity (if available)
        energy_intensity = None
        # This would need to be calculated from building attributes if available
        
        profile = {
            "start_time": start_iso,
            "end_time": end_iso,
            "resolution": resolution,
            "resolution_unit": resolution_unit,
            "summary": {
                "heating": heating_stats,
                "cooling": cooling_stats,
                "electricity": electricity_stats,
                "total_energy_demand_kwh": total_energy,
                "peak_heating_load_kw": peak_heating,
                "peak_cooling_load_kw": peak_cooling
            }
        }
        
        # Add energy intensity if floor area is available
        if energy_intensity is not None:
            profile["summary"]["energy_intensity_kwh_m2"] = energy_intensity
        
        # Include timeseries data if specifically requested in response (not just for saving)
        if self.include_timeseries and has_times:
            profile["timeseries"] = {
                "timestamps": [t.isoformat() for t in times] if isinstance(times, pd.DatetimeIndex) else [str(t) for t in times],
                "heating_kw": heating.tolist(),
                "cooling_kw": cooling.tolist(),
                "electricity_kw": electricity.tolist()
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