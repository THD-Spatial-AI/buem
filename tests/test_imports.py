import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

print("Current working directory:", os.getcwd())
print("Project root:", project_root)

try:
    print("Testing imports...")
    import pandas
    print(f"- pandas: OK ({pandas.__version__})")
    import numpy
    print(f"- numpy: OK ({numpy.__version__})")
    import pvlib
    print(f"- pvlib: OK ({pvlib.__version__})")
    import cvxpy
    print(f"- cvxpy: OK ({cvxpy.__version__})")

    print("\nTesting model import...")
    from buem.thermal.model_buem import ModelBUEM
    print(f"- ModelBUEM: OK ({ModelBUEM.__module__})")

    print("\nAll imports successful!")

except ImportError as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
