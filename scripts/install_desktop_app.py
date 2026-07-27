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


ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _mark_from_logo(logo: Path):
    """The square mark out of branding/logo.png, ready to sit in an icon.

    Most logos are wordmarks - ours is 739x202 - and squeezing one into 16x16
    produces a smudge. So: find the ink, and if the logo is wide, cut at the
    first clear vertical gap, which in a wordmark is the space between the
    symbol and the lettering. A logo that is already roughly square is used
    whole. Returns None if Pillow cannot read the file, so the caller can fall
    back rather than fail the install.
    """
    from PIL import Image

    try:
        im = Image.open(logo).convert("RGBA")
    except Exception:
        return None

    # Ink = visible and not near-white, so a white-on-transparent logo still works.
    px = im.load()
    w, h = im.size
    cols = [False] * w
    for x in range(w):
        for y in range(0, h, 2):  # every other row is plenty to find a gap
            r, g, b, a = px[x, y]
            if a > 24 and r + g + b < 720:
                cols[x] = True
                break
    xs = [x for x, on in enumerate(cols) if on]
    if not xs:
        return None
    left, right = xs[0], xs[-1]

    if (right - left + 1) / max(1, h) > 1.4:  # wordmark: keep the leading mark
        gap_start = None
        for x in range(left, right + 1):
            if not cols[x]:
                gap_start = x if gap_start is None else gap_start
            else:
                if gap_start is not None and x - gap_start >= 8:
                    right = gap_start
                    break
                gap_start = None
    return im.crop((left, 0, right + 1, h))


def make_icon(dest: Path) -> Path:
    """Build the multi-size .ico from the branding logo.

    The icon used to be drawn here in Pillow - a green square with a flame - so
    the shortcut and the window carried something the rest of the app no longer
    looked like. It now comes from branding/logo.png, which means rebranding is
    still one file drop.
    """
    from PIL import Image, ImageDraw

    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # White plate with a brand-coloured rim. A brand-filled plate was tried and
    # the logo's own blues sank into it - illegible by 16px. Most marks are drawn
    # for white, and the rim keeps the icon from vanishing on a light taskbar.
    brand = _brand_colors()
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=52,
                        fill=(255, 255, 255, 255), outline=brand, width=8)

    mark = _mark_from_logo(PROJECT_ROOT / "branding" / "logo.png")
    if mark is not None:
        inner = int(size * 0.70)  # padding so it reads as an icon, not a sticker
        mark.thumbnail((inner, inner), Image.LANCZOS)
        img.alpha_composite(mark, ((size - mark.width) // 2, (size - mark.height) // 2))
    else:
        d.text((size // 2, size // 2), "W", anchor="mm", fill=brand)

    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, sizes=ICON_SIZES)
    return dest


def _brand_colors() -> tuple:
    """Icon plate colour from branding/brand.json, so it tracks the brand."""
    import json

    try:
        cfg = json.loads((PROJECT_ROOT / "branding" / "brand.json").read_text(encoding="utf-8"))
        h = (cfg.get("colors", {}).get("primary") or "").lstrip("#")
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    except Exception:
        pass
    return (45, 90, 45, 255)


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
