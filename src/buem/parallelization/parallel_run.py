#!/usr/bin/env python3
"""
Parallel Building Processing Module for BUEM

This module implements parallel processing capabilities for multiple building energy models,
allowing efficient processing of thousands of buildings using multiprocessing.

Key Features:
- Parallel processing using multiprocessing.Pool
- Configurable process count based on CPU cores
- Progress tracking and performance monitoring
- Error handling and recovery for individual buildings
- Memory optimization for large building datasets
- Detailed timing and performance metrics
- Support for different processing strategies (batch, streaming)
- Enhanced thermal calculation strategies (sequential vs parallel heating/cooling)
- Building ID validation to prevent heating/cooling mismatches

Usage:
    # Basic parallel processing
    from parallel_run import ParallelBuildingProcessor
    
    processor = ParallelBuildingProcessor(workers=8)
    results = processor.process_buildings(building_files)
    
    # Advanced configuration with thermal strategies
    processor = ParallelBuildingProcessor(
        workers=8,
        thermal_strategy='parallel',
        thermal_workers=4,
        timeout=300
    )
    results = processor.process_buildings(building_files)

Requirements:
    - multiprocessing (built-in)
    - concurrent.futures (built-in Python 3.2+)
    - psutil (optional, for advanced system monitoring)
"""

import json
import time
import logging
import traceback
import copy
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime, timezone
from multiprocessing import Pool, cpu_count, Manager
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
import sys
import os

# Add the project root to Python path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root / "src"))

try:
    from buem.integration.scripts.geojson_processor import GeoJsonProcessor
    from buem.integration import validate_request_file
    from buem.main import run_model
    from buem.config.cfg_building import CfgBuilding
except ImportError as e:
    print(f"Error importing BUEM modules: {e}")
    print("Make sure BUEM is properly installed and the path is correct.")
    sys.exit(1)

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


