#!/usr/bin/env python3
"""
Building Processing Performance Comparison Module for BUEM

This module provides comprehensive performance comparison between parallel and sequential
building processing approaches. It includes benchmarking, analysis, and reporting
capabilities to help determine the optimal processing strategy for different scenarios.

Key Features:
- Head-to-head comparison of parallel vs sequential processing
- Detailed performance metrics collection and analysis
- Memory usage profiling and optimization recommendations
- Scalability analysis with varying building counts
- Performance visualization and reporting
- Automated recommendation generation
- Batch testing with different configurations

Usage:
    # Basic comparison
    from performance_comparison import PerformanceComparator
    
    comparator = PerformanceComparator()
    results = comparator.compare_processing_methods(building_files)
    
    # Advanced benchmarking
    comparator = PerformanceComparator(
        test_scenarios=['small', 'medium', 'large'],
        visualize_results=True,
        save_detailed_report=True
    )
    benchmark_results = comparator.run_comprehensive_benchmark()

Performance Insights:
- Processing time comparison (parallel vs sequential)
- Memory usage analysis
- CPU utilization metrics
- Scalability characteristics
- Optimal worker count determination
- Bottleneck identification
"""

import json
import time
import logging
import psutil
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timezone
import sys
import os

# Add the project root to Python path for imports
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root / "src"))

try:
    from buem.parallelization.parallel_run import ParallelBuildingProcessor
    from buem.parallelization.sequence_run import SequentialBuildingProcessor
