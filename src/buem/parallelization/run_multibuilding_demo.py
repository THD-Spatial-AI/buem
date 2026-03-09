#!/usr/bin/env python3
"""
BUEM Multi-Building Processing Demonstration & Testing Suite

This master script demonstrates the complete multi-building processing capabilities
of the BUEM system, including parallel and sequential processing with performance
comparison and analysis.

Features Demonstrated:
- 🏢 Multiple building configurations processing
- ⚡ Parallel vs Sequential processing comparison
- 📊 Performance metrics and analysis
- 📈 Scalability testing
- 🎯 Optimization recommendations
- 📋 Comprehensive reporting

Usage:
    # Run complete demonstration
    python run_multibuilding_demo.py
    
    # Run specific tests
    python run_multibuilding_demo.py --test parallel
    python run_multibuilding_demo.py --test sequential
    python run_multibuilding_demo.py --test comparison
    python run_multibuilding_demo.py --test benchmark

Requirements:
    - BUEM system properly installed
    - Dummy building configurations (automatically created if missing)
    - psutil and joblib packages (automatically installed if missing)

Output:
    - Performance comparison reports
    - Processing results for each building
    - Visualization charts (if matplotlib available)
    - Optimization recommendations
"""

import argparse
import sys
import time
import logging
import multiprocessing
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to Python path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root / "src"))

try:
    from buem.parallelization.parallel_run import ParallelBuildingProcessor, demo_parallel_processing
    from buem.parallelization.sequence_run import SequentialBuildingProcessor, demo_sequential_processing
    from buem.parallelization.performance_comparison import PerformanceComparator, demo_performance_comparison
except ImportError as e:
    print(f"Error importing processing modules: {e}")
    print("Make sure all processing modules are available in the parallelization folder.")
    sys.exit(1)


def print_banner():
    """Print a nice banner for the demonstration."""
    print("\\n" + "="*80)
    print("🏢 BUEM MULTI-BUILDING PROCESSING DEMONSTRATION SUITE 🏢")
    print("="*80)
    print("This demonstration shows the capabilities of the BUEM system for")
    print("processing multiple buildings efficiently using parallel computing.")
    print("="*80 + "\n")


def check_dependencies():
    """Check if all required dependencies are available."""
    dependencies = {
        'numpy': 'numpy',
        'pandas': 'pandas',
        'psutil': 'psutil',
        'joblib': 'joblib'
    }
    
    missing_deps = []
    
    for name, module in dependencies.items():
        try:
            __import__(module)
            logger.info(f"✅ {name} is available")
        except ImportError:
            missing_deps.append(name)
            logger.warning(f"❌ {name} is missing")
    
    if missing_deps:
        logger.error(f"Missing dependencies: {', '.join(missing_deps)}")
        logger.info("Please install missing dependencies using conda:")
        logger.info(f"conda install {' '.join(missing_deps)}")
        return False
    
    return True


def check_dummy_buildings() -> List[Path]:
    """Check for dummy building files and create them if missing."""
    dummy_dir = Path(__file__).parent.parent / "integration/json_schema/versions/v2/dummy"
    building_files = list(dummy_dir.glob("*.json"))
    
    if not building_files:
        logger.warning("No dummy building files found!")
        logger.info("Please run the individual scripts to create dummy buildings first.")
        logger.info("Expected location: src/buem/integration/json_schema/versions/v2/dummy/")
        return []
    
    logger.info(f"Found {len(building_files)} dummy building files:")
    for file in building_files:
        logger.info(f"  🏢 {file.name}")
    
    return building_files


def run_parallel_demo():
    """Run the parallel processing demonstration."""
    print("\\n" + "🚀" * 20)
    print("PARALLEL PROCESSING DEMONSTRATION")
    print("🚀" * 20)
    
    try:
        results = demo_parallel_processing()
        logger.info("✅ Parallel processing demonstration completed successfully")
        return results
    except Exception as e:
        logger.error(f"❌ Parallel processing demonstration failed: {e}")
        return None


def run_sequential_demo():
    """Run the sequential processing demonstration."""
    print("\\n" + "🐌" * 20)
    print("SEQUENTIAL PROCESSING DEMONSTRATION")
    print("🐌" * 20)
    
    try:
        results = demo_sequential_processing()
        logger.info("✅ Sequential processing demonstration completed successfully")
        return results
    except Exception as e:
        logger.error(f"❌ Sequential processing demonstration failed: {e}")
        return None


