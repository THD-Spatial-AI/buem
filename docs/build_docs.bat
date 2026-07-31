@echo off
REM Build documentation using the activated conda environment
REM Usage: Run this from the docs directory with buem_env activated

echo Building BuEM Documentation...
echo ================================

REM Check if we're in the right directory
if not exist "source\conf.py" (
    echo Error: conf.py not found. Please run from the docs directory.
    pause
    exit /b 1
)

REM Check if sphinx is available
python -c "import sphinx; print('✓ Sphinx available')" 2>nul
if errorlevel 1 (
    echo Error: Sphinx not found. Please ensure buem_env is activated and dependencies are installed.
    echo Run: conda activate buem_env
    echo Then: conda env update -f ../environment.yml
    pause
    exit /b 1
)

REM Clean previous build
if exist "build" (
    echo Cleaning previous build...
    rmdir /s /q build
)

REM Build documentation
echo Building HTML documentation...
python -m sphinx -b html source build

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ✓ Documentation built successfully!
echo Open: build\html\index.html
echo.
pause