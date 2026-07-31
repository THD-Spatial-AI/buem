#!/usr/bin/env python3
"""
Parallel Building Processing Module for BUEM

This module implements parallel processing capabilities for multiple building energy models,
allowing efficient processing of thousands of buildings using multiprocessing.

The thermal model uses a single-pass LP solver (CLARABEL) that simultaneously determines
heating and cooling demand via a dead-band formulation. Building-level parallelism is
achieved by distributing buildings across worker processes.

Key Features:
- Parallel processing using ProcessPoolExecutor
- Configurable process count based on CPU cores
- Progress tracking and performance monitoring
- Error handling and recovery for individual buildings
- Memory optimization for large building datasets
- Detailed timing and performance metrics

Usage:
    # Basic parallel processing
    from parallel_run import ParallelBuildingProcessor
    
    processor = ParallelBuildingProcessor(workers=8)
    results = processor.process_buildings(building_files)

Requirements:
    - concurrent.futures (built-in Python 3.2+)
    - psutil (optional, for advanced system monitoring)
"""

import json
import logging
import time
import traceback
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, TimeoutError, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import UTC, datetime
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any

from buem.config.weather_cache import (
    distinct_locations,
    get_or_fetch_weather,
    weather_available,
)
from buem.integration import validate_request_file
from buem.integration.scripts.geojson_processor import GeoJsonProcessor


def _worker_init():
    """
    Worker initializer called once per spawned process.

    On Windows the 'spawn' start-method creates a fresh Python interpreter for each
    worker.  Pre-importing the heavy modules here (cvxpy, numpy, pandas, and the
    BUEM config stack) moves that one-time cost into pool creation rather than into the
    first ``process_single_building`` call.

    The import of ``buem.config.cfg_attribute`` also triggers the bundled-CSV
    weather-data load (the offline fallback default). Because the main process has
    already created its feather cache, workers read the fast binary feather file
    (~50 ms) instead of parsing the CSV and running the pvlib DISC decomposition
    (~2-3 s). Per-building dynamic weather (when the optional ``weather`` package is
    installed) is resolved separately, per building, inside each worker via
    ``AttributeBuilder.generate_weather_profile()`` -- see ``process_buildings``'s
    pre-warm step below for why that no longer assumes a single global location.
    """
    # Heavy numerics / solver
    import cvxpy  # noqa: F401
    import numpy  # noqa: F401
    import pandas  # noqa: F401

    # BUEM config stack (triggers weather feather-cache read via cfg_attribute)
    from buem.config import cfg_attribute  # noqa: F401

def _extract_building_attrs(building_file: str | Path) -> dict[str, Any]:
    """Best-effort extraction of latitude/longitude/year/weather_provider
    from a raw building request JSON file, for weather cache pre-warming.

    Returns an empty dict (falls back to distinct_locations()'s own
    defaults) on any parse failure -- a malformed file here should not
    block pre-warming for the rest of the batch; process_single_building
    still validates and reports errors for that file individually.
    """
    try:
        with Path(building_file).open('r') as f:
            data = json.load(f)
        feature = data['features'][0] if 'features' in data else data
        attrs: dict[str, Any] = dict(
            feature.get('properties', {}).get('building_attributes', {})
        )
        coords = feature.get('geometry', {}).get('coordinates')
        if coords and len(coords) >= 2:
            attrs.setdefault('longitude', coords[0])
            attrs.setdefault('latitude', coords[1])
        return attrs
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        return {}


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Optional dependency for system monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - system monitoring will be limited")


