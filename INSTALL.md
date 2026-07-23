# Packaging & Install Guide

## Packaging it for someone else (3 steps, on your machine)

```powershell
# From the project root - produces a clean release archive
# (code only, no venv / outputs / map tiles; a few MB)
git archive -o WildfireHazardDetection.zip HEAD
```

Send `WildfireHazardDetection.zip` to the recipient (cloud drive or USB stick).

> Want them to **skip downloading models and map tiles**? After creating the zip,
> copy your `models/` and `map/` folders into their unpacked directory. Those two
> folders are not in Git, so they must be carried over manually.

## Installing it (4 steps, on their machine)

1. Install **Python 3.13** (python.org - tick *Add python.exe to PATH*)
2. Unzip to any directory (avoid paths with spaces or non-ASCII characters)
3. Double-click **`install.bat`** - it creates the venv, installs PyTorch
   (CUDA build, automatic CPU fallback), installs the dependencies, and creates
   the desktop shortcut (needs internet once, about 4 GB of packages)
4. Double-click **"Wildfire Hazard Detection"** on the Desktop - a native window
   opens and everything runs offline from then on

The first detection run downloads the flame/smoke model automatically (or use
Settings -> *Download missing models* while online). Satellite map tiles are
downloaded for the current area from the Map page or the Settings page.

## Requirements

| Item | Requirement |
|------|-------------|
| OS | Windows 10/11 (macOS is code-compatible via MPS/CPU but untested; the shortcut installer is Windows-only) |
| Python | 3.13 |
| GPU | Any NVIDIA card (CUDA used automatically); without a GPU it runs on CPU - slower but usable |
| Disk | ~10 GB (dependencies + models) |
| Network | Only needed during installation; operation is fully offline |

## Why not a single setup.exe?

Bundling PyTorch CUDA + DeepForest with PyInstaller produces an 8 GB+ build and
runs into DLL compatibility problems constantly. A clean zip plus `install.bat`
is the pragmatic approach for ML desktop applications: the distributable stays
small, and once installed the experience matches a normal installed program
(desktop icon, native window, no terminal).
