# BUEM Multi-Building Processing System

This module provides comprehensive parallel and sequential processing capabilities for multiple building energy models using the BUEM (Building Energy Model) system.

## 🎯 Overview

The multi-building processing system enables efficient analysis of large building datasets with support for:

- **Parallel Processing**: Utilize multiple CPU cores for faster processing
- **Sequential Processing**: Traditional single-threaded processing for debugging and comparison
- **Performance Comparison**: Automated benchmarking between processing methods
- **Scalability Analysis**: Test performance across different dataset sizes
- **Comprehensive Reporting**: Detailed metrics, visualizations, and recommendations

## 📁 Module Structure

```
src/buem/parallelization/
├── parallel_run.py              # Parallel processing implementation
├── sequence_run.py              # Sequential processing implementation 
├── performance_comparison.py    # Performance analysis and comparison
├── run_multibuilding_demo.py    # Master demonstration script
└── README.md                    # This documentation
```

## 🏢 Demo Building Configurations

Five diverse building configurations are provided for testing:

```
src/buem/integration/json_schema/versions/v2/dummy/
├── building_01_small_residential.json    # 80 m² residential building
├── building_02_medium_office.json        # 250 m² office building
├── building_03_large_commercial.json     # 500 m² commercial building
├── building_04_industrial.json           # 800 m² industrial building
└── building_05_mixed_use.json           # 350 m² mixed-use building
```

## 🚀 Quick Start

### 1. Install Dependencies

The required packages are already included in the BUEM environment:

```bash
conda activate buem_env
# Dependencies (psutil, joblib) are automatically installed
```

### 2. Run Complete Demonstration

```bash
cd src/buem/parallelization
python run_multibuilding_demo.py
```

### 3. Run Specific Tests

```bash
# Parallel processing only
python run_multibuilding_demo.py --test parallel

# Sequential processing only  
python run_multibuilding_demo.py --test sequential

# Performance comparison
python run_multibuilding_demo.py --test comparison

# Comprehensive benchmark
python run_multibuilding_demo.py --test benchmark
```

## 📊 Usage Examples

### Basic Parallel Processing

```python
from buem.parallelization.parallel_run import ParallelBuildingProcessor

# Initialize processor
processor = ParallelBuildingProcessor(
    workers=4,           # Number of worker processes
    chunk_size=5,        # Buildings per chunk
    timeout=300          # Timeout per building (seconds)
)

# Process buildings
results = processor.process_buildings(
    building_files=["building1.json", "building2.json", ...],
    save_results=True
)

print(f"Processed {results['summary']['total_buildings']} buildings")
print(f"Success rate: {results['summary']['success_rate_percent']:.1f}%")
print(f"Total time: {results['summary']['total_processing_time']:.2f}s")
```

### Performance Comparison

```python
from buem.parallelization.performance_comparison import PerformanceComparator

# Initialize comparator
comparator = PerformanceComparator(
    visualize_results=True,
    save_detailed_report=True
)

# Compare processing methods
comparison = comparator.compare_processing_methods(
    building_files=building_list,
    worker_counts=[1, 2, 4, 8]
)

# Get recommendations
recommendations = comparison['recommendations']
print(f"Best configuration: {recommendations['best_configuration']}")
print(f"Speedup: {recommendations['best_speedup']:.2f}x")
print(f"Recommended approach: {recommendations['recommended_approach']}")
```

### Sequential Processing

```python
from buem.parallelization.sequence_run import SequentialBuildingProcessor

# Initialize sequential processor
processor = SequentialBuildingProcessor(
    timeout=300,
    detailed_logging=True,
    memory_monitoring=True
)

# Process buildings sequentially
results = processor.process_buildings(building_files)

print(f"Average time per building: {results['performance']['average_time_per_building']:.2f}s")
print(f"Peak memory usage: {results['performance']['peak_memory_mb']:.1f} MB")
```

## ⚡ Performance Characteristics

### Expected Performance

| Dataset Size | Parallel (4 cores) | Sequential | Expected Speedup |
|-------------|-------------------|------------|------------------|
| 5 buildings | ~15-30 seconds    | ~30-60 seconds | 1.5-2.0x |
| 50 buildings | ~2-5 minutes     | ~8-15 minutes  | 2.5-4.0x |
| 500 buildings | ~20-50 minutes   | ~2-4 hours     | 3.0-6.0x |

### Optimization Guidelines

- **Worker Count**: Start with `CPU cores - 1`, max tested up to 16 workers
- **Memory**: ~100-500 MB per worker process
- **I/O Considerations**: SSD recommended for large datasets
- **Network**: Local processing recommended; network latency affects performance

## 📈 Output and Reporting

### Performance Reports

All processing results include:

```json
{
  "summary": {
    "total_buildings": 5,
    "successful": 5,
    "failed": 0,
    "success_rate_percent": 100.0,
    "total_processing_time": 25.67
  },
  "performance": {
    "workers": 4,
    "buildings_per_second": 0.19,
    "average_time_per_building": 5.13,
    "memory_usage_mb": 245.3
  },
  "buildings": {
    "successful": [...],  // Individual building results
    "failed": [...]       // Error details for failed buildings
  }
}
```

