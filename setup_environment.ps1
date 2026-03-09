# BUEM Thermal Model Environment Setup (PowerShell)
# This eliminates console/import issues for reliable model execution

Write-Host "=============================================" -ForegroundColor Green
Write-Host "BUEM Thermal Model Environment Setup" -ForegroundColor Green  
Write-Host "=============================================" -ForegroundColor Green

# 1. Set working directory to project root
Set-Location "d:\test\buem"
Write-Host "✅ Working directory: $PWD" -ForegroundColor Green

# 2. Set Python path for imports
$env:PYTHONPATH = "$PWD\src;$env:PYTHONPATH"
Write-Host "✅ PYTHONPATH set to: $env:PYTHONPATH" -ForegroundColor Green

# 3. Set environment variable for weather data  
$env:BUEM_WEATHER_DIR = "$PWD\src\buem\data"
Write-Host "✅ BUEM_WEATHER_DIR set to: $env:BUEM_WEATHER_DIR" -ForegroundColor Green

# 4. Set Python executable path
$PythonExe = "C:\Users\sahoo002\.conda\envs\buem_env\python.exe"
Write-Host "✅ Python executable: $PythonExe" -ForegroundColor Green

# 5. Verify Python and imports work
Write-Host "`n🔧 Testing Python environment..." -ForegroundColor Yellow
try {
    & $PythonExe -c "import sys; print('Python version:', sys.version[:5]); sys.path.insert(0, 'src'); from buem.thermal.model_buem import ModelBUEM; print('✅ ModelBUEM import successful')"
    Write-Host "✅ Environment test passed!" -ForegroundColor Green
} catch {
    Write-Host "❌ Environment test failed: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host "Environment setup complete!" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host "`nYou can now run:" -ForegroundColor Cyan
Write-Host "  & '$PythonExe' test_simple.py" -ForegroundColor White  
Write-Host "  & '$PythonExe' your_model_script.py" -ForegroundColor White
Write-Host ""