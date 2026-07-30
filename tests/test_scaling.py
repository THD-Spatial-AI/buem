"""
Worker count scaling test: run 15 buildings with different worker counts
to find the optimal configuration for the 22-core system.
"""
import time
from pathlib import Path

# Ensure feather cache exists by importing cfg_attribute first
from buem.config import cfg_attribute  # noqa: F401
from buem.integration.scripts.result_cache import clear_cache

dummy_dir = Path(__file__).parent.parent / "src" / "buem" / "data" / "buildings" / "dummy"
building_files = sorted(dummy_dir.glob("*.json"))

# Import after ensuring weather cache
from buem.parallelization.parallel_run import ParallelBuildingProcessor

if __name__ == "__main__":
    print(f"Found {len(building_files)} building files")

    worker_counts = [4, 6, 8, 10, 12]
    results_summary = []

    for n_workers in worker_counts:
        # Clear result cache for fair comparison
        cleared = clear_cache()
        print(f"\n{'='*60}")
        print(f"Testing with {n_workers} workers ({cleared} cached results cleared)")
        print(f"{'='*60}")

        processor = ParallelBuildingProcessor(
            workers=n_workers,
            timeout=120.0,
        )

        t0 = time.time()
        results = processor.process_buildings(
            building_files=list(building_files),
            save_results=False,
        )
        wall_time = time.time() - t0

        summary = results["summary"]
        perf = results["performance"]
        results_summary.append({
            "workers": n_workers,
            "wall_time_s": round(wall_time, 2),
            "successful": summary["successful"],
            "failed": summary["failed"],
            "rate_bldg_per_sec": round(perf["buildings_per_second"], 2),
            "avg_per_building_s": round(perf["average_time_per_building"], 2),
        })

        print(f"  Wall time: {wall_time:.2f}s")
        print(f"  Success: {summary['successful']}/{summary['total_buildings']}")
        print(f"  Rate: {perf['buildings_per_second']:.2f} buildings/sec")

    print(f"\n{'='*60}")
    print("SCALING SUMMARY")
    print(f"{'='*60}")
    print(f"{'Workers':>8} {'Wall(s)':>8} {'OK':>4} {'Fail':>4} {'Rate':>8} {'Avg(s)':>8}")
    print("-" * 48)
    for r in results_summary:
        print(f"{r['workers']:>8} {r['wall_time_s']:>8.2f} {r['successful']:>4} {r['failed']:>4} {r['rate_bldg_per_sec']:>8.2f} {r['avg_per_building_s']:>8.2f}")

    # Find optimal
    best = min(results_summary, key=lambda x: x["wall_time_s"])
    print(f"\nOptimal: {best['workers']} workers ({best['wall_time_s']:.2f}s)")