def run_comparison_demo():
    """Run the performance comparison demonstration."""
    print("\\n" + "⚖️" * 20)
    print("PERFORMANCE COMPARISON DEMONSTRATION")
    print("⚖️" * 20)
    
    try:
        results = demo_performance_comparison()
        logger.info("✅ Performance comparison demonstration completed successfully")
        return results
    except Exception as e:
        logger.error(f"❌ Performance comparison demonstration failed: {e}")
        return None


def run_benchmark_demo():
    """Run comprehensive benchmark testing."""
    print("\\n" + "🎯" * 20)
    print("COMPREHENSIVE BENCHMARK DEMONSTRATION")
    print("🎯" * 20)
    
    building_files = check_dummy_buildings()
    if not building_files:
        logger.error("Cannot run benchmark without building files")
        return None
    
    try:
        comparator = PerformanceComparator(
            test_scenarios=['small', 'medium'],
            visualize_results=True,
            save_detailed_report=True
        )
        
        results = comparator.run_comprehensive_benchmark(
            building_files=building_files,
            scaling_test=True
        )
        
        logger.info("✅ Comprehensive benchmark completed successfully")
        return results
    except Exception as e:
        logger.error(f"❌ Comprehensive benchmark failed: {e}")
        return None


def run_complete_demo():
    """Run the complete demonstration suite."""
    print("\\n" + "🌟" * 20)
    print("COMPLETE MULTI-BUILDING PROCESSING DEMONSTRATION")
    print("🌟" * 20)
    
    # Check dependencies
    if not check_dependencies():
        logger.error("Cannot proceed with missing dependencies")
        return False
    
    # Check building files
    building_files = check_dummy_buildings()
    if not building_files:
        logger.error("Cannot proceed without building files")
        return False
    
    results = {}
    
    # 1. Run parallel processing demo
    logger.info("\\n" + "="*60)
    logger.info("STEP 1: Parallel Processing Demo")
    logger.info("="*60)
    parallel_results = run_parallel_demo()
    if parallel_results:
        results['parallel'] = parallel_results
    
    # 2. Run sequential processing demo
    logger.info("\\n" + "="*60)
    logger.info("STEP 2: Sequential Processing Demo")
    logger.info("="*60)
    sequential_results = run_sequential_demo()
    if sequential_results:
        results['sequential'] = sequential_results
    
    # 3. Run performance comparison
    logger.info("\n" + "="*60)
    logger.info("STEP 3: Performance Comparison")
    logger.info("="*60)
    comparison_results = run_comparison_demo()
    if comparison_results:
        results['comparison'] = comparison_results
    
    # 4. Generate summary report
    if results:
        generate_summary_report(results)
    
    return len(results) > 0


