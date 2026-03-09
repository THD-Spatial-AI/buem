#!/usr/bin/env python3
"""
BUEM Multi-Building Performance Analyzer

Focused analysis script to understand multi-building performance bottlenecks
without complex time-series modifications.

Key Analysis:
1. Single vs Multi-building performance comparison  
2. Worker allocation optimization
3. Memory usage profiling
4. CPU utilization analysis

Usage:
    python analyze_multibuilding.py --buildings 8 --workers 16
"""

import argparse
import time
import sys
import os
import psutil
import multiprocessing
from pathlib import Path
from typing import List, Dict, Any
import json
import threading

# Add project root to path (this file lives in src/buem/parallelization/)
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# Optimize environment
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['MKL_NUM_THREADS'] = '4' 

try:
    from buem.main import run_model, cfg
    from buem.parallelization.parallel_run import ParallelBuildingProcessor
    from buem.integration.scripts.geojson_processor import GeoJsonProcessor
    import pandas as pd
except ImportError as e:
    print(f"❌ Error importing BUEM modules: {e}")
    sys.exit(1)

class PerformanceMonitor:
    """Monitor system performance during building processing."""
    
    def __init__(self):
        self.monitoring = False
        self.cpu_samples = []
        self.memory_samples = []
        self.thread_samples = []
    
    def start_monitoring(self):
        """Start performance monitoring in background thread."""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring and return stats."""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=1)
        
        if self.cpu_samples and self.memory_samples:
            return {
                'avg_cpu_percent': sum(self.cpu_samples) / len(self.cpu_samples),
                'max_cpu_percent': max(self.cpu_samples),
                'avg_memory_mb': sum(self.memory_samples) / len(self.memory_samples),
                'max_memory_mb': max(self.memory_samples),
                'max_threads': max(self.thread_samples) if self.thread_samples else 0
            }
        return {}
    
    def _monitor_loop(self):
        """Monitor system resources every 0.5 seconds."""
        process = psutil.Process()
        while self.monitoring:
            try:
                self.cpu_samples.append(psutil.cpu_percent(interval=None))
                mem_mb = process.memory_info().rss / (1024 * 1024)
                self.memory_samples.append(mem_mb)
                self.thread_samples.append(process.num_threads())
                time.sleep(0.5)
            except:
                break

def analyze_single_building_performance():
    """Analyze single building performance as baseline."""
    print("🏢 SINGLE BUILDING BASELINE ANALYSIS")
    print("=" * 50)
    
    monitor = PerformanceMonitor()
    
    # Test with sequential thermal
    print("Testing sequential thermal processing...")
    monitor.start_monitoring()
    start_time = time.time()
    
    try:
        result = run_model(
            cfg,
            plot=False,
            use_milp=False,
            parallel_thermal=False,
            use_chunked_processing=False
        )
        sequential_time = time.time() - start_time
        sequential_stats = monitor.stop_monitoring()
        print(f"  ✅ Sequential: {sequential_time:.2f}s")
    except Exception as e:
        sequential_time = float('inf')
        sequential_stats = {}
        print(f"  ❌ Sequential failed: {e}")
    
    # Test with parallel thermal
    print("Testing parallel thermal processing...")
    monitor = PerformanceMonitor()
    monitor.start_monitoring()
    start_time = time.time()
    
    try:
        result = run_model(
            cfg,
            plot=False,
            use_milp=False,
            parallel_thermal=True,
            use_chunked_processing=False
        )
        parallel_time = time.time() - start_time
        parallel_stats = monitor.stop_monitoring()
        print(f"  ✅ Parallel: {parallel_time:.2f}s")
    except Exception as e:
        parallel_time = float('inf')
        parallel_stats = {}
        print(f"  ❌ Parallel failed: {e}")
    
    # Calculate speedup
    if sequential_time < float('inf') and parallel_time < float('inf'):
        speedup = sequential_time / parallel_time
        print(f"🚀 Thermal parallelization speedup: {speedup:.2f}x")
    
    print("\\n📊 Resource Usage:")
    if sequential_stats:
        print(f"  Sequential - CPU: {sequential_stats.get('avg_cpu_percent', 0):.1f}%, "
              f"RAM: {sequential_stats.get('avg_memory_mb', 0):.0f}MB, "
              f"Threads: {sequential_stats.get('max_threads', 0)}")
    if parallel_stats:
        print(f"  Parallel   - CPU: {parallel_stats.get('avg_cpu_percent', 0):.1f}%, "
              f"RAM: {parallel_stats.get('avg_memory_mb', 0):.0f}MB, "
              f"Threads: {parallel_stats.get('max_threads', 0)}")
    
    return {
        'sequential_time': sequential_time,
        'parallel_time': parallel_time,
        'sequential_stats': sequential_stats,
        'parallel_stats': parallel_stats
    }

def test_worker_allocation_efficiency(building_count: int = 8, max_workers: int = 16):
    """Test different worker allocations with real building files."""
    print(f"\\n👥 WORKER ALLOCATION ANALYSIS ({building_count} buildings)")
    print("=" * 50)
    
    # Load real building files from parallelization folder
    parallelization_dir = Path("src/buem/parallelization")
    geojson_files = list(parallelization_dir.glob("*.geojson"))
    
    if not geojson_files:
        print("⚠️  No GeoJSON files found in parallelization folder")
        return {}
    
    # Use available files, cycle if needed
    building_files = []
    for i in range(building_count):
        file_idx = i % len(geojson_files)
        building_files.append(geojson_files[file_idx])
    
    print(f"📁 Using {len(set(building_files))} unique building files")
    
    # Test different worker counts
    worker_counts = [1, 2, 4, 8, 12, 16] if max_workers >= 16 else [1, 2, 4, max_workers]
    worker_counts = [w for w in worker_counts if w <= max_workers]
    
    results = {}
    
    for workers in worker_counts:
        print(f"\\n  Testing {workers} workers...")
        
        monitor = PerformanceMonitor()
        monitor.start_monitoring()
        start_time = time.time()
        
        try:
            # Process buildings in parallel
            processor = ParallelBuildingProcessor(
                workers=workers,
                thermal_strategy='parallel',
                thermal_workers=2
            )
            
            building_results = []
            processed_count = 0
            
            for building_file in building_files:
                try:
                    with open(building_file, 'r') as f:
                        building_data = json.load(f)
                    
                    geojson_processor = GeoJsonProcessor(building_data)
                    result = geojson_processor.process()
                    building_results.append(result)
                    processed_count += 1
                    
                except Exception as e:
                    print(f"    ⚠️  Failed to process {building_file.name}: {e}")
                    continue
            
            elapsed = time.time() - start_time
            stats = monitor.stop_monitoring()
            
            buildings_per_second = processed_count / elapsed if elapsed > 0 else 0
            
            results[workers] = {
                'elapsed': elapsed,
                'buildings_per_second': buildings_per_second,
                'buildings_processed': processed_count,
                'stats': stats
            }
            
            print(f"    ✅ Processed {processed_count} buildings in {elapsed:.2f}s")
            print(f"       Rate: {buildings_per_second:.2f} buildings/sec")
            print(f"       CPU: {stats.get('avg_cpu_percent', 0):.1f}% avg, "
                  f"RAM: {stats.get('max_memory_mb', 0):.0f}MB max, "
                  f"Threads: {stats.get('max_threads', 0)}")
            
        except Exception as e:
            print(f"    ❌ Failed with {workers} workers: {e}")
            results[workers] = {
                'elapsed': float('inf'),
                'buildings_per_second': 0,
                'error': str(e)
            }
    
    # Find optimal configuration
    if results:
        valid_results = {k: v for k, v in results.items() 
                        if v['buildings_per_second'] > 0}
        
        if valid_results:
            optimal_workers = max(valid_results.keys(), 
                                key=lambda k: valid_results[k]['buildings_per_second'])
            optimal_rate = valid_results[optimal_workers]['buildings_per_second']
            
            print(f"\\n🏆 OPTIMAL CONFIGURATION:")
            print(f"   Workers: {optimal_workers}")
            print(f"   Throughput: {optimal_rate:.2f} buildings/second")
            
            # Calculate scaling efficiency
            if 1 in valid_results and valid_results[1]['buildings_per_second'] > 0:
                single_worker_rate = valid_results[1]['buildings_per_second']
                scaling_efficiency = (optimal_rate / single_worker_rate) / optimal_workers * 100
                print(f"   Scaling Efficiency: {scaling_efficiency:.1f}%")
    
    return results

def analyze_multibuilding_bottlenecks():
    """Analyze why multi-building processing doesn't scale linearly."""
    print(f"\\n🔍 MULTI-BUILDING BOTTLENECK ANALYSIS")
    print("=" * 50)
    
    bottlenecks = {
        'io_bound': 'File I/O operations (reading/writing GeoJSON, results)',
        'memory_bound': 'Memory allocation and matrix assembly overhead',
        'cpu_bound': 'CPU computational limits reached',
        'synchronization': 'Thread synchronization and worker coordination',
        'thermal_serial': 'Sequential thermal processing within each building',
        'shared_resources': 'Shared resources like weather data processing'
    }
    
    print("Potential bottlenecks:")
    for key, description in bottlenecks.items():
        print(f"  • {key}: {description}")
    
    recommendations = [
        "Enable chunked processing for memory-intensive buildings",
        "Optimize thermal_workers (2-4) vs main workers (8-16) ratio",
        "Use NVMe SSD for faster I/O with large result files",
        "Consider memory mapping for weather data sharing",
        "Profile individual building complexity vs processing time",
        "Test with reduced result output (disable plotting, minimize JSON)"
    ]
    
    print("\\n💡 OPTIMIZATION RECOMMENDATIONS:")
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec}")
    
    return bottlenecks

