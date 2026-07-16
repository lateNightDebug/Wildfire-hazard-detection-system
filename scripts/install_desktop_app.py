"""Install the console as a desktop app: app icon + Desktop / Start Menu shortcuts.

    python -m scripts.install_desktop_app

Creates assets/wildfire.ico (drawn with Pillow) and shortcuts that launch
`pythonw.exe -m src.wildfire.console --desktop` — a native window, no terminal.
Run again any time to refresh; delete the shortcuts to "uninstall".
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT_ROOT / "assets"
APP_NAME = "Wildfire Hazard Detection"


def make_icon(dest: Path) -> Path:
    """Draw the app icon (green rounded square + white flame) as a multi-size .ico."""
    from PIL import Image, ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, fill=(45, 90, 45, 255))
    d.rounded_rectangle([8, 8, size - 8, size - 8], radius=56, outline=(58, 154, 58, 255), width=6)

    # Flame: teardrop body + inner notch, mirroring the console's logo mark.
    cx = size / 2
    flame = [
        (cx, 42), (cx + 26, 84), (cx + 44, 126), (cx + 46, 158),
        (cx + 34, 192), (cx, 208), (cx - 34, 192), (cx - 46, 158),
        (cx - 44, 126), (cx - 26, 84),
    ]
    d.polygon(flame, fill=(255, 255, 255, 255))
    d.polygon([(cx, 118), (cx + 18, 152), (cx + 10, 182), (cx, 192),
               (cx - 10, 182), (cx - 18, 152)], fill=(45, 90, 45, 255))

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return dest


def make_shortcut(lnk_path: Path, icon: Path) -> None:
    pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{lnk_path}')
$s.TargetPath = '{pythonw}'
$s.Arguments = '-m src.wildfire.console --desktop'
$s.WorkingDirectory = '{PROJECT_ROOT}'
$s.IconLocation = '{icon}'
$s.Description = 'Offline drone wildfire hazard detection console'
$s.Save()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True,
                   capture_output=True, text=True)


def main() -> int:
    pythonw = PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        print(f"venv pythonw not found at {pythonw} — create the venv first.")
        return 2

    icon = make_icon(ASSETS / "wildfire.ico")
    print(f"icon    : {icon}")

    import os

    # Ask Windows for the real Desktop (handles OneDrive-redirected profiles).
    probe = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
        capture_output=True, text=True)
    desktop = Path(probe.stdout.strip() or (Path.home() / "Desktop"))
    start_menu = Path(os.path.expandvars(
        r"%APPDATA%")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    for where in (desktop, start_menu):
        if where.exists():
            lnk = where / f"{APP_NAME}.lnk"
            make_shortcut(lnk, icon)
            print(f"shortcut: {lnk}")
    print(f"\nDouble-click \"{APP_NAME}\" — the app opens in its own window, no terminal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
