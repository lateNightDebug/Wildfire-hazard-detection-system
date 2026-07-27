#!/bin/bash
# ============================================================
#  Wildfire Hazard Detection System - one-click installer
#  >>> macOS ONLY. On Windows run install-windows.bat instead. <<<
#
#  Double-click this file in Finder, or run ./install-macos.command from
#  Terminal. (.command is the macOS counterpart of a .bat: Finder opens
#  Terminal and runs it, so there is nothing to type either way.)
#
#  Prerequisites on this machine:
#    1) Python 3.13      brew install python@3.13
#                        (or python.org - the installer adds it to PATH)
#    2) Internet for THIS install only (~4 GB of packages);
#       afterwards the app runs fully offline.
#  Apple Silicon uses the GPU through Metal (MPS) automatically;
#  Intel Macs fall back to CPU - slower, but it works.
# ============================================================
set -u
cd "$(dirname "$0")" || exit 1

# This installs the Apple build of PyTorch, so running it anywhere else would
# quietly produce a broken environment. Fail loudly, and name the right script.
if [ "$(uname -s)" != "Darwin" ]; then
  echo "ERROR: install-macos.command is the macOS installer - it installs the"
  echo "       Apple Metal build of PyTorch, which is wrong for $(uname -s)."
  echo "       On Windows, run install-windows.bat instead."
  exit 1
fi

PY=""
for candidate in python3.13 /opt/homebrew/opt/python@3.13/bin/python3.13 \
                 /usr/local/opt/python@3.13/bin/python3.13 \
                 /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "ERROR: Python 3.13 not found."
  echo "       Install it with:  brew install python@3.13"
  echo "       (or from https://www.python.org/downloads/)"
  exit 1
fi
echo "Using $("$PY" --version) at $(command -v "$PY")"

VENV_PY=".venv/bin/python"

echo "[1/5] Creating virtual environment (.venv)..."
if [ ! -x "$VENV_PY" ]; then "$PY" -m venv .venv || exit 1; fi

echo "[2/5] Installing PyTorch (CPU + Apple Metal build)..."
"$VENV_PY" -m pip install -U pip --quiet
"$VENV_PY" -m pip install -r requirements-mac.txt || exit 1

echo "[3/5] Installing application dependencies..."
"$VENV_PY" -m pip install -r requirements.txt || exit 1

echo "[4/5] Installing the dead-tree detector (DeepForest, large)..."
"$VENV_PY" -m pip install -r requirements-deadtree.txt || exit 1

echo "[5/5] Creating the desktop app..."
# Non-fatal: the console runs perfectly well without the launcher bundle.
"$VENV_PY" -m scripts.install_desktop_app || \
  echo "      (skipped - start the app with ./run-console-macos.command instead)"

echo
echo "Done! Double-click \"Wildfire Hazard Detection\" on the Desktop."
echo "First detection run downloads the fire/smoke model automatically"
echo "(or use Settings -> \"Download missing models\" while online)."
