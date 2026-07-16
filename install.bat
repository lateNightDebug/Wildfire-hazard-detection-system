@echo off
REM ============================================================
REM  Wildfire Hazard Detection System - one-click installer
REM  Prerequisites on this machine:
REM    1) Python 3.13        https://www.python.org/downloads/
REM       (check "Add python.exe to PATH" during install)
REM    2) NVIDIA GPU driver  (CPU-only also works, just slower)
REM    3) Internet for THIS install only (~4 GB of packages);
REM       afterwards the app runs fully offline.
REM ============================================================
cd /d "%~dp0"

py -3.13 --version >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python 3.13 not found. Install it from python.org first
  echo        and tick "Add python.exe to PATH".
  pause & exit /b 1
)

echo [1/5] Creating virtual environment (.venv)...
if not exist ".venv\Scripts\python.exe" py -3.13 -m venv .venv

echo [2/5] Installing PyTorch (CUDA build; falls back to CPU wheel on failure)...
".venv\Scripts\python.exe" -m pip install -U pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements-win-cuda.txt || ^
".venv\Scripts\python.exe" -m pip install torch torchvision

echo [3/5] Installing application dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo [4/5] Installing the dead-tree detector (DeepForest, large)...
".venv\Scripts\python.exe" -m pip install -r requirements-deadtree.txt

echo [5/5] Creating the desktop app shortcut...
".venv\Scripts\python.exe" -m scripts.install_desktop_app

echo.
echo Done! Double-click "Wildfire Hazard Detection" on the Desktop.
echo First detection run downloads the fire/smoke model automatically
echo (or use Settings -^> "Download missing models" while online).
pause