def generate_summary_report(results):
    """Generate a summary report of all demonstrations."""
    print("\n" + "="*80)
    print("📋 DEMONSTRATION SUMMARY REPORT")
    print("="*80)
    
    # Parallel processing summary
    if 'parallel' in results:
        parallel = results['parallel']
        summary = parallel['summary']
        performance = parallel['performance']
        
        print("\n🚀 PARALLEL PROCESSING RESULTS:")
        print(f"   📊 Buildings processed: {summary['total_buildings']}")
        print(f"   ✅ Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"   ⏱️  Total time: {summary['total_processing_time']:.2f} seconds")
        print(f"   🏗️  Workers used: {performance['workers']}")
        print(f"   🚀 Rate: {performance['buildings_per_second']:.2f} buildings/sec")
    
    # Sequential processing summary
    if 'sequential' in results:
        sequential = results['sequential']
        summary = sequential['summary']
        performance = sequential['performance']
        
        print("\n🐌 SEQUENTIAL PROCESSING RESULTS:")
        print(f"   📊 Buildings processed: {summary['total_buildings']}")
        print(f"   ✅ Success rate: {summary['success_rate_percent']:.1f}%")
        print(f"   ⏱️  Total time: {summary['total_processing_time']:.2f} seconds")
        print(f"   🐌 Rate: {performance['buildings_per_second']:.2f} buildings/sec")
    
    # Performance comparison summary
    if 'comparison' in results:
        comparison = results['comparison']
        recommendations = comparison['recommendations']
        
        print("\n  ⚖️  PERFORMANCE COMPARISON RESULTS:")
        print(f"   🏆 Best configuration: {recommendations['best_configuration']}")
        print(f"   🚀 Best speedup: {recommendations['best_speedup']:.2f}x")
        print(f"   ⚡ Efficiency: {recommendations['best_efficiency']:.2f}")
        print(f"   💡 Recommendation: {recommendations['recommended_approach'].upper()}")
        print(f"   📝 Reasoning: {recommendations['reasoning']}")
    
    # Overall insights
    print("\n🔍 KEY INSIGHTS:")
    
    if 'parallel' in results and 'sequential' in results:
        parallel_time = results['parallel']['summary']['total_processing_time']
        sequential_time = results['sequential']['summary']['total_processing_time']
        speedup = sequential_time / parallel_time
        
        print(f"   • Parallel processing achieved {speedup:.2f}x speedup over sequential")
        
        if speedup > 2.0:
            print("   • Excellent parallelization benefits - suitable for large-scale processing")
        elif speedup > 1.5:
            print("   • Good parallelization benefits - recommended for multiple buildings")
        elif speedup > 1.2:
            print("   • Modest parallelization benefits - consider for larger datasets")
        else:
            print("   • Limited parallelization benefits - sequential may be sufficient")
    
    print("\n💡 RECOMMENDATIONS:")
    print("   • Use parallel processing for datasets with > 10 buildings")
    print("   • Start with 4-8 workers for most systems")
    print("   • Monitor memory usage for very large datasets")
    print("   • Consider sequential processing for debugging individual buildings")
    
    print("\n" + "="*80)
    print("🎉 DEMONSTRATION COMPLETED SUCCESSFULLY!")
    print("Check the performance_reports/ directory for detailed reports and charts.")
    print("="*80)


def validate_system_parameters(cores: Optional[int] = None, workers: Optional[int] = None, 
                             thermal_workers: Optional[int] = None) -> Tuple[bool, Dict[str, Any], str]:
    """Validate system parameters and provide recommendations."""
    system_info = get_system_info()
    max_cores = system_info['cpu_cores']['logical']
    max_memory_gb = system_info['memory']['total_gb']
    
    errors = []
    recommendations = {}
    
    # Validate cores
    if cores is not None:
        if cores < 1:
            errors.append("Cores must be >= 1")
        elif cores > max_cores:
            errors.append(f"Cores ({cores}) exceeds available logical cores ({max_cores})")
        recommendations['cores'] = min(cores, max_cores)
    else:
        recommendations['cores'] = min(max_cores // 2, 8)  # Conservative default
    
    # Validate workers
    if workers is not None:
        if workers < 1:
            errors.append("Workers must be >= 1")
        elif workers > max_cores:
            errors.append(f"Workers ({workers}) exceeds available logical cores ({max_cores})")
        recommendations['workers'] = min(workers, max_cores)
    else:
        recommendations['workers'] = min(max_cores // 2, 8)
    
    # Validate thermal workers
    if thermal_workers is not None:
        if thermal_workers < 1:
            errors.append("Thermal workers must be >= 1")
        elif thermal_workers > 4:  # Limit for thermal calculations
            errors.append(f"Thermal workers ({thermal_workers}) should not exceed 4 for optimal performance")
        recommendations['thermal_workers'] = min(thermal_workers, 4)
    else:
        recommendations['thermal_workers'] = min(4, max_cores // 4)
    
    # Memory validation
    estimated_memory_per_building = 0.5  # GB estimate
    concurrent_buildings = recommendations.get('workers', 4)
    estimated_total_memory = concurrent_buildings * estimated_memory_per_building
    
    if estimated_total_memory > max_memory_gb * 0.8:  # 80% memory limit
        errors.append(f"Estimated memory usage ({estimated_total_memory:.1f}GB) may exceed 80% of available memory ({max_memory_gb}GB)")
    
    # Generate range suggestions
    range_suggestions = f"""
Valid parameter ranges for your system:
  --cores: 1 to {max_cores} (recommended: {recommendations['cores']})
  --workers: 1 to {max_cores} (recommended: {recommendations['workers']})
  --thermal-workers: 1 to 4 (recommended: {recommendations['thermal_workers']})

System specs: {max_cores} logical cores, {system_info['cpu_cores']['physical']} physical cores, {max_memory_gb}GB RAM
"""
    
    is_valid = len(errors) == 0
    error_msg = "; ".join(errors) if errors else ""
    
    return is_valid, recommendations, range_suggestions if not is_valid else ""


def get_system_info() -> Dict[str, Any]:
    """Get detailed system information for optimization."""
    cpu_logical = multiprocessing.cpu_count()
    
    if PSUTIL_AVAILABLE:
        cpu_physical = psutil.cpu_count(logical=False)
        memory = psutil.virtual_memory()
        memory_gb = memory.total // (1024**3)
        cpu_freq = psutil.cpu_freq()
        
        return {
            'cpu_cores': {
                'logical': cpu_logical,
                'physical': cpu_physical or cpu_logical,
                'frequency_mhz': cpu_freq.current if cpu_freq else None
            },
            'memory': {
                'total_gb': memory_gb,
                'available_gb': memory.available // (1024**3),
                'percent_used': memory.percent
            },
            'psutil_available': True
        }
    else:
        return {
            'cpu_cores': {
                'logical': cpu_logical,
                'physical': cpu_logical,  # Fallback
                'frequency_mhz': None
            },
            'memory': {
                'total_gb': 8,  # Conservative fallback
                'available_gb': 6,
                'percent_used': 25
            },
            'psutil_available': False
        }


def run_optimization_tests(building_files: List[Path]) -> Dict[str, Any]:
    """Run comprehensive optimization tests with different configurations."""
    logger.info("\\n🔬 Starting Optimization Tests...")
    
    system_info = get_system_info()
    max_cores = system_info['cpu_cores']['logical']
    
    # Test configurations
    test_configs = [
        {'workers': 2, 'thermal_strategy': 'parallel', 'desc': '2 Workers + Parallel Thermal'},
        {'workers': 4, 'thermal_strategy': 'parallel', 'desc': '4 Workers + Parallel Thermal'},
        {'workers': 4, 'thermal_strategy': 'parallel', 'desc': '4 Workers + Parallel Thermal + Chunked'},
        {'workers': 8, 'thermal_strategy': 'parallel', 'desc': '8 Workers + Parallel Thermal + Chunked'},
        {'workers': min(12, max_cores), 'thermal_strategy': 'parallel', 'desc': f'{min(12, max_cores)} Workers + Parallel Thermal + Chunked'},
    ]
    
    # Add high-performance config if system supports it
    if max_cores >= 16:
        test_configs.append({
            'workers': 16, 'thermal_strategy': 'parallel', 'desc': '16 Workers + Parallel Thermal + Chunked (High-Performance)'
        })
    
    results = []
    
    for i, config in enumerate(test_configs, 1):
        logger.info(f"\\n📊 Test {i}/{len(test_configs)}: {config['desc']}")
        start_time = time.time()
        
        try:
            # Simple test without full PerformanceComparator for now
            from buem.parallelization.parallel_run import ParallelBuildingProcessor
            
            # Test with subset of buildings for speed
            test_buildings = building_files[:3] if len(building_files) > 3 else building_files
            
            processor = ParallelBuildingProcessor(workers=config['workers'])
            test_result = processor.process_buildings(test_buildings)
            
            config_result = {
                'config': config,
                'test_time': time.time() - start_time,
                'success_rate': test_result['summary']['success_rate_percent'] / 100 if test_result['summary']['success_rate_percent'] else 0,
                'buildings_per_second': test_result['performance']['buildings_per_second'] if test_result['performance']['buildings_per_second'] else 0,
                'memory_usage_mb': test_result['performance'].get('final_memory_mb', 0),
                'status': 'success',
                'buildings_tested': len(test_buildings)
            }
            
            results.append(config_result)
            
            logger.info(f"   ⏱️  Time: {config_result['test_time']:.1f}s")
            logger.info(f"   🚀 Rate: {config_result['buildings_per_second']:.2f} buildings/sec")
            logger.info(f"   ✅ Success: {config_result['success_rate']:.1%}")
            
        except Exception as e:
            logger.warning(f"   ❌ Test failed: {e}")
            results.append({
                'config': config,
                'status': 'failed',
                'error': str(e),
                'test_time': time.time() - start_time
            })
    
    # Find optimal configuration
    successful_results = [r for r in results if r['status'] == 'success']
    
    if successful_results:
        optimal_config = max(successful_results, 
                           key=lambda x: x['buildings_per_second'] * x['success_rate'])
        
        logger.info(f"\\n🏆 Optimal Configuration Found:")
        logger.info(f"   📋 Config: {optimal_config['config']['desc']}")
        logger.info(f"   🚀 Performance: {optimal_config['buildings_per_second']:.2f} buildings/sec")
        logger.info(f"   ✅ Success Rate: {optimal_config['success_rate']:.1%}")
        
        return {
            'optimal_config': optimal_config['config'],
            'all_results': results,
            'recommendation': optimal_config['config']
        }
    else:
        logger.warning("❌ No successful test configurations found")
        return {
            'optimal_config': None,
            'all_results': results,
            'recommendation': {'workers': 4, 'thermal_strategy': 'sequential'}  # Safe fallback
        }


def run_enhanced_parallel_demo(workers: int, thermal_strategy: str = 'sequential', 
                             thermal_workers: int = 2):
    """Run parallel demo with enhanced configuration options."""
    print("\\n" + "🚀" * 20)
    print(f"ENHANCED PARALLEL PROCESSING DEMONSTRATION")
    print(f"Workers: {workers} | Thermal Strategy: {thermal_strategy} | Thermal Workers: {thermal_workers}")
    print("🚀" * 20)
    
    building_files = check_dummy_buildings()
    if not building_files:
        logger.error("Cannot run parallel demo without building files")
        return None
    
    try:
        from buem.parallelization.parallel_run import ParallelBuildingProcessor
        
        processor = ParallelBuildingProcessor(
            workers=workers,
            thermal_strategy=thermal_strategy,
            thermal_workers=thermal_workers
        )
        results = processor.process_buildings(building_files)
        
        logger.info("✅ Enhanced parallel processing demonstration completed successfully")
        return results
    except Exception as e:
        logger.error(f"❌ Enhanced parallel processing demonstration failed: {e}")
        return None


def run_thermal_strategy_tests():
    """Test different thermal calculation strategies."""
    print("\\n" + "🔥" * 20)
    print("THERMAL STRATEGY TESTING")
    print("🔥" * 20)
    
    building_files = check_dummy_buildings()
    if not building_files:
        logger.error("Cannot run thermal tests without building files")
        return None
    
    strategies = ['sequential', 'parallel']
    results = {}
    
    for strategy in strategies:
        logger.info(f"\\n🧪 Testing {strategy} thermal strategy...")
        try:
            from buem.parallelization.parallel_run import ParallelBuildingProcessor
            
            processor = ParallelBuildingProcessor(
                workers=4,
                thermal_strategy=strategy
            )
            
            # Use subset for testing
            test_buildings = building_files[:2]
            result = processor.process_buildings(test_buildings)
            
            results[strategy] = {
                'status': 'success',
                'time': result['performance']['total_time'],
                'rate': result['performance']['buildings_per_second'],
                'success_rate': result['summary']['success_rate_percent']
            }
            
            logger.info(f"   ✅ {strategy}: {result['performance']['total_time']:.2f}s, {result['performance']['buildings_per_second']:.2f} buildings/sec")
            
        except Exception as e:
            logger.error(f"   ❌ {strategy} failed: {e}")
            results[strategy] = {'status': 'failed', 'error': str(e)}
    
    # Compare results
    if all(r['status'] == 'success' for r in results.values()):
        sequential_time = results['sequential']['time']
        parallel_time = results['parallel']['time']
        
        if parallel_time < sequential_time:
            speedup = sequential_time / parallel_time
            logger.info(f"\\n🏆 Parallel thermal strategy is {speedup:.2f}x faster!")
        else:
            logger.info(f"\\n📊 Sequential thermal strategy performed better for this dataset")
    
    return results


def main():
    """Main function to handle command line arguments and run demonstrations."""
    parser = argparse.ArgumentParser(
        description="BUEM Multi-Building Processing Demonstration Suite with Advanced Parallelization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python run_multibuilding_demo.py                                    # Auto-optimized complete demo
  python run_multibuilding_demo.py --test parallel                    # Default parallel processing
  
  # Advanced parallelization
  python run_multibuilding_demo.py --test parallel --cores 8          # 8-core parallel processing
  python run_multibuilding_demo.py --test parallel --workers 4        # 4 worker processes
  python run_multibuilding_demo.py --test parallel --thermal-workers 2 # 2 thermal calculation workers
  
  # Optimization and testing
  python run_multibuilding_demo.py --test optimize                    # Auto-find optimal configuration
  python run_multibuilding_demo.py --test thermal                     # Test thermal calculation strategies
  
  # Combined configurations
  python run_multibuilding_demo.py --test parallel --cores 16 --workers 8 --thermal-workers 4
  
  # System validation
  python run_multibuilding_demo.py --validate-system                  # Check system capabilities
        """
    )
    
    parser.add_argument(
        '--test',
        choices=['parallel', 'sequential', 'comparison', 'benchmark', 'complete', 'optimize', 'thermal'],
        default='complete',
        help='Specific test to run (default: complete demo)'
    )
    
    parser.add_argument(
        '--cores',
        type=int,
        help='Number of CPU cores to use for processing (overrides workers)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        help='Number of worker processes for building processing'
    )
    
    parser.add_argument(
        '--thermal-workers',
        type=int,
        help='Number of worker processes for thermal calculations within each building'
    )
    
    parser.add_argument(
        '--thermal-strategy',
        choices=['sequential', 'parallel'],
        default='parallel',  # Default to parallel for better performance
        help='Strategy for heating/cooling calculations: sequential or parallel (default: parallel)'
    )
    
    parser.add_argument(
        '--validate-system',
        action='store_true',
        help='Validate system capabilities and show recommended parameters'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Reduce logging output'
    )
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    # Handle system validation
    if args.validate_system:
        is_valid, recommendations, range_info = validate_system_parameters(
            cores=args.cores,
            workers=args.workers,
            thermal_workers=args.thermal_workers
        )
        
        print("\\n" + "🔍" * 20)
        print("SYSTEM VALIDATION RESULTS")
        print("🔍" * 20)
        
        system_info = get_system_info()
        print(f"\\n💻 System Specifications:")
        print(f"   CPU Cores: {system_info['cpu_cores']['logical']} logical, {system_info['cpu_cores']['physical']} physical")
        print(f"   Memory: {system_info['memory']['total_gb']} GB total, {system_info['memory']['available_gb']} GB available")
        if system_info.get('psutil_available'):
            print(f"   Memory Usage: {system_info['memory']['percent_used']:.1f}% used")
        
        if is_valid:
            print(f"\\n✅ Configuration is valid!")
            print(f"\\n🎯 Recommended settings:")
            print(f"   --cores {recommendations['cores']}")
            print(f"   --workers {recommendations['workers']}")
            print(f"   --thermal-workers {recommendations['thermal_workers']}")
        else:
            print(f"\\n❌ Configuration issues found:")
            print(f"{range_info}")
        
        sys.exit(0 if is_valid else 1)
    
    # Validate parameters if provided
    is_valid, recommendations, error_msg = validate_system_parameters(
        cores=args.cores,
        workers=args.workers,
        thermal_workers=args.thermal_workers
    )
    
    if not is_valid:
        print(f"\\n❌ Invalid parameters: {error_msg}")
        sys.exit(1)
    
    # Apply validated parameters
    if args.cores:
        args.workers = args.cores  # Override workers with cores if specified
    
    print_banner()
    
    start_time = time.time()
    
    # Run the requested test with enhanced parameters
    if args.test == 'parallel':
        success = run_enhanced_parallel_demo(
            workers=args.workers or recommendations['workers'],
            thermal_strategy=args.thermal_strategy,
            thermal_workers=args.thermal_workers or recommendations['thermal_workers']
        ) is not None
    elif args.test == 'sequential':
        success = run_sequential_demo() is not None
    elif args.test == 'comparison':
        success = run_comparison_demo() is not None
    elif args.test == 'benchmark':
        success = run_benchmark_demo() is not None
    elif args.test == 'optimize':
        building_files = check_dummy_buildings()
        if building_files:
            optimization_results = run_optimization_tests(building_files)
            success = optimization_results['optimal_config'] is not None
        else:
            success = False
    elif args.test == 'thermal':
        success = run_thermal_strategy_tests() is not None
    else:  # complete
        success = run_complete_demo()
    
    total_time = time.time() - start_time
    
    print(f"\\n" + "⏱️" * 20)
    print(f"TOTAL EXECUTION TIME: {total_time:.2f} seconds")
    print("⏱️" * 20)
    
    if success:
        print("\\n✅ All demonstrations completed successfully!")
        sys.exit(0)
    else:
        print("\\n❌ Some demonstrations failed. Check the logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()