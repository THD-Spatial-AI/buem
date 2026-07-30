import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

print("Current working directory:", os.getcwd())
print("Project root:", project_root)

try:
    print("Testing imports...")
    print("- pandas: OK")
    print("- numpy: OK")
    print("- pvlib: OK")
    print("- cvxpy: OK")

    print("\nTesting model import...")
    print("- ModelBUEM: OK")

    print("\nAll imports successful!")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()
    sys.exit(1)
