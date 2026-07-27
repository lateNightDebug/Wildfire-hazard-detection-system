@echo off
REM Double-click to launch the Wildfire review app using the project venv.
REM >>> WINDOWS. On macOS use run-app-macos.command instead. <<<
REM (The system Python does not have the dependencies; they live in .venv.)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run install-windows.bat first.
  pause
  exit /b 1
)
echo Starting Wildfire review app... a browser will open at http://127.0.0.1:7860
".venv\Scripts\python.exe" -m src.wildfire.app
pause
