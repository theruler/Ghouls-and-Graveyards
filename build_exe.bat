@echo off
rem ============================================================
rem  Builds GhoulsAndGraveyards.exe  (single file, no console)
rem  The .\data folder and ALL its sub-folders are bundled inside.
rem  Run this file from the folder that contains:
rem     ghouls_and_graveyards_v5.py   and   data\
rem ============================================================
setlocal
cd /d "%~dp0"

if not exist "data\" (
    echo ERROR: the "data" folder was not found next to this script.
    pause & exit /b 1
)

echo Installing / updating build requirements...
python -m pip install --upgrade pyinstaller pillow miniaudio
if errorlevel 1 ( echo pip failed & pause & exit /b 1 )

echo Building...
python -m PyInstaller --noconfirm --clean --onefile --noconsole ^
    --name GhoulsAndGraveyards ^
    --add-data "data;data" ^
    --collect-all miniaudio ^
    --hidden-import _cffi_backend ^
    ghouls_and_graveyards.py
if errorlevel 1 ( echo BUILD FAILED & pause & exit /b 1 )

echo.
echo Done:  dist\GhoulsAndGraveyards.exe
pause