except ImportError as e:
    print(f"Error importing processing modules: {e}")
    print("Make sure parallel_run.py and sequence_run.py are in the parallelization folder.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Optional imports for visualization
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available - visualization features will be limited")


class PerformanceComparator:
    """
    Comprehensive performance comparison system for building processing methods.
    
    This class orchestrates performance testing between parallel and sequential
    processing approaches, collecting detailed metrics and generating insights
    for optimization.
    
    Attributes
    ----------
    test_scenarios : List[str]
        List of test scenarios to run ['small', 'medium', 'large']
    max_workers : int
        Maximum number of workers for parallel processing tests
    visualize_results : bool
        Generate performance visualizations
    save_detailed_report : bool
        Save comprehensive performance report
    """
    
    def __init__(
        self,
        test_scenarios: List[str] = None,
        max_workers: int = None,
        visualize_results: bool = True,
        save_detailed_report: bool = True,
        output_dir: str = "performance_reports"
    ):
        """
        Initialize the performance comparator.
        
        Parameters
        ----------
        test_scenarios : List[str], optional
            Scenarios to test. Options: 'small', 'medium', 'large', 'xlarge'
        max_workers : int, optional
            Maximum workers for parallel testing (default: CPU count)
        visualize_results : bool
            Generate performance charts (default: True)
        save_detailed_report : bool
            Save detailed analysis report (default: True)
        output_dir : str
            Directory for saving reports and charts (default: "performance_reports")
        """
        self.test_scenarios = test_scenarios or ['small', 'medium']
        self.max_workers = max_workers or max(1, psutil.cpu_count() - 1)
        self.visualize_results = visualize_results and MATPLOTLIB_AVAILABLE
        self.save_detailed_report = save_detailed_report
        
        # Create output directory
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # System information
        self.system_info = self._collect_system_info()
        
        logger.info(f"Initialized PerformanceComparator")
        logger.info(f"Test scenarios: {self.test_scenarios}")
        logger.info(f"Max workers: {self.max_workers}")
        logger.info(f"CPU cores: {psutil.cpu_count()} (logical: {psutil.cpu_count(logical=True)})")
        logger.info(f"Available memory: {psutil.virtual_memory().total / (1024**3):.1f} GB")
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information for benchmarking context."""
        try:
            sys_info = {
                'cpu_count_physical': psutil.cpu_count(logical=False),
                'cpu_count_logical': psutil.cpu_count(logical=True),
                'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                'platform': sys.platform,
                'python_version': sys.version,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            return sys_info
        except Exception as e:
            logger.warning(f"Could not collect system info: {e}")
            return {'error': str(e)}
    
    def compare_processing_methods(
        self,
        building_files: List[Union[str, Path]],
        worker_counts: List[int] = None
    ) -> Dict[str, Any]:
        """
        Compare parallel and sequential processing on the same dataset.
        
        Parameters
        ----------
        building_files : List[Union[str, Path]]
            List of building configuration files to process
        worker_counts : List[int], optional
            List of worker counts to test for parallel processing
            
        Returns
        -------
        Dict[str, Any]
            Comparison results with performance metrics
        """
        if not building_files:
            raise ValueError("No building files provided for comparison")
        
        worker_counts = worker_counts or [1, 2, 4, self.max_workers]
        worker_counts = [w for w in worker_counts if w <= self.max_workers]
        
        logger.info(f"Starting performance comparison with {len(building_files)} buildings")
        logger.info(f"Testing worker counts: {worker_counts}")
        
        comparison_results = {
            'test_info': {
                'building_count': len(building_files),
                'worker_counts_tested': worker_counts,
                'test_timestamp': datetime.now(timezone.utc).isoformat()
            },
            'system_info': self.system_info,
            'results': {}
        }
        
        # Run sequential processing (baseline)
        logger.info("\\n" + "="*50)
        logger.info("RUNNING SEQUENTIAL PROCESSING (BASELINE)")
        logger.info("="*50)
        
        sequential_processor = SequentialBuildingProcessor(
            detailed_logging=False,  # Reduce log noise for comparison
            memory_monitoring=True
        )
        
        sequential_start = time.time()
        sequential_results = sequential_processor.process_buildings(
            building_files=building_files,
            save_results=False
        )
        sequential_total_time = time.time() - sequential_start
        
        comparison_results['results']['sequential'] = {
            'performance': sequential_results['performance'],
            'summary': sequential_results['summary'],
            'actual_total_time': sequential_total_time
        }
        
        # Run parallel processing with different worker counts
        parallel_results = {}
        
        for worker_count in worker_counts:
            logger.info(f"\\n" + "="*50)
            logger.info(f"RUNNING PARALLEL PROCESSING ({worker_count} WORKERS)")
            logger.info("="*50)
            
            parallel_processor = ParallelBuildingProcessor(
                workers=worker_count,
                chunk_size=max(1, len(building_files) // worker_count)
            )
            
            parallel_start = time.time()
            parallel_result = parallel_processor.process_buildings(
                building_files=building_files,
                save_results=False
            )
            parallel_total_time = time.time() - parallel_start
            
            parallel_results[f"parallel_{worker_count}w"] = {
                'workers': worker_count,
                'performance': parallel_result['performance'],
                'summary': parallel_result['summary'],
                'actual_total_time': parallel_total_time,
                'speedup_vs_sequential': sequential_total_time / parallel_total_time,
                'efficiency': (sequential_total_time / parallel_total_time) / worker_count
            }
        
        comparison_results['results']['parallel'] = parallel_results
        
        # Calculate best performing configuration
        best_config = self._find_best_configuration(comparison_results)
        comparison_results['recommendations'] = best_config
        
        # Generate performance summary
        summary = self._generate_performance_summary(comparison_results)
        comparison_results['analysis_summary'] = summary
        
        # Save results if requested
        if self.save_detailed_report:
            self._save_comparison_report(comparison_results)
        
        # Generate visualizations if requested
        if self.visualize_results:
            self._create_performance_visualizations(comparison_results)
        
        return comparison_results
    
    def run_comprehensive_benchmark(
        self,
        building_files: List[Union[str, Path]] = None,
        scaling_test: bool = True
    ) -> Dict[str, Any]:
        """
        Run comprehensive benchmarking across multiple scenarios.
        
        Parameters
        ----------
        building_files : List[Union[str, Path]], optional
            Building files to use. If None, uses dummy files
        scaling_test : bool
            Whether to run scaling tests with different building counts
            
        Returns
        -------
        Dict[str, Any]
            Comprehensive benchmark results
        """
        if building_files is None:
            # Find dummy building files
            dummy_dir = Path(__file__).parent.parent / "integration/json_schema/versions/v2/dummy"
            building_files = list(dummy_dir.glob("*.json"))
            
            if not building_files:
                raise FileNotFoundError(f"No dummy building files found in {dummy_dir}")
        
        logger.info("\\n" + "="*60)
        logger.info("STARTING COMPREHENSIVE BENCHMARK")
        logger.info("="*60)
        
        benchmark_results = {
            'benchmark_info': {
                'scenarios_tested': self.test_scenarios,
                'total_building_files': len(building_files),
                'scaling_test_enabled': scaling_test,
                'benchmark_timestamp': datetime.now(timezone.utc).isoformat()
            },
            'system_info': self.system_info,
            'scenario_results': {}
        }
        
        scenario_configs = {
            'small': {'count': min(3, len(building_files)), 'workers': [1, 2]},
            'medium': {'count': min(5, len(building_files)), 'workers': [1, 2, 4]},
            'large': {'count': len(building_files), 'workers': [1, 2, 4, 8]},
            'xlarge': {'count': len(building_files) * 2, 'workers': [1, 4, 8, 16]}  # Duplicated files
        }
        
        for scenario in self.test_scenarios:
            if scenario not in scenario_configs:
                logger.warning(f"Unknown scenario: {scenario}")
                continue
            
            config = scenario_configs[scenario]
            
            # Prepare building files for this scenario
            if scenario == 'xlarge':
                # Duplicate files to create larger dataset
                test_files = (building_files * 2)[:config['count']]
            else:
                test_files = building_files[:config['count']]
            
            logger.info(f"\\n" + "-"*40)
            logger.info(f"TESTING SCENARIO: {scenario.upper()} ({len(test_files)} buildings)")
            logger.info("-"*40)
            
            # Filter worker counts based on availability
            available_workers = [w for w in config['workers'] if w <= self.max_workers]
            
            scenario_result = self.compare_processing_methods(
                building_files=test_files,
                worker_counts=available_workers
            )
            
            benchmark_results['scenario_results'][scenario] = scenario_result
        
        # Generate overall analysis
        overall_analysis = self._analyze_benchmark_results(benchmark_results)
        benchmark_results['overall_analysis'] = overall_analysis
        
        # Save comprehensive report
        if self.save_detailed_report:
            self._save_benchmark_report(benchmark_results)
        
        # Create comprehensive visualizations
        if self.visualize_results:
            self._create_benchmark_visualizations(benchmark_results)
        
        return benchmark_results
    
    def _find_best_configuration(self, comparison_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze results and recommend best configuration."""
        sequential_time = comparison_results['results']['sequential']['actual_total_time']
        parallel_results = comparison_results['results']['parallel']
        
        best_parallel = None
        best_speedup = 0
        best_efficiency = 0
        
        for config_name, result in parallel_results.items():
            speedup = result['speedup_vs_sequential']
            efficiency = result['efficiency']
            
            if speedup > best_speedup:
                best_speedup = speedup
                best_parallel = config_name
                best_efficiency = efficiency
        
        recommendations = {
            'best_configuration': best_parallel,
            'best_speedup': best_speedup,
            'best_efficiency': best_efficiency,
            'sequential_time': sequential_time,
            'recommended_approach': 'parallel' if best_speedup > 1.2 else 'sequential',
            'reasoning': self._generate_recommendation_reasoning(
                best_speedup, best_efficiency, sequential_time
            )
        }
        
        return recommendations
    
    def _generate_recommendation_reasoning(
        self, best_speedup: float, best_efficiency: float, sequential_time: float
    ) -> str:
        """Generate human-readable reasoning for recommendations."""
        if best_speedup < 1.1:
            return ("Sequential processing is recommended. Parallel processing overhead "
                   "exceeds benefits for this dataset size.")
        elif best_speedup < 1.5:
            return ("Parallel processing provides modest benefits. Consider sequential "
                   "processing for simplicity unless processing larger datasets.")
        elif best_efficiency > 0.7:
            return ("Parallel processing is highly recommended with excellent efficiency. "
                   "Significant speedup with good resource utilization.")
        else:
            return ("Parallel processing provides good speedup but with diminishing returns. "
                   "Consider reducing worker count for better efficiency.")
    
    def _generate_performance_summary(self, comparison_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate human-readable performance summary."""
        sequential = comparison_results['results']['sequential']
        parallel_results = comparison_results['results']['parallel']
        
        summary = {
            'sequential_performance': {
                'total_time': sequential['actual_total_time'],
                'buildings_per_second': sequential['performance']['buildings_per_second'],
                'success_rate': sequential['summary']['success_rate_percent']
            },
            'parallel_performance': {},
            'key_insights': []
        }
        
        # Analyze parallel results
        for config_name, result in parallel_results.items():
            workers = result['workers']
            summary['parallel_performance'][config_name] = {
                'workers': workers,
                'total_time': result['actual_total_time'],
                'speedup': result['speedup_vs_sequential'],
                'efficiency': result['efficiency'],
                'buildings_per_second': result['performance']['buildings_per_second']
            }
        
        # Generate insights
        speedups = [r['speedup_vs_sequential'] for r in parallel_results.values()]
        max_speedup = max(speedups)
        avg_speedup = statistics.mean(speedups)
        
        summary['key_insights'].append(f"Maximum speedup achieved: {max_speedup:.2f}x")
        summary['key_insights'].append(f"Average speedup across configurations: {avg_speedup:.2f}x")
        
        if max_speedup > 2.0:
            summary['key_insights'].append("Excellent parallelization potential - consider larger datasets")
        elif max_speedup > 1.5:
            summary['key_insights'].append("Good parallelization benefits observed")
        else:
            summary['key_insights'].append("Limited parallelization benefits - evaluate dataset size")
        
        return summary
    
    def _analyze_benchmark_results(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze benchmark results across all scenarios."""
        analysis = {
            'scaling_characteristics': {},
            'optimal_configurations': {},
            'performance_trends': {},
            'recommendations_by_scale': {}
        }
        
        # Analyze scaling by scenario
        for scenario, results in benchmark_results['scenario_results'].items():
            building_count = results['test_info']['building_count']
            sequential_time = results['results']['sequential']['actual_total_time']
            
            best_parallel = None
            best_speedup = 0
            
            for config_name, parallel_result in results['results']['parallel'].items():
                speedup = parallel_result['speedup_vs_sequential']
                if speedup > best_speedup:
                    best_speedup = speedup
                    best_parallel = config_name
            
            analysis['scaling_characteristics'][scenario] = {
                'building_count': building_count,
                'sequential_time': sequential_time,
                'best_speedup': best_speedup,
                'best_configuration': best_parallel
            }
        
        return analysis
    
    def _save_comparison_report(self, comparison_results: Dict[str, Any]):
        """Save detailed comparison report to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.output_dir / f"performance_comparison_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(comparison_results, f, indent=2, default=str)
        
        logger.info(f"Performance comparison report saved: {report_file}")
    
    def _save_benchmark_report(self, benchmark_results: Dict[str, Any]):
        """Save comprehensive benchmark report to file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = self.output_dir / f"comprehensive_benchmark_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(benchmark_results, f, indent=2, default=str)
        
        logger.info(f"Comprehensive benchmark report saved: {report_file}")
    
    def _create_performance_visualizations(self, comparison_results: Dict[str, Any]):
        """Create performance visualization charts."""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available - skipping visualizations")
            return
        
        try:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
            
            # Extract data
            sequential_time = comparison_results['results']['sequential']['actual_total_time']
            parallel_results = comparison_results['results']['parallel']
            
            worker_counts = []
            processing_times = []
            speedups = []
            efficiencies = []
            
            for config_name, result in parallel_results.items():
                worker_counts.append(result['workers'])
                processing_times.append(result['actual_total_time'])
                speedups.append(result['speedup_vs_sequential'])
                efficiencies.append(result['efficiency'])
            
            # Sort by worker count for better visualization
            sorted_data = sorted(zip(worker_counts, processing_times, speedups, efficiencies))
            worker_counts, processing_times, speedups, efficiencies = zip(*sorted_data)
            
            # Chart 1: Processing Time Comparison
            ax1.bar(['Sequential'] + [f'{w} workers' for w in worker_counts], 
                   [sequential_time] + list(processing_times),
                   color=['red'] + ['blue'] * len(worker_counts))
            ax1.set_title('Processing Time by Configuration')
            ax1.set_ylabel('Time (seconds)')
            ax1.tick_params(axis='x', rotation=45)
            
            # Chart 2: Speedup vs Worker Count
            ax2.plot(worker_counts, speedups, 'o-', color='green', linewidth=2, markersize=8)
            ax2.axhline(y=1.0, color='red', linestyle='--', label='Baseline (Sequential)')
            ax2.set_title('Speedup vs Worker Count')
            ax2.set_xlabel('Number of Workers')
            ax2.set_ylabel('Speedup Factor')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Chart 3: Efficiency vs Worker Count
            ax3.plot(worker_counts, efficiencies, 's-', color='orange', linewidth=2, markersize=8)
            ax3.axhline(y=1.0, color='red', linestyle='--', label='Perfect Efficiency')
            ax3.set_title('Parallel Efficiency vs Worker Count')
            ax3.set_xlabel('Number of Workers')
            ax3.set_ylabel('Efficiency (Speedup / Workers)')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # Chart 4: Buildings per Second
            buildings_per_sec = [comparison_results['results']['sequential']['performance']['buildings_per_second']]
            for config_name, result in parallel_results.items():
                buildings_per_sec.append(result['performance']['buildings_per_second'])
            
            ax4.bar(['Sequential'] + [f'{w}w' for w in worker_counts], 
                   buildings_per_sec,
                   color=['red'] + ['purple'] * len(worker_counts))
            ax4.set_title('Processing Rate by Configuration')
            ax4.set_ylabel('Buildings/Second')
            ax4.tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            # Save chart
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            chart_file = self.output_dir / f"performance_comparison_charts_{timestamp}.png"
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Performance visualization saved: {chart_file}")
            
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}")
    
    def _create_benchmark_visualizations(self, benchmark_results: Dict[str, Any]):
        """Create comprehensive benchmark visualization charts."""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available - skipping benchmark visualizations")
            return
        
        try:
            # Create scaling analysis chart
            scenarios = []
            building_counts = []
            best_speedups = []
            sequential_times = []
            
            for scenario, results in benchmark_results['scenario_results'].items():
                scenarios.append(scenario.capitalize())
                building_counts.append(results['test_info']['building_count'])
                best_speedup = max([r['speedup_vs_sequential'] for r in results['results']['parallel'].values()])
                best_speedups.append(best_speedup)
                sequential_times.append(results['results']['sequential']['actual_total_time'])
            
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Speedup by scenario
            bars1 = ax1.bar(scenarios, best_speedups, color='skyblue', edgecolor='navy')
            ax1.axhline(y=1.0, color='red', linestyle='--', label='No Speedup')
            ax1.set_title('Best Speedup by Scenario')
            ax1.set_ylabel('Best Speedup Factor')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for bar, value in zip(bars1, best_speedups):
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                        f'{value:.2f}x', ha='center', va='bottom')
            
            # Processing time by scenario
            bars2 = ax2.bar(scenarios, sequential_times, color='lightcoral', edgecolor='darkred')
            ax2.set_title('Sequential Processing Time by Scenario')
            ax2.set_ylabel('Time (seconds)')
            ax2.grid(True, alpha=0.3)
            
            # Add value labels on bars
            for bar, value in zip(bars2, sequential_times):
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                        f'{value:.1f}s', ha='center', va='bottom')
            
            plt.tight_layout()
            
            # Save chart
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            chart_file = self.output_dir / f"benchmark_analysis_{timestamp}.png"
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Benchmark visualization saved: {chart_file}")
            
        except Exception as e:
            logger.error(f"Error creating benchmark visualizations: {e}")