def process_single_building(building_file: str | Path) -> dict[str, Any]:
    """
    Process a single building file and return results.
    
    This function is designed to work in a multiprocessing environment.
    It handles all the necessary imports and error handling for individual building processing.
    The thermal model uses a single-pass LP solver (CLARABEL) that simultaneously
    determines heating and cooling demand.
    
    Parameters
    ----------
    building_file : Union[str, Path]
        Path to the building configuration JSON file
        
    Returns
    -------
    Dict[str, Any]
        Processing results including:
        - building_id: Identifier of processed building
        - success: Boolean indicating success/failure
        - results: Thermal load results (if successful)
        - error: Error message (if failed)
        - processing_time: Time taken to process this building
        - metadata: Additional processing metadata
    """
    start_time = time.time()
    building_file = Path(building_file)
    
    try:
        # Load building configuration
        with building_file.open('r') as f:
            building_data = json.load(f)
        
        # Extract building ID
        if building_data.get('features'):
            building_id = building_data['features'][0].get('id', building_file.stem)
        else:
            building_id = building_file.stem
        
        logger.info(f"Processing building: {building_id}")
        
        # Validate the building configuration
        validation_result = validate_request_file(building_file)
        if not validation_result:
            return {
                'building_id': building_id,
                'success': False,
                'error': "Validation failed",
                'processing_time': time.time() - start_time,
                'file_path': str(building_file)
            }
        
        # Process with GeoJsonProcessor (uses single-pass LP solver internally)
        processor = GeoJsonProcessor(
            payload=building_data,
            include_timeseries=False
        )
        response = processor.process()
        
        processing_time = time.time() - start_time
        
        # Check response metadata for processing errors
        resp_meta = response.get('metadata', {})
        failed_features = resp_meta.get('failed_features', 0)
        total_features = resp_meta.get('total_features', 0)
        
        if failed_features > 0 and failed_features == total_features:
            # All features failed — report the building as failed
            errors = response.get('validation_report', {}).get('processing_errors', [])
            error_msg = '; '.join(errors) if errors else 'All features failed during processing'
            return {
                'building_id': building_id,
                'success': False,
                'error': error_msg,
                'processing_time': processing_time,
                'file_path': str(building_file),
                'metadata': {
                    'processed_at': datetime.now(UTC).isoformat(),
                    'validation_passed': validation_result,
                    'failed_features': failed_features,
                    'total_features': total_features
                }
            }
        
        # Extract summary results
        summary_stats = {}
        thermal_breakdown = {}
        if response.get('features'):
            feature = response['features'][0]
            if 'properties' in feature and 'buem' in feature['properties']:
                thermal_profile = feature['properties']['buem'].get('thermal_load_profile', {})
                summary_stats = thermal_profile.get('summary', {})
                thermal_breakdown = {
                    'heating_load_kwh': summary_stats.get('heating_load_kwh', 0),
                    'cooling_load_kwh': summary_stats.get('cooling_load_kwh', 0),
                    'total_load_kwh': summary_stats.get('total_load_kwh', 0),
                    'peak_heating_kw': summary_stats.get('peak_heating_kw', 0),
                    'peak_cooling_kw': summary_stats.get('peak_cooling_kw', 0)
                }
        
        # Partial success: some features failed
        has_partial_errors = failed_features > 0
        
        return {
            'building_id': building_id,
            'success': True,
            'partial_errors': has_partial_errors,
            'results': response,
            'summary_stats': summary_stats,
            'thermal_breakdown': thermal_breakdown,
            'processing_time': processing_time,
            'file_path': str(building_file),
            'metadata': {
                'processed_at': datetime.now(UTC).isoformat(),
                'validation_passed': validation_result,
                'failed_features': failed_features,
                'total_features': total_features
            }
        }
        
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        processing_time = time.time() - start_time
        error_msg = f"Error processing {building_file}: {e!s}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        return {
            'building_id': building_file.stem,
            'success': False,
            'error': error_msg,
            'processing_time': processing_time,
            'file_path': str(building_file),
            'metadata': {
                'processed_at': datetime.now(UTC).isoformat(),
                'validation_passed': False,
                'traceback': traceback.format_exc()
            }
        }