### Visualization

Performance comparison generates charts showing:

- Processing time by configuration
- Speedup vs worker count  
- Parallel efficiency analysis
- Processing rate comparison

Charts are saved as high-resolution PNG files in `performance_reports/`.

### Building Results

Each processed building returns:

```json
{
  "building_id": "building_001_small_residential",
  "success": true,
  "processing_time": 4.23,
  "summary_stats": {
    "heating": {
      "total_kwh": 1245.6,
      "max_kw": 8.4,
      "mean_kw": 2.1
    },
    "cooling": {
      "total_kwh": 856.3,
      "max_kw": 5.2,
      "mean_kw": 1.4
    },
    "total_energy_demand_kwh": 2101.9
  }
}
```

## 🔧 Advanced Configuration

### Custom Processing Pipeline

```python
# Custom progress tracking
def progress_handler(completed: int, total: int):
    print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)")

# Advanced parallel configuration
processor = ParallelBuildingProcessor(
    workers=8,
    chunk_size=10,
    timeout=600,  # 10 minutes per building
    progress_callback=progress_handler
)

# Process with custom settings
results = processor.process_buildings(
    building_files=large_dataset,
    save_results=True,
    results_file="custom_results.json"
)
```

### Benchmarking Different Scenarios

```python
# Test multiple scenarios
comparator = PerformanceComparator(
    test_scenarios=['small', 'medium', 'large'],
    max_workers=16,
    visualize_results=True
)

benchmark_results = comparator.run_comprehensive_benchmark(
    building_files=building_dataset,
    scaling_test=True
)

# Analyze scaling characteristics
for scenario, results in benchmark_results['scenario_results'].items():
    scaling = benchmark_results['overall_analysis']['scaling_characteristics'][scenario]
    print(f"{scenario}: {scaling['building_count']} buildings, "
          f"{scaling['best_speedup']:.2f}x speedup")
```

## 🐛 Troubleshooting

### Common Issues

1. **Out of Memory Errors**
   ```python
   # Solution: Reduce worker count or chunk size
   processor = ParallelBuildingProcessor(workers=2, chunk_size=3)
   ```

2. **Processing Timeouts**
   ```python
   # Solution: Increase timeout for complex buildings
   processor = ParallelBuildingProcessor(timeout=600)  # 10 minutes
   ```

3. **Import Errors**
   ```bash
   # Ensure BUEM is properly installed and paths are correct
   cd src/buem
   python -c "import buem; print('BUEM available')"
   ```

### Debugging Individual Buildings

```python
# Use sequential processing for detailed debugging
processor = SequentialBuildingProcessor(
    detailed_logging=True,
    memory_monitoring=True
)

# Process single building for debugging
results = processor.process_buildings([problematic_building])
```

## 🎯 Use Cases

### Research Applications
- **Building Stock Analysis**: Process 1000s of buildings for urban energy analysis
- **Parameter Studies**: Test different building configurations efficiently  
- **Climate Analysis**: Process buildings across different weather conditions
- **Policy Impact Assessment**: Analyze building performance under different scenarios

### Production Deployment
- **REST API Backend**: Process building requests in parallel
- **Batch Processing**: Scheduled processing of building datasets
- **Real-time Analysis**: Quick processing for interactive applications
- **Cloud Deployment**: Scalable processing in cloud environments

## 📝 Dependencies

### Required Dependencies
- `numpy` - Numerical computations
- `pandas` - Data manipulation
- `psutil` - System monitoring
- `joblib` - Parallel processing utilities
- `buem` - Core building energy modeling

### Optional Dependencies
- `matplotlib` - Performance visualization
- `flask` - Web API integration

## 🔮 Future Enhancements

Planned improvements include:

1. **Distributed Processing**: Cluster computing with Ray/Dask
2. **Cloud Integration**: AWS/Azure parallel processing
3. **Real-time Monitoring**: Live processing dashboards
4. **Advanced Caching**: Intelligent result caching
5. **ML Integration**: Performance prediction and optimization

## 📚 Additional Resources

- [BUEM Core Documentation](../../README.md)
- [Building Configuration Schema](../integration/json_schema/versions/v2/)
- [Performance Optimization Guide](./docs/optimization.md) *(coming soon)*
- [Production Deployment Guide](./docs/deployment.md) *(coming soon)*

## 🤝 Contributing

When contributing to the multi-building processing system:

1. **Test with Multiple Scenarios**: Verify changes work across different building types
2. **Performance Testing**: Benchmark any changes that affect processing speed
3. **Memory Profiling**: Monitor memory usage for large datasets
4. **Documentation**: Update this README for any API changes
5. **Error Handling**: Ensure robust error handling for production use

## 📄 License

This module is part of the BUEM project and follows the same MIT license terms.