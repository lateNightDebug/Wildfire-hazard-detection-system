@echo off
REM Double-click to launch the Wildfire operations console using the project venv.
REM >>> WINDOWS. On macOS use run-console-macos.command instead. <<<
REM (The system Python does not have the dependencies; they live in .venv.)
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run install-windows.bat first.
  pause
  exit /b 1
)
echo Starting Wildfire operations console... a browser will open at http://127.0.0.1:7861
echo (Run run-app-windows.bat too if you want the review/annotation app at :7860)
".venv\Scripts\python.exe" -m src.wildfire.console
pause