class ParallelBuildingProcessor:
    """
    High-performance parallel processor for multiple building energy models.
    
    This class provides efficient parallel processing of building configurations
    using multiprocessing for CPU-intensive thermal modeling computations.
    
    Attributes
    ----------
    workers : int
        Number of worker processes
    chunk_size : int
        Size of chunks for batch processing
    timeout : float
        Timeout for individual building processing (seconds)
    progress_callback : Callable
        Optional callback for progress updates
    """
    
    def __init__(
        self,
        workers: int | None = None,
        chunk_size: int = 5,
        timeout: float = 300.0,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """
        Initialize the parallel processor.
        
        Parameters
        ----------
        workers : Optional[int]
            Number of worker processes. If None, auto-detect based on CPU cores
        chunk_size : int
            Number of buildings to process in each chunk (default: 5)
        timeout : float
            Timeout for individual building processing in seconds (default: 300)
        progress_callback : Optional[Callable]
            Callback function called with (completed_count, total_count)
        """
        # Optimal worker count ≈ 60% of logical cores for CPU-bound LP workloads.
        # This approximates the physical core count on hybrid P/E architectures
        # and avoids excessive context-switching overhead.  Benchmark on a 22-core
        # Intel Ultra 7 165H showed 10 workers optimal for 15 buildings.
        self.workers = workers or min(16, max(2, int(cpu_count() * 0.6)))
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.progress_callback = progress_callback
        
        logger.info(f"Initialized ParallelBuildingProcessor with {self.workers} workers")
        logger.info(f"Optimized for {cpu_count()}-core system")
        
        if PSUTIL_AVAILABLE:
            memory_info = psutil.virtual_memory()
            logger.info(f"System memory: {memory_info.total / (1024**3):.1f} GB available")
    
    def process_buildings(
        self,
        building_files: Sequence[str | Path],
        save_results: bool = True,
        results_file: str | None = None
    ) -> dict[str, Any]:
        """
        Process multiple buildings in parallel.
        
        Parameters
        ----------
        building_files : List[Union[str, Path]]
            List of paths to building configuration files
        save_results : bool
            Whether to save results to a file (default: True)
        results_file : Optional[str]
            Path to save results file (default: auto-generated)
            
        Returns
        -------
        Dict[str, Any]
            Comprehensive results including:
            - summary: Overall processing summary
            - buildings: Individual building results
            - performance: Performance metrics
            - errors: List of errors encountered
        """
        start_time = time.time()
        total_buildings = len(building_files)
        
        logger.info(f"Starting parallel processing of {total_buildings} buildings")
        logger.info(f"Using {self.workers} worker processes")
        
        # Initialize results tracking
        completed_buildings = []
        failed_buildings = []
        performance_metrics = {
            'start_time': start_time,
            'workers': self.workers,
            'total_buildings': total_buildings
        }
        
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
            performance_metrics['initial_memory_mb'] = initial_memory
        
        try:
            # Ensure the bundled-CSV feather cache exists before spawning workers
            # (the offline fallback default -- see cfg_attribute.py). The import
            # triggers module-level code which either reads the existing cache or
            # creates it from CSV + pvlib DISC.
            from buem.config import cfg_attribute  # noqa: F401
            logger.info("Bundled weather feather cache ready")

            # Pre-warm the dynamic per-location weather cache for every distinct
            # (latitude, longitude, year, provider) across this batch, in the main
            # process, before forking workers. A single building batch can span
            # many locations, so this replaces the old single-global-cache
            # assumption above with one cache entry per distinct location.
            if weather_available():
                locations = distinct_locations(
                    _extract_building_attrs(f) for f in building_files
                )
                logger.info(
                    "Pre-warming weather cache for %d distinct location(s)",
                    len(locations),
                )
                for lat, lon, year, provider in locations:
                    try:
                        get_or_fetch_weather(lat, lon, year, provider)
                    except (ImportError, FileNotFoundError, KeyError, OSError, ValueError) as exc:
                        logger.warning(
                            "Weather pre-warm failed for (lat=%s, lon=%s, year=%s, "
                            "provider=%s): %s -- affected buildings will fall back "
                            "to the bundled default at processing time.",
                            lat, lon, year, provider, exc,
                        )

            # Use ProcessPoolExecutor for better control over process lifecycle.
            # _worker_init pre-imports heavy modules (cvxpy, numpy, pandas, buem model
            # stack) in each spawned process so the first building doesn't pay the
            # import cost (~3-5 s on Windows with 'spawn' start method).
            with ProcessPoolExecutor(
                max_workers=self.workers,
                initializer=_worker_init,
            ) as executor:
                # Submit all building jobs
                future_to_file = {
                    executor.submit(process_single_building, building_file): building_file
                    for building_file in building_files
                }
                
                # Process completed jobs as they finish
                completed_count = 0
                for future in as_completed(future_to_file, timeout=self.timeout * total_buildings):
                    try:
                        result = future.result(timeout=self.timeout)
                        
                        if result['success']:
                            completed_buildings.append(result)
                            logger.info(f"✅ Completed: {result['building_id']} "
                                      f"({result['processing_time']:.2f}s)")
                        else:
                            failed_buildings.append(result)
                            logger.error(f"❌ Failed: {result['building_id']} - {result['error']}")
                        
                        completed_count += 1
                        
                        # Progress callback
                        if self.progress_callback:
                            self.progress_callback(completed_count, total_buildings)
                        
                        # Memory monitoring
                        if PSUTIL_AVAILABLE and completed_count % 10 == 0:
                            current_memory = process.memory_info().rss / (1024 * 1024)  # MB
                            logger.info(f"Memory usage: {current_memory:.1f} MB")
                        
                    except TimeoutError:
                        building_file = future_to_file[future]
                        error_result = {
                            'building_id': Path(building_file).stem,
                            'success': False,
                            'error': f"Processing timeout ({self.timeout}s)",
                            'processing_time': self.timeout,
                            'file_path': str(building_file)
                        }
                        failed_buildings.append(error_result)
                        logger.error(f"⏱️ Timeout: {error_result['building_id']}")
                        completed_count += 1
                    
                    except (OSError, ValueError, KeyError, IndexError, TypeError,
                            AttributeError, BrokenProcessPool) as e:
                        building_file = future_to_file[future]
                        error_result = {
                            'building_id': Path(building_file).stem,
                            'success': False,
                            'error': f"Unexpected error: {e!s}",
                            'processing_time': 0,
                            'file_path': str(building_file)
                        }
                        failed_buildings.append(error_result)
                        logger.error(f"💥 Error: {error_result['building_id']} - {e!s}")
                        completed_count += 1
        
        except Exception as e:
            logger.error(f"Critical error in parallel processing: {e!s}")
            raise
        
        # Calculate performance metrics
        total_time = time.time() - start_time
        successful_count = len(completed_buildings)
        failed_count = len(failed_buildings)
        
        performance_metrics.update({
            'total_time': total_time,
            'successful_buildings': successful_count,
            'failed_buildings': failed_count,
            'success_rate': successful_count / total_buildings if total_buildings > 0 else 0,
            'buildings_per_second': total_buildings / total_time if total_time > 0 else 0,
            'average_time_per_building': sum(r['processing_time'] for r in completed_buildings) / max(1, successful_count)
        })
        
        if PSUTIL_AVAILABLE:
            final_memory = process.memory_info().rss / (1024 * 1024)  # MB
            performance_metrics['final_memory_mb'] = final_memory
            performance_metrics['memory_increase_mb'] = final_memory - initial_memory
        
        # Compile comprehensive results
        results = {
            'summary': {
                'total_buildings': total_buildings,
                'successful': successful_count,
                'failed': failed_count,
                'success_rate_percent': performance_metrics['success_rate'] * 100,
                'total_processing_time': total_time,
                'processed_at': datetime.now(UTC).isoformat()
            },
            'buildings': {
                'successful': completed_buildings,
                'failed': failed_buildings
            },
            'performance': performance_metrics
        }
        
        # Save results if requested
        if save_results:
            if not results_file:
                results_dir = Path(__file__).resolve().parent.parent / "results"
                results_dir.mkdir(parents=True, exist_ok=True)
                results_file = str(results_dir / f"parallel_processing_results_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json")
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to: {results_file}")
            results['results_file'] = results_file
        
        # Log summary
        logger.info("🎯 Processing Summary:")
        logger.info(f"   Total buildings: {total_buildings}")
        logger.info(f"   ✅ Successful: {successful_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        logger.info(f"   📊 Success rate: {performance_metrics['success_rate']:.1%}")
        logger.info(f"   ⏱️ Total time: {total_time:.2f}s")
        logger.info(f"   🚀 Rate: {performance_metrics['buildings_per_second']:.2f} buildings/sec")
        
        return results


def demo_parallel_processing():
    """
    Demonstrate parallel processing with the dummy building files.
    
    This function shows how to use the ParallelBuildingProcessor with
    the previously created dummy building configurations.
    """
    # Find dummy building files
    dummy_dir = Path(__file__).parent.parent / "data/buildings/dummy"
    building_files = list(dummy_dir.glob("*.json"))
    
    if not building_files:
        logger.error(f"No building files found in {dummy_dir}")
        return
    
    logger.info(f"Found {len(building_files)} building files for processing")
    
    def progress_handler(completed: int, total: int):
        """Simple progress handler for demonstration."""
        progress = (completed / total) * 100
        logger.info(f"Progress: {completed}/{total} ({progress:.1f}%)")
    
    # Create processor with auto-detected worker count
    processor = ParallelBuildingProcessor(
        chunk_size=2,
        timeout=120.0,
        progress_callback=progress_handler
    )
    
    # Process buildings
    print("\\n" + "="*60)
    print("STARTING PARALLEL BUILDING PROCESSING DEMONSTRATION")
    print("="*60)
    
    results = processor.process_buildings(
        building_files=building_files,
        save_results=True
    )
    
    # Display detailed results
    print("\\n" + "="*60)
    print("PROCESSING RESULTS SUMMARY")
    print("="*60)
    
    summary = results['summary']
    performance = results['performance']
    
    print(f"📊 Buildings processed: {summary['total_buildings']}")
    print(f"✅ Successful: {summary['successful']}")
    print(f"❌ Failed: {summary['failed']}")
    print(f"📈 Success rate: {summary['success_rate_percent']:.1f}%")
    print(f"⏱️ Total time: {summary['total_processing_time']:.2f} seconds")
    print(f"🚀 Processing rate: {performance['buildings_per_second']:.2f} buildings/second")
    print(f"⚡ Avg time per building: {performance['average_time_per_building']:.2f} seconds")
    
    # Show individual building results
    print("\\n" + "-"*60)
    print("INDIVIDUAL BUILDING RESULTS")
    print("-"*60)
    
    for building in results['buildings']['successful']:
        stats = building.get('summary_stats', {})
        heating = stats.get('heating', {})
        cooling = stats.get('cooling', {})
        
        print(f"🏢 {building['building_id']}")
        print(f"   ⏱️ Processing time: {building['processing_time']:.2f}s")
        if heating:
            print(f"   🔥 Heating total: {heating.get('total_kwh', 0):.1f} kWh")
        if cooling:
            print(f"   ❄️ Cooling total: {cooling.get('total_kwh', 0):.1f} kWh")
        print()
    
    # Show failures if any
    if results['buildings']['failed']:
        print("\\n" + "-"*60)
        print("FAILED BUILDINGS")
        print("-"*60)
        for building in results['buildings']['failed']:
            print(f"❌ {building['building_id']}: {building['error']}")
    
    return results


if __name__ == "__main__":
    # Run the demonstration
    demo_parallel_processing()
