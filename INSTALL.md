# Packaging & Install Guide

## Packaging it for someone else (3 steps, on your machine)

```bash
# From the project root - produces a clean release archive
# (code only, no venv / outputs / map tiles; a few MB)
git archive -o WildfireHazardDetection.zip HEAD
```

Send `WildfireHazardDetection.zip` to the recipient (cloud drive or USB stick).

> Want them to **skip downloading models and map tiles**? After creating the zip,
> copy your `models/` and `map/` folders into their unpacked directory. Those two
> folders are not in Git, so they must be carried over manually.

## Which file do I run?

Both platforms' scripts ship in the same archive, and every filename says which
OS it belongs to. **Run only your platform's** - the two installers fetch
different PyTorch builds (CUDA vs Apple Metal), so the wrong one produces an
environment that will not run.

| | Windows | macOS |
|---|---|---|
| Install (once) | `install-windows.bat` | `install-macos.command` |
| Console in a browser | `run-console-windows.bat` | `run-console-macos.command` |
| Legacy review app | `run-app-windows.bat` | `run-app-macos.command` |

All six are double-clickable. `.command` is the macOS counterpart of `.bat`:
Finder opens Terminal and runs it, so neither platform has anything to type.
Running the macOS installer on a non-Mac stops with a message naming the right
script rather than half-installing.

## Installing it (4 steps, on their machine)

### Windows

1. Install **Python 3.13** (python.org - tick *Add python.exe to PATH*)
2. Unzip to any directory (avoid paths with spaces or non-ASCII characters)
3. Double-click **`install-windows.bat`** - it creates the venv, installs PyTorch
   (CUDA build, automatic CPU fallback), installs the dependencies, and creates
   the desktop shortcut (needs internet once, about 4 GB of packages)
4. Double-click **"Wildfire Hazard Detection"** on the Desktop - a native window
   opens and everything runs offline from then on

### macOS

1. Install **Python 3.13** (`brew install python@3.13`, or python.org)
2. Unpack the zip anywhere in the home folder
3. Double-click **`install-macos.command`** (Finder opens Terminal and runs it) -
   same steps with the CPU/Metal build of PyTorch, ending with an app in
   `~/Applications` and a shortcut to it on the Desktop
4. Double-click **"Wildfire Hazard Detection"** on the Desktop - a native window
   opens and everything runs offline from then on

> The bundle lives in `~/Applications` (no admin password needed), which is a
> different folder from the `/Applications` in the Finder sidebar - hence the
> Desktop shortcut, matching what the Windows installer creates. Spotlight
> (Cmd-Space) finds it by name either way. Do not tell users "it is in
> Launchpad": **macOS 26 removed Launchpad**, replacing it with the Apps view in
> Spotlight.

The first detection run downloads the flame/smoke model automatically (or use
Settings -> *Download missing models* while online). Satellite map tiles are
downloaded for the current area from the Map page or the Settings page.

## Requirements

| Item | Requirement |
|------|-------------|
| OS | Windows 10/11, or macOS 11+ (Apple Silicon or Intel) |
| Python | 3.13 |
| GPU | Windows: any NVIDIA card (CUDA used automatically). macOS: Apple Silicon via Metal/MPS, automatic. Without either it runs on CPU - slower but usable |
| Disk | ~10 GB (dependencies + models) |
| Network | Only needed during installation; operation is fully offline |

## Why not a single setup.exe / .dmg?

Bundling PyTorch CUDA + DeepForest with PyInstaller produces an 8 GB+ build and
runs into DLL compatibility problems constantly; py2app hits the same wall on
macOS. A clean zip plus one install script is the pragmatic approach for ML
desktop applications: the distributable stays small, and once installed the
experience matches a normal installed program (desktop icon, Spotlight entry,
native window, no terminal).

The macOS `.app` the installer writes is a three-file bundle - `Info.plist`, an
icon, and a shell launcher pointing at `.venv/bin/python` - not a frozen copy of
the code. It keeps working after a `git pull`, exactly like the Windows `.lnk`.
It is also unsigned, which is fine because the user builds it locally; a bundle
that arrived over the network would need notarizing.
