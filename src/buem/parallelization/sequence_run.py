#!/usr/bin/env python3
"""
Sequential Building Processing Module for BUEM

This module implements sequential (single-threaded) processing for multiple building energy models.
It serves as a baseline comparison for parallel processing performance evaluation.

Key Features:
- Sequential processing of multiple buildings
- Detailed timing and performance metrics
- Error handling and recovery for individual buildings
- Memory monitoring and optimization
- Compatible API with ParallelBuildingProcessor
- Progress tracking and logging
- Comprehensive result compilation

Usage:
    # Basic sequential processing
    from sequence_run import SequentialBuildingProcessor
    
    processor = SequentialBuildingProcessor()
    results = processor.process_buildings(building_files)
    
    # Advanced configuration
    processor = SequentialBuildingProcessor(
        timeout=300,
        progress_callback=my_progress_handler,
        detailed_logging=True
    )
    results = processor.process_batch(building_files)

Performance Notes:
    - Sequential processing is useful for:
      * Debugging individual building processing issues
      * Memory-constrained environments
      * Single-core systems or limited resources
      * Baseline performance comparison
    - For large datasets (>100 buildings), parallel processing is recommended
"""

import json
import time
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime, timezone
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


def process_single_building_sequential(building_file: Union[str, Path]) -> Dict[str, Any]:
    """
    Process a single building file sequentially and return results.
    
    This function is designed for sequential processing and includes detailed
    error handling and logging for debugging purposes.
    
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
        - detailed_stats: Detailed performance statistics
    """
    start_time = time.time()
    building_file = Path(building_file)
    
    # Initialize detailed stats tracking
    stats = {
        'load_time': 0,
        'validation_time': 0,
        'processing_time': 0,
        'total_time': 0
    }
    
    try:
        # Load building configuration
        load_start = time.time()
        with building_file.open('r') as f:
            building_data = json.load(f)
        stats['load_time'] = time.time() - load_start
        
        # Extract building ID
        if 'features' in building_data and building_data['features']:
            building_id = building_data['features'][0].get('id', building_file.stem)
        else:
            building_id = building_file.stem
        
        logger.info(f"Processing building: {building_id} (sequential)")
        
        # Validate the building configuration
        validation_start = time.time()
        validation_result = validate_request_file(building_file)
        stats['validation_time'] = time.time() - validation_start
        
        if not validation_result:
            return {
                'building_id': building_id,
                'success': False,
                'error': f"Validation failed",
                'processing_time': time.time() - start_time,
                'file_path': str(building_file),
                'detailed_stats': stats
            }
        
        # Process with GeoJsonProcessor
        processing_start = time.time()
        processor = GeoJsonProcessor(
            payload=building_data,
            include_timeseries=False  # Set to True if you need detailed timeseries
        )
        
        # Run the processing
        response = processor.process()
        stats['processing_time'] = time.time() - processing_start
        
        total_time = time.time() - start_time
        stats['total_time'] = total_time
        
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
            'processing_time': total_time,
            'file_path': str(building_file),
            'detailed_stats': stats,
            'metadata': {
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'validation_passed': validation_result,
                'processing_mode': 'sequential'
            }
        }
        
    except Exception as e:
        total_time = time.time() - start_time
        stats['total_time'] = total_time
        error_msg = f"Error processing {building_file}: {str(e)}"
        logger.error(f"{error_msg}\\n{traceback.format_exc()}")
        
        return {
            'building_id': building_file.stem,
            'success': False,
            'error': error_msg,
            'processing_time': total_time,
            'file_path': str(building_file),
            'detailed_stats': stats,
            'metadata': {
                'processed_at': datetime.now(timezone.utc).isoformat(),
                'validation_passed': False,
                'processing_mode': 'sequential',
                'traceback': traceback.format_exc()
            }
        }


