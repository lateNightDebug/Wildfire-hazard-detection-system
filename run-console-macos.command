#!/bin/bash
# Launch the Wildfire operations console using the project venv.
# >>> macOS. On Windows use run-console-windows.bat instead. <<<
# (The system Python does not have the dependencies; they live in .venv.)
#
# Double-click in Finder, or from Terminal pass --desktop for the native
# window, or any other console flag:
#   ./run-console-macos.command --desktop
#   ./run-console-macos.command --no-browser --port 7871
set -u
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
  echo "ERROR: .venv not found. Run ./install-macos.command first."
  exit 1
fi

echo "Starting Wildfire operations console... a browser will open at http://127.0.0.1:7861"
echo "(Run ./run-app-macos.command too if you want the review/annotation app at :7860)"
exec .venv/bin/python -m src.wildfire.console "$@"
