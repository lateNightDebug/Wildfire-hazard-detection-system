"""Native desktop window for the console (pywebview over Edge WebView2).

`python -m src.wildfire.console --desktop` starts the FastAPI server on a
background thread and opens the UI in a real application window — no browser
chrome, no terminal. Launched via pythonw.exe (see scripts/install_desktop_app.py)
there is no console window at all: it looks and behaves like installed software.

Closing the window shuts the server down.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))  # so scripts/ is importable for the icon

APP_TITLE = "Wildfire Hazard Detection System"


def _wait_for_port(port: int, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _app_icon() -> str | None:
    """Path to the window icon, built from the branding logo if it is missing.

    Without this the title bar and the taskbar show the Python interpreter's
    icon, because that is the process pywebview is hosted in - it looks like a
    script someone left running rather than an installed application.
    """
    ico = PROJECT_ROOT / "assets" / "wildfire.ico"
    if not ico.exists():
        try:
            from scripts.install_desktop_app import make_icon

            make_icon(ico)
        except Exception:
            return None
    return str(ico) if ico.exists() else None


def run_desktop(port: int = 7861) -> None:
    import uvicorn
    import webview

    from .server import create_app

    config = uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    threading.Thread(target=server.run, name="console-server", daemon=True).start()
    if not _wait_for_port(port):
        raise RuntimeError(f"console server did not start on port {port}")

    webview.create_window(
        APP_TITLE, f"http://127.0.0.1:{port}",
        width=1440, height=920, min_size=(1100, 700),
    )
    icon = _app_icon()
    # icon= needs pywebview 5+; older builds raise TypeError, and a missing icon
    # is not a reason to refuse to open the window.
    try:
        webview.start(icon=icon) if icon else webview.start()
    except TypeError:
        webview.start()
    server.should_exit = True
