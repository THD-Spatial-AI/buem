"""Debug: test worker init and process_single_building in pool."""
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

# Ensure feather cache
from buem.config import cfg_attribute  # noqa: F401
from buem.parallelization.parallel_run import _worker_init, process_single_building

building = Path(__file__).resolve().parent.parent / "src" / "buem" / "data" / "buildings" / "dummy" / "building_01_small_residential.json"


if __name__ == "__main__":
    # Test 1: Direct call (no pool)
    print("Test 1: Direct call...")
    result = process_single_building(building)
    print(f"  success={result['success']}, time={result['processing_time']:.2f}s")

    # Test 2: Pool with initializer, 2 workers
    print("\nTest 2: Pool with initializer (2 workers)...")
    with ProcessPoolExecutor(max_workers=2, initializer=_worker_init) as ex:
        fut = ex.submit(process_single_building, building)
        try:
            res = fut.result(timeout=120)
            print(f"  success={res['success']}, time={res['processing_time']:.2f}s")
        except (TimeoutError, BrokenProcessPool, OSError, ValueError, KeyError,
                IndexError, TypeError, AttributeError) as e:
            print(f"  FAILED: {type(e).__name__}: {e}")

    # Test 3: Pool WITHOUT initializer (to compare)
    print("\nTest 3: Pool without initializer (2 workers)...")
    with ProcessPoolExecutor(max_workers=2) as ex:
        fut = ex.submit(process_single_building, building)
        try:
            res = fut.result(timeout=120)
            print(f"  success={res['success']}, time={res['processing_time']:.2f}s")
        except (TimeoutError, BrokenProcessPool, OSError, ValueError, KeyError,
                IndexError, TypeError, AttributeError) as e:
            print(f"  FAILED: {type(e).__name__}: {e}")