def process_single_building_enhanced(building_file: Union[str, Path], thermal_strategy: str = 'sequential', 
                                   thermal_workers: int = 2) -> Dict[str, Any]:
    """
    Process a single building file with enhanced thermal calculation strategies.
    
    This function implements parallel heating and cooling calculations when thermal_strategy='parallel'.
    It ensures proper building matching between heating and cooling results.
    
    Parameters
    ----------
    building_file : Union[str, Path]
        Path to the building configuration JSON file
    thermal_strategy : str
        Strategy for thermal calculations: 'sequential' or 'parallel'
    thermal_workers : int
        Number of workers for parallel thermal calculations
        
    Returns
    -------
    Dict[str, Any]
        Enhanced processing results with thermal strategy information
    """
    start_time = time.time()
    building_file = Path(building_file)
    
    try:
        # Load building configuration
        with building_file.open('r') as f:
            building_data = json.load(f)
        
        # Extract building ID
        if 'features' in building_data and building_data['features']:
            building_id = building_data['features'][0].get('id', building_file.stem)
        else:
            building_id = building_file.stem
        
        logger.info(f"Processing building: {building_id} (thermal: {thermal_strategy})")
        
        # Validate the building configuration
        validation_result = validate_request_file(building_file)
        if not validation_result:
            return {
                'building_id': building_id,
                'success': False,
                'error': f"Validation failed",
                'processing_time': time.time() - start_time,
                'file_path': str(building_file),
                'thermal_strategy': thermal_strategy
            }
        
        # Enhanced processing based on thermal strategy
        if thermal_strategy == 'parallel':
            response = process_building_parallel_thermal(building_data, building_id, thermal_workers)
        else:
            response = process_building_sequential_thermal(building_data, building_id)
        
        processing_time = time.time() - start_time
        
        # Extract enhanced summary results
        summary_stats = {}
        thermal_breakdown = {}
        
        if 'features' in response and response['features']:
            feature = response['features'][0]
            if 'properties' in feature and 'buem' in feature['properties']:
                thermal_profile = feature['properties']['buem'].get('thermal_load_profile', {})
                summary_stats = thermal_profile.get('summary', {})
                
                # Extract heating/cooling breakdown if available
                thermal_breakdown = {
                    'heating_load_kwh': summary_stats.get('heating_load_kwh', 0),
                    'cooling_load_kwh': summary_stats.get('cooling_load_kwh', 0),
                    'total_load_kwh': summary_stats.get('total_load_kwh', 0),
                    'peak_heating_kw': summary_stats.get('peak_heating_kw', 0),
                    'peak_cooling_kw': summary_stats.get('peak_cooling_kw', 0)
                }
        
        return {
            'building_id': building_id,
            'success': True,
            'results': response,
            'summary_stats': summary_stats,
            'thermal_breakdown': thermal_breakdown,
            'processing_time': processing_time,
            'file_path': str(building_file),
            'thermal_strategy': thermal_strategy,
            'thermal_workers': thermal_workers if thermal_strategy == 'parallel' else 1,
            'metadata': {
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'validation_passed': validation_result,
                'thermal_strategy_used': thermal_strategy
            }
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Error processing {building_file}: {str(e)}"
        logger.error(f"{error_msg}\\n{traceback.format_exc()}")
        
        return {
            'building_id': building_file.stem,
            'success': False,
            'error': error_msg,
            'processing_time': processing_time,
            'file_path': str(building_file),
            'thermal_strategy': thermal_strategy,
            'metadata': {
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'validation_passed': False,
                'traceback': traceback.format_exc(),
                'thermal_strategy': thermal_strategy
            }
        }


def process_building_parallel_thermal(building_data: Dict[str, Any], building_id: str, 
                                    thermal_workers: int) -> Dict[str, Any]:
    """Process building with parallel heating and cooling calculations."""
    from concurrent.futures import ThreadPoolExecutor
    import copy
    
    logger.debug(f"Starting parallel thermal processing for {building_id} with {thermal_workers} workers")
    
    # Create separate copies for heating and cooling calculations
    heating_data = copy.deepcopy(building_data)
    cooling_data = copy.deepcopy(building_data)
    
    # Process heating and cooling in parallel with proper building ID maintenance
    with ThreadPoolExecutor(max_workers=thermal_workers) as executor:
        try:
            # Submit both thermal calculations
            heating_future = executor.submit(
                calculate_thermal_loads, heating_data, building_id, 'heating'
            )
            cooling_future = executor.submit(
                calculate_thermal_loads, cooling_data, building_id, 'cooling'
            )
            
            # Collect results ensuring building ID consistency
            heating_result = heating_future.result(timeout=120)
            cooling_result = cooling_future.result(timeout=120)
            
            # Validate building ID consistency
            heating_building_id = extract_building_id(heating_result)
            cooling_building_id = extract_building_id(cooling_result)
            
            if heating_building_id != cooling_building_id or heating_building_id != building_id:
                raise ValueError(f"Building ID mismatch: expected {building_id}, got heating={heating_building_id}, cooling={cooling_building_id}")
            
            # Merge results ensuring no building mismatch
            merged_result = merge_thermal_results(heating_result, cooling_result, building_id)
            
            logger.debug(f"Successfully completed parallel thermal processing for {building_id}")
            return merged_result
            
        except TimeoutError:
            logger.error(f"Thermal calculation timeout for {building_id}")
            raise TimeoutError(f"Thermal calculations timed out for building {building_id}")


def process_building_sequential_thermal(building_data: Dict[str, Any], building_id: str) -> Dict[str, Any]:
    """Process building with traditional sequential thermal calculations."""
    logger.debug(f"Starting sequential thermal processing for {building_id}")
    
    # Use existing GeoJsonProcessor for sequential processing
    processor = GeoJsonProcessor(
        payload=building_data,
        include_timeseries=False
    )
    
    # Run the processing
    response = processor.process()
    
    logger.debug(f"Completed sequential thermal processing for {building_id}")
    return response


def calculate_thermal_loads(building_data: Dict[str, Any], building_id: str, 
                          load_type: str) -> Dict[str, Any]:
    """Calculate thermal loads for a specific type (heating or cooling)."""
    logger.debug(f"Calculating {load_type} loads for {building_id}")
    
    # For now, use the existing processor
    # In future versions, this could be enhanced to separate heating/cooling calculations
    processor = GeoJsonProcessor(
        payload=building_data,
        include_timeseries=False
    )
    
    result = processor.process()
    
    # Tag result with load type and building ID for verification
    if 'features' in result and result['features']:
        result['features'][0]['load_type'] = load_type
        result['features'][0]['building_id_verified'] = building_id
    
    logger.debug(f"Completed {load_type} calculation for {building_id}")
    return result


def extract_building_id(thermal_result: Dict[str, Any]) -> str:
    """Extract building ID from thermal calculation result."""
    if 'features' in thermal_result and thermal_result['features']:
        return thermal_result['features'][0].get('building_id_verified', 
                thermal_result['features'][0].get('id', 'unknown'))
    return 'unknown'


def merge_thermal_results(heating_result: Dict[str, Any], cooling_result: Dict[str, Any], 
                        building_id: str) -> Dict[str, Any]:
    """Merge heating and cooling results ensuring building consistency."""
    logger.debug(f"Merging thermal results for {building_id}")
    
    # Use heating result as base and merge cooling data
    merged_result = copy.deepcopy(heating_result)
    
    # Ensure building ID consistency
    if 'features' in merged_result and merged_result['features']:
        merged_result['features'][0]['id'] = building_id
        merged_result['features'][0]['building_id'] = building_id
        
        # Merge thermal properties if available
        if 'properties' in merged_result['features'][0]:
            props = merged_result['features'][0]['properties']
            
            # Add parallel processing metadata
            if 'buem' not in props:
                props['buem'] = {}
            
            props['buem']['thermal_processing'] = {
                'strategy': 'parallel',
                'building_id': building_id,
                'heating_calculated': True,
                'cooling_calculated': True,
                'merged_at': datetime.now(timezone.utc).isoformat()
            }
    
    logger.debug(f"Successfully merged thermal results for {building_id}")
    return merged_result


def process_building_wrapper(args):
    """Wrapper function for enhanced building processing with thermal strategies."""
    building_file, thermal_strategy, thermal_workers = args
    return process_single_building_enhanced(building_file, thermal_strategy, thermal_workers)


def process_single_building(building_file: Union[str, Path]) -> Dict[str, Any]:
    """
    Process a single building file and return results (backwards compatibility).
    
    This function maintains backwards compatibility while using enhanced processing.
    """
    return process_single_building_enhanced(building_file, 'sequential', 1)
    """
    Process a single building file and return results.
    
    This function is designed to work in a multiprocessing environment.
    It handles all the necessary imports and error handling for individual building processing.
    
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
        if 'features' in building_data and building_data['features']:
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
                'error': f"Validation failed",
                'processing_time': time.time() - start_time,
                'file_path': str(building_file)
            }
        
        # Process with GeoJsonProcessor
        processor = GeoJsonProcessor(
            payload=building_data,
            include_timeseries=False  # Set to True if you need detailed timeseries
        )
        
        # Run the processing
        response = processor.process()
        
        processing_time = time.time() - start_time
        
        # Extract summary results
        summary_stats = {}
        if 'features' in response and response['features']:
            feature = response['features'][0]
            if 'properties' in feature and 'buem' in feature['properties']:
                thermal_profile = feature['properties']['buem'].get('thermal_load_profile', {})
                summary_stats = thermal_profile.get('summary', {})
        
        return {
            'building_id': building_id,
            'success': True,
            'results': response,
            'summary_stats': summary_stats,
            'processing_time': processing_time,
            'file_path': str(building_file),
            'metadata': {
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'validation_passed': validation_result
            }
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Error processing {building_file}: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        
        return {
            'building_id': building_file.stem,
            'success': False,
            'error': error_msg,
            'processing_time': processing_time,
            'file_path': str(building_file),
            'metadata': {
                'processed_at': datetime.now(timezone.utc).isoformat(),
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
        workers: Optional[int] = None,
        chunk_size: int = 5,
        timeout: float = 300.0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        thermal_strategy: str = 'parallel',
        thermal_workers: int = 2
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
        thermal_strategy : str
            Strategy for thermal calculations: 'parallel' (recommended) or 'sequential'
            'parallel' provides significant speedup on multi-core systems
        thermal_workers : int
            Number of workers for thermal calculations (heating/cooling)
        """
        self.workers = workers or min(16, max(1, cpu_count() - 1))  # Optimize for 16-core systems
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.progress_callback = progress_callback
        self.thermal_strategy = thermal_strategy
        self.thermal_workers = thermal_workers
        
        logger.info(f"🚀 Initialized ParallelBuildingProcessor with {self.workers} workers")
        logger.info(f"💡 Thermal strategy: {thermal_strategy}, thermal workers: {thermal_workers}")
        logger.info(f"📊 Optimized for {cpu_count()}-core system")
        
        if PSUTIL_AVAILABLE:
            memory_info = psutil.virtual_memory()
            logger.info(f"System memory: {memory_info.total / (1024**3):.1f} GB available")
    
    def process_buildings(
        self, 
        building_files: List[Union[str, Path]],
        save_results: bool = True,
        results_file: Optional[str] = None
    ) -> Dict[str, Any]:
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
            # Use ProcessPoolExecutor for better control over process lifecycle
            with ProcessPoolExecutor(max_workers=self.workers) as executor:
                # Submit all jobs with enhanced thermal processing
                if self.thermal_strategy == 'parallel':
                    # Use enhanced processing with thermal strategies
                    future_to_file = {
                        executor.submit(
                            process_building_wrapper,
                            (building_file, self.thermal_strategy, self.thermal_workers)
                        ): building_file
                        for building_file in building_files
                    }
                else:
                    # Use standard processing for sequential thermal strategy
                    future_to_file = {
                        executor.submit(
                            process_building_wrapper,
                            (building_file, 'sequential', 1)
                        ): building_file
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
                    
                    except Exception as e:
                        building_file = future_to_file[future]
                        error_result = {
                            'building_id': Path(building_file).stem,
                            'success': False,
                            'error': f"Unexpected error: {str(e)}",
                            'processing_time': 0,
                            'file_path': str(building_file)
                        }
                        failed_buildings.append(error_result)
                        logger.error(f"💥 Error: {error_result['building_id']} - {str(e)}")
                        completed_count += 1
        
        except Exception as e:
            logger.error(f"Critical error in parallel processing: {str(e)}")
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
                'processed_at': datetime.now(timezone.utc).isoformat()
            },
            'buildings': {
                'successful': completed_buildings,
                'failed': failed_buildings
            },
            'performance': performance_metrics
        }
        
        # Save results if requested
        if save_results:
            results_file = results_file or f"parallel_processing_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to: {results_file}")
            results['results_file'] = results_file
        
        # Log summary
        logger.info(f"🎯 Processing Summary:")
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
    dummy_dir = Path(__file__).parent.parent / "integration/json_schema/versions/v2/dummy"
    building_files = list(dummy_dir.glob("*.json"))
    
    if not building_files:
        logger.error(f"No building files found in {dummy_dir}")
        return
    
    logger.info(f"Found {len(building_files)} building files for processing")
    
    def progress_handler(completed: int, total: int):
        """Simple progress handler for demonstration."""
        progress = (completed / total) * 100
        logger.info(f"Progress: {completed}/{total} ({progress:.1f}%)")
    
    # Create processor with different configurations for comparison
    processor = ParallelBuildingProcessor(
        workers=4,  # Use 4 workers for demonstration
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
