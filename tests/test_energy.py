#!/usr/bin/env python3
"""Integration smoke-test: run the thermal model and check energy output."""
import sys
import os
from pathlib import Path

# Resolve project root (this file lives in tests/)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
os.environ.setdefault("BUEM_WEATHER_DIR", str(project_root / "src" / "buem" / "data"))

from buem.main import run_model
from buem.config.cfg_attribute import cfg


def main():
    try:
        print("Testing thermal model with realistic parameters...")
        res = run_model(cfg, plot=False, return_models=True)

        heating = res["heating"].sum()
        cooling = res["cooling"].sum()

        print(f"\n=== ENERGY RESULTS ===")
        print(f"Heating: {heating:.0f} kWh/year")
        print(f"Cooling: {cooling:.0f} kWh/year")
        print(f"Total: {abs(heating) + abs(cooling):.0f} kWh/year")

        floor_area = 100.0  # m²
        print(f"Heating per floor area: {heating/floor_area:.0f} kWh/m²/year")
        print(f"Cooling per floor area: {abs(cooling)/floor_area:.0f} kWh/m²/year")
        print("======================")

        import numpy as np
        mh = res.get("model_heat")
        if mh is not None:
            T_air = np.asarray(mh.T_air)
            T_sur = np.asarray(mh.T_sur)
            T_m = np.asarray(mh.T_m)
            T_e = mh.cfg["weather"]["T"].values
            print(f"\n=== TEMPERATURE STATS (heating model) ===")
            print(f"T_air : min={T_air.min():.1f}  max={T_air.max():.1f}  mean={T_air.mean():.1f} °C")
            print(f"T_sur : min={T_sur.min():.1f}  max={T_sur.max():.1f}  mean={T_sur.mean():.1f} °C")
            print(f"T_m   : min={T_m.min():.1f}  max={T_m.max():.1f}  mean={T_m.mean():.1f} °C")
            print(f"T_ext : min={T_e.min():.1f}  max={T_e.max():.1f}  mean={T_e.mean():.1f} °C")

    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
