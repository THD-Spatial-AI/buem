#!/usr/bin/env python3
"""
BUEM Thermal Model Validation Script
Validates that environment and model are working correctly.
"""
import os
import sys
import traceback
from pathlib import Path

def main():
    print("=" * 50)
    print("BUEM Thermal Model Environment Validation")
    print("=" * 50)
    
    # Check working directory
    print(f"✓ Working directory: {os.getcwd()}")
    
    # Check Python path
    print(f"✓ Python path includes src: {'src' in sys.path[0] or any('src' in p for p in sys.path)}")
    
    # Check environment variables
    buem_weather_dir = os.environ.get('BUEM_WEATHER_DIR')
    print(f"✓ BUEM_WEATHER_DIR: {buem_weather_dir}")
    
    # Test imports
    try:
        import pandas as pd
        print("✓ pandas imported successfully")
        
        import numpy as np  
        print("✓ numpy imported successfully")
        
        import pvlib
        print("✓ pvlib imported successfully")
        
        import cvxpy
        print("✓ cvxpy imported successfully")
        
        # Add src to path if not already there
        src_path = os.path.join(os.getcwd(), 'src')
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            
        from buem.thermal.model_buem import ModelBUEM
        print("✓ ModelBUEM imported successfully")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
        
    # Test simple model configuration
    try:
        print("\n" + "=" * 30)
        print("Testing Model Configuration")  
        print("=" * 30)
        
        # Minimal weather data
        times = pd.date_range('2024-01-01', periods=24, freq='h', tz='UTC')
        times = times.tz_convert(None)
        
        weather_data = pd.DataFrame({
            'T': np.full(24, 15.0),  # Constant 15°C
            'GHI': np.zeros(24),     # No solar
            'DNI': np.zeros(24),
            'DHI': np.zeros(24)
        }, index=times)
        
        print("✓ Weather data created")
        
        # Required configuration
        cfg_test = {
            'weather': weather_data,
            'latitude': 52.0,
            'longitude': 5.0, 
            'A_ref': 150.0,
            'h_room': 2.5,
            'n_air_infiltration': 0.5,
            'n_air_use': 0.5,
            'comfortT_lb': 21.0,
            'comfortT_ub': 24.0,
            'g_gl_n_Window': 0.6,
            'design_T_min': -10.0,
            'thermalClass': 'medium',
            'F_sh_vert': 1.0,
            'F_sh_hor': 1.0, 
            'F_w': 1.0,
            'F_f': 0.6,
            'components': {
                'Walls': {
                    'U': 0.3,
                    'elements': [
                        {'id': 'South_Wall', 'area': 30.0, 'azimuth': 180.0, 'tilt': 90.0}
                    ]
                },
                'Roof': {
                    'U': 0.2,
                    'elements': [
                        {'id': 'Roof_1', 'area': 75.0, 'azimuth': 180.0, 'tilt': 45.0}
                    ]
                },
                'Floor': {
                    'U': 0.25,
                    'elements': [
                        {'id': 'Ground_Floor', 'area': 75.0, 'azimuth': 0.0, 'tilt': 0.0}
                    ]
                },
                'Windows': {
                    'U': 1.4,
                    'elements': [
                        {'id': 'South_Window', 'area': 12.0, 'azimuth': 180.0, 'tilt': 90.0}
                    ]
                }
            }
        }
        
        print("✓ Configuration created")
        
        # Test model initialization
        model = ModelBUEM(cfg_test)
        print("✓ Model initialized")
        
        model._addPara()
        print("✓ Parameters computed")
        
        # Check solar gains are reasonable
        wall_gains_max = model.profiles["bQ_sol_Walls"].max()
        roof_gains_max = model.profiles["bQ_sol_Roof"].max()
        window_gains_max = model.profiles["bQ_sol_Windows"].max()
        
        print(f"✓ Wall solar gains: {wall_gains_max:.3f} kW")
        print(f"✓ Roof solar gains: {roof_gains_max:.3f} kW") 
        print(f"✓ Window solar gains: {window_gains_max:.3f} kW")
        
        # Validate gains are reasonable (should be ~0 with no solar)
        if abs(wall_gains_max) < 0.1 and abs(roof_gains_max) < 0.1:
            print("✓ Solar gains are reasonable")
        else:
            print(f"❌ Solar gains excessive: walls={wall_gains_max}, roofs={roof_gains_max}")
            return False
            
        print("\n" + "=" * 50)
        print("🎉 ALL VALIDATIONS PASSED!")
        print("Environment and model are working correctly.")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"❌ Model test error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)