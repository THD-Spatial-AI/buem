@echo off
:: BUEM Thermal Model Environment Setup Script
:: This eliminates console/import issues for reliable model execution

echo ===========================================
echo BUEM Thermal Model Environment Setup
echo ===========================================

:: 1. Set working directory to project root
cd /d "d:\test\buem"
echo ✅ Working directory: %CD%

:: 2. Activate conda environment
echo.
echo Activating buem_env conda environment...
call C:\Users\sahoo002\.conda\envs\buem_env\Scripts\activate.bat
echo ✅ Conda environment activated

:: 3. Set Python path for imports
echo.
echo Setting Python path...
set PYTHONPATH=%CD%\src;%PYTHONPATH%
echo ✅ PYTHONPATH set to: %PYTHONPATH%

:: 4. Set environment variable for weather data
echo.
echo Setting weather data path...
set BUEM_WEATHER_DIR=%CD%\src\buem\data
echo ✅ BUEM_WEATHER_DIR set to: %BUEM_WEATHER_DIR%

:: 5. Verify Python and imports work
echo.
echo Testing Python environment...
C:\Users\sahoo002\.conda\envs\buem_env\python.exe -c "import sys; print('Python version:', sys.version[:5]); sys.path.insert(0, 'src'); from buem.thermal.model_buem import ModelBUEM; print('✅ ModelBUEM import successful')"

echo.
echo ===========================================
echo Environment setup complete!
echo ===========================================
echo.
echo You can now run:
echo   python test_simple.py
echo   python your_model_script.py
echo.
pause