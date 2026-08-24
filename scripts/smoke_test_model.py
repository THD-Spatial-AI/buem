"""Manual smoke test: run the module-level demo config through ModelBUEM
and print heating/cooling totals and dead-band hours.

Usage::

    python scripts/smoke_test_model.py
"""
import os

os.environ.setdefault('BUEM_WEATHER_DIR', os.path.abspath('src/buem/data'))

from buem.config.cfg_attribute import cfg
from buem.thermal.model_buem import ModelBUEM

m = ModelBUEM(cfg)
m.sim_model()
h = m.heating_load
c = m.cooling_load
A = float(cfg['A_ref'])
nh = int((h > 0).sum())
nc = int((c < 0).sum())
nb = 8760 - nh - nc
print("\n--- RESULTS ---")
print(f"Heating: {h.sum():.0f} kWh/yr  ({h.sum()/A:.0f} kWh/m2/yr)")
print(f"Cooling: {abs(c.sum()):.0f} kWh/yr  ({abs(c.sum())/A:.0f} kWh/m2/yr)")
print(f"heating_hours={nh}  cooling_hours={nc}  dead_band_hours={nb}  simultaneous={int(((h>0)&(c<0)).sum())}")