def main():
    parser = argparse.ArgumentParser(description="BUEM Multi-Building Performance Analyzer")
    
    parser.add_argument('--buildings', type=int, default=8,
                       help='Number of buildings to test (default: 8)')
    parser.add_argument('--workers', type=int, default=16,
                       help='Maximum workers to test (default: 16)')
    parser.add_argument('--skip-single', action='store_true',
                       help='Skip single building baseline test')
    
    args = parser.parse_args()
    
    # System info
    cpu_count = multiprocessing.cpu_count()
    memory_gb = round(psutil.virtual_memory().total / (1024**3))
    
    print("🚀" * 60)
    print("BUEM MULTI-BUILDING PERFORMANCE ANALYZER")
    print("🚀" * 60)
    print(f"💻 System: {cpu_count} logical cores, {memory_gb}GB RAM")
    print(f"🏗️  Test: {args.buildings} buildings, max {args.workers} workers")
    print("🚀" * 60)
    
    all_results = {}
    
    # Single building baseline
    if not args.skip_single:
        single_results = analyze_single_building_performance()
        all_results['single_building'] = single_results
    
    # Multi-building worker allocation
    worker_results = test_worker_allocation_efficiency(args.buildings, args.workers)
    all_results['worker_allocation'] = worker_results
    
    # Bottleneck analysis
    bottlenecks = analyze_multibuilding_bottlenecks()
    all_results['bottlenecks'] = bottlenecks
    
    # Final summary
    print(f"\\n📋 PERFORMANCE SUMMARY")
    print("=" * 50)
    
    if 'single_building' in all_results:
        single = all_results['single_building']
        if single['sequential_time'] < float('inf') and single['parallel_time'] < float('inf'):
            speedup = single['sequential_time'] / single['parallel_time']
            print(f"Single building thermal speedup: {speedup:.2f}x")
    
    if worker_results:
        best_workers = max([k for k, v in worker_results.items() 
                           if v['buildings_per_second'] > 0], 
                          key=lambda k: worker_results[k]['buildings_per_second'],
                          default=None)
        if best_workers:
            best_rate = worker_results[best_workers]['buildings_per_second']
            print(f"Best multi-building config: {best_workers} workers @ {best_rate:.2f} buildings/sec")
            
            # Estimate time for 50 buildings
            time_50_buildings = 50 / best_rate / 60  # minutes
            print(f"Estimated time for 50 buildings: {time_50_buildings:.1f} minutes")
    
    # Save results
    timestamp = int(time.time())
    results_file = f"performance_analysis_{timestamp}.json"
    
    # Convert results to JSON-serializable format
    json_results = {}
    for key, value in all_results.items():
        if isinstance(value, dict):
            json_results[key] = value
        else:
            json_results[key] = str(value)
    
    with open(results_file, 'w') as f:
        json.dump(json_results, f, indent=2)
    
    print(f"\\n📁 Results saved to: {results_file}")
    
    return all_results

if __name__ == "__main__":
    main()