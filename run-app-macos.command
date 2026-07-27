#!/bin/bash
# Launch the legacy Wildfire review app using the project venv.
# >>> macOS. On Windows use run-app-windows.bat instead. <<<
# (The system Python does not have the dependencies; they live in .venv.)
set -u
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: .venv not found. Run ./install-macos.command first."
  exit 1
fi

echo "Starting Wildfire review app... a browser will open at http://127.0.0.1:7860"
exec .venv/bin/python -m src.wildfire.app
