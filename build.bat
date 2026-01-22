@echo off
REM FFXI Gear Set Optimizer - Build Script
REM Run this from the GSO_wsdist directory

echo ============================================
echo FFXI Gear Set Optimizer - Build Script
echo ============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if PyInstaller is available
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Check for required packages
echo Checking dependencies...
pip install -r requirements.txt

echo.
echo Building executable...
echo.

REM Clean previous build
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Run PyInstaller
pyinstaller gso.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build complete!
echo.
echo The executable is in: dist\FFXI_Gear_Optimizer\
echo Run: dist\FFXI_Gear_Optimizer\FFXI_Gear_Optimizer.exe
echo ============================================
echo.
pause