def demo_performance_comparison():
    """
    Demonstrate the performance comparison functionality.
    
    This function shows how to use the PerformanceComparator to evaluate
    parallel vs sequential processing performance.
    """
    print("\\n" + "="*70)
    print("BUEM PERFORMANCE COMPARISON DEMONSTRATION")
    print("="*70)
    
    # Find dummy building files
    dummy_dir = Path(__file__).parent.parent / "integration/json_schema/versions/v2/dummy"
    building_files = list(dummy_dir.glob("*.json"))
    
    if not building_files:
        logger.error(f"No building files found in {dummy_dir}")
        return
    
    logger.info(f"Found {len(building_files)} building files for performance comparison")
    
    # Create performance comparator
    comparator = PerformanceComparator(
        test_scenarios=['small', 'medium'],
        visualize_results=True,
        save_detailed_report=True
    )
    
    # Run basic comparison
    print("\\n" + "-"*50)
    print("RUNNING BASIC PERFORMANCE COMPARISON")
    print("-"*50)
    
    comparison_results = comparator.compare_processing_methods(
        building_files=building_files,
        worker_counts=[1, 2, 4]
    )
    
    # Display results
    print("\\n" + "="*50)
    print("PERFORMANCE COMPARISON RESULTS")
    print("="*50)
    
    recommendations = comparison_results['recommendations']
    print(f"🏆 Best Configuration: {recommendations['best_configuration']}")
    print(f"🚀 Best Speedup: {recommendations['best_speedup']:.2f}x")
    print(f"⚡ Efficiency: {recommendations['best_efficiency']:.2f}")
    print(f"💡 Recommended Approach: {recommendations['recommended_approach'].upper()}")
    print(f"📝 Reasoning: {recommendations['reasoning']}")
    
    # Show detailed metrics
    analysis = comparison_results['analysis_summary']
    sequential_perf = analysis['sequential_performance']
    
    print(f"\\n📊 Sequential Performance:")
    print(f"   ⏱️  Total time: {sequential_perf['total_time']:.2f} seconds")
    print(f"   🏢 Rate: {sequential_perf['buildings_per_second']:.2f} buildings/sec")
    print(f"   ✅ Success rate: {sequential_perf['success_rate']:.1f}%")
    
    print(f"\\n📊 Parallel Performance Comparison:")
    for config, perf in analysis['parallel_performance'].items():
        print(f"   {config}: {perf['workers']} workers")
        print(f"      🚀 Speedup: {perf['speedup']:.2f}x")
        print(f"      ⚡ Efficiency: {perf['efficiency']:.2f}")
        print(f"      🏢 Rate: {perf['buildings_per_second']:.2f} buildings/sec")
        print()
    
    # Show key insights
    print("🔍 Key Insights:")
    for insight in analysis['key_insights']:
        print(f"   • {insight}")
    
    # Run comprehensive benchmark if there are enough buildings
    if len(building_files) >= 3:
        print("\\n" + "-"*50)
        print("RUNNING COMPREHENSIVE BENCHMARK")
        print("-"*50)
        
        benchmark_results = comparator.run_comprehensive_benchmark(
            building_files=building_files,
            scaling_test=True
        )
        
        print("\\n" + "="*50)
        print("COMPREHENSIVE BENCHMARK RESULTS")
        print("="*50)
        
        for scenario, results in benchmark_results['scenario_results'].items():
            building_count = results['test_info']['building_count']
            recommendations = results['recommendations']
            
            print(f"\\n🎯 {scenario.upper()} Scenario ({building_count} buildings):")
            print(f"   🏆 Best Config: {recommendations['best_configuration']}")
            print(f"   🚀 Speedup: {recommendations['best_speedup']:.2f}x")
            print(f"   💡 Recommended: {recommendations['recommended_approach'].upper()}")
    
    return comparison_results


if __name__ == "__main__":
    # Run the demonstration
    demo_performance_comparison()