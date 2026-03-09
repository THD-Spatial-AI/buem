import sys
import os
from pathlib import Path

# Resolve project root (this file lives in tests/)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

print("Current working directory:", os.getcwd())
print("Project root:", project_root)

try:
    print("Testing imports...")
    import pandas as pd
    print("- pandas: OK")
    import numpy as np
    print("- numpy: OK")
    import pvlib
    print("- pvlib: OK")
    import cvxpy
    print("- cvxpy: OK")

    print("\nTesting model import...")
    from buem.thermal.model_buem import ModelBUEM
    print("- ModelBUEM: OK")

    print("\nAll imports successful!")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