class SequentialBuildingProcessor:
    """
    Sequential processor for multiple building energy models.
    
    This class provides sequential processing of building configurations
    as a baseline for comparison with parallel processing approaches.
    
    Attributes
    ----------
    timeout : float
        Timeout for individual building processing (seconds)
    progress_callback : Callable
        Optional callback for progress updates
    detailed_logging : bool
        Enable detailed logging for each building
    memory_monitoring : bool
        Enable memory usage monitoring
    """
    
    def __init__(
        self,
        timeout: float = 300.0,
        progress_callback: Optional[Callable[[int, int], None]] = None,
        detailed_logging: bool = True,
        memory_monitoring: bool = True
    ):
        """
        Initialize the sequential processor.
        
        Parameters
        ----------
        timeout : float
            Timeout for individual building processing in seconds (default: 300)
        progress_callback : Optional[Callable]
            Callback function called with (completed_count, total_count)
        detailed_logging : bool
            Enable detailed logging for each building (default: True)
        memory_monitoring : bool
            Enable memory usage monitoring (default: True)
        """
        self.timeout = timeout
        self.progress_callback = progress_callback
        self.detailed_logging = detailed_logging
        self.memory_monitoring = memory_monitoring and PSUTIL_AVAILABLE
        
        logger.info("Initialized SequentialBuildingProcessor")
        
        if self.memory_monitoring:
            memory_info = psutil.virtual_memory()
            logger.info(f"System memory: {memory_info.total / (1024**3):.1f} GB available")
    
    def process_buildings(
        self, 
        building_files: List[Union[str, Path]],
        save_results: bool = True,
        results_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process multiple buildings sequentially.
        
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
        
        logger.info(f"Starting sequential processing of {total_buildings} buildings")
        
        # Initialize results tracking
        completed_buildings = []
        failed_buildings = []
        performance_metrics = {
            'start_time': start_time,
            'mode': 'sequential',
            'total_buildings': total_buildings,
            'detailed_timing': []
        }
        
        if self.memory_monitoring:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
            performance_metrics['initial_memory_mb'] = initial_memory
            performance_metrics['memory_samples'] = []
        
        try:
            # Process buildings one by one
            for idx, building_file in enumerate(building_files):
                building_start_time = time.time()
                
                try:
                    # Apply timeout using a simple time check
                    result = process_single_building_sequential(building_file)
                    
                    if result['processing_time'] > self.timeout:
                        result['success'] = False
                        result['error'] = f"Processing timeout ({self.timeout}s)"
                        failed_buildings.append(result)
                        logger.error(f"⏱️ Timeout: {result['building_id']}")
                    elif result['success']:
                        completed_buildings.append(result)
                        if self.detailed_logging:
                            logger.info(f"✅ Completed: {result['building_id']} "
                                      f"({result['processing_time']:.2f}s)")
                    else:
                        failed_buildings.append(result)
                        logger.error(f"❌ Failed: {result['building_id']} - {result['error']}")
                    
                    # Record detailed timing
                    building_time = time.time() - building_start_time
                    performance_metrics['detailed_timing'].append({
                        'building_id': result['building_id'],
                        'processing_time': building_time,
                        'success': result['success']
                    })
                    
                    # Progress callback
                    if self.progress_callback:
                        self.progress_callback(idx + 1, total_buildings)
                    
                    # Memory monitoring
                    if self.memory_monitoring and (idx + 1) % 5 == 0:
                        current_memory = process.memory_info().rss / (1024 * 1024)  # MB
                        performance_metrics['memory_samples'].append({
                            'step': idx + 1,
                            'memory_mb': current_memory
                        })
                        if self.detailed_logging:
                            logger.info(f"Memory usage: {current_memory:.1f} MB")
                    
                except Exception as e:
                    error_result = {
                        'building_id': Path(building_file).stem,
                        'success': False,
                        'error': f"Unexpected error: {str(e)}",
                        'processing_time': time.time() - building_start_time,
                        'file_path': str(building_file),
                        'metadata': {
                            'traceback': traceback.format_exc()
                        }
                    }
                    failed_buildings.append(error_result)
                    logger.error(f"💥 Error: {error_result['building_id']} - {str(e)}")
        
        except KeyboardInterrupt:
            logger.warning("Processing interrupted by user")
            raise
        
        except Exception as e:
            logger.error(f"Critical error in sequential processing: {str(e)}")
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
        
        if self.memory_monitoring:
            final_memory = process.memory_info().rss / (1024 * 1024)  # MB
            performance_metrics['final_memory_mb'] = final_memory
            performance_metrics['memory_increase_mb'] = final_memory - initial_memory
            performance_metrics['peak_memory_mb'] = max(
                [sample['memory_mb'] for sample in performance_metrics['memory_samples']] + [final_memory]
            ) if performance_metrics['memory_samples'] else final_memory
        
        # Calculate detailed statistics
        if completed_buildings:
            all_stats = [b['detailed_stats'] for b in completed_buildings if 'detailed_stats' in b]
            if all_stats:
                performance_metrics['average_load_time'] = sum(s['load_time'] for s in all_stats) / len(all_stats)
                performance_metrics['average_validation_time'] = sum(s['validation_time'] for s in all_stats) / len(all_stats)
                performance_metrics['average_model_processing_time'] = sum(s['processing_time'] for s in all_stats) / len(all_stats)
        
        # Compile comprehensive results
        results = {
            'summary': {
                'total_buildings': total_buildings,
                'successful': successful_count,
                'failed': failed_count,
                'success_rate_percent': performance_metrics['success_rate'] * 100,
                'total_processing_time': total_time,
                'processing_mode': 'sequential',
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
            results_file = results_file or f"sequential_processing_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to: {results_file}")
            results['results_file'] = results_file
        
        # Log summary
        logger.info(f"🎯 Sequential Processing Summary:")
        logger.info(f"   Total buildings: {total_buildings}")
        logger.info(f"   ✅ Successful: {successful_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        logger.info(f"   📊 Success rate: {performance_metrics['success_rate']:.1%}")
        logger.info(f"   ⏱️ Total time: {total_time:.2f}s")
        logger.info(f"   🐌 Rate: {performance_metrics['buildings_per_second']:.2f} buildings/sec")
        logger.info(f"   ⚡ Avg time per building: {performance_metrics['average_time_per_building']:.2f}s")
        
        if self.memory_monitoring:
            logger.info(f"   💾 Memory increase: {performance_metrics['memory_increase_mb']:.1f} MB")
            logger.info(f"   📈 Peak memory: {performance_metrics['peak_memory_mb']:.1f} MB")
        
        return results


def demo_sequential_processing():
    """
    Demonstrate sequential processing with the dummy building files.
    
    This function shows how to use the SequentialBuildingProcessor with
    the previously created dummy building configurations.
    """
    # Find dummy building files
    dummy_dir = Path(__file__).parent.parent / "integration/json_schema/versions/v2/dummy"
    building_files = list(dummy_dir.glob("*.json"))
    
    if not building_files:
        logger.error(f"No building files found in {dummy_dir}")
        return
    
    logger.info(f"Found {len(building_files)} building files for sequential processing")
    
    def progress_handler(completed: int, total: int):
        """Simple progress handler for demonstration."""
        progress = (completed / total) * 100
        logger.info(f"Sequential Progress: {completed}/{total} ({progress:.1f}%)")
    
    # Create sequential processor
    processor = SequentialBuildingProcessor(
        timeout=120.0,
        progress_callback=progress_handler,
        detailed_logging=True,
        memory_monitoring=True
    )
    
    # Process buildings
    print("\\n" + "="*60)
    print("STARTING SEQUENTIAL BUILDING PROCESSING DEMONSTRATION")
    print("="*60)
    
    results = processor.process_buildings(
        building_files=building_files,
        save_results=True
    )
    
    # Display detailed results
    print("\\n" + "="*60)
    print("SEQUENTIAL PROCESSING RESULTS SUMMARY")
    print("="*60)
    
    summary = results['summary']
    performance = results['performance']
    
    print(f"📊 Buildings processed: {summary['total_buildings']}")
    print(f"✅ Successful: {summary['successful']}")
    print(f"❌ Failed: {summary['failed']}")
    print(f"📈 Success rate: {summary['success_rate_percent']:.1f}%")
    print(f"⏱️ Total time: {summary['total_processing_time']:.2f} seconds")
    print(f"🐌 Processing rate: {performance['buildings_per_second']:.2f} buildings/second")
    print(f"⚡ Avg time per building: {performance['average_time_per_building']:.2f} seconds")
    
    if 'peak_memory_mb' in performance:
        print(f"💾 Peak memory usage: {performance['peak_memory_mb']:.1f} MB")
        print(f"📈 Memory increase: {performance['memory_increase_mb']:.1f} MB")
    
    # Show detailed timing breakdown if available
    if 'average_load_time' in performance:
        print("\\n📋 Detailed timing breakdown (averages):")
        print(f"   📂 File loading: {performance['average_load_time']*1000:.1f} ms")
        print(f"   ✅ Validation: {performance['average_validation_time']*1000:.1f} ms")
        print(f"   🏗️ Model processing: {performance['average_model_processing_time']*1000:.1f} ms")
    
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
    demo_sequential_processing()
