"""Entry point: python -m src.wildfire.console  ->  http://127.0.0.1:7861"""

from __future__ import annotations

import argparse
import sys
import webbrowser


def main() -> None:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Wildfire operations console (offline).")
    ap.add_argument("--port", type=int, default=7861)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--desktop", action="store_true",
                    help="open as a native app window (pywebview) instead of a browser tab")
    args = ap.parse_args()

    if args.desktop:
        from .desktop import run_desktop

        run_desktop(port=args.port)
        return

    import uvicorn

    from .server import create_app

    app = create_app()
    url = f"http://127.0.0.1:{args.port}"
    print(f"Wildfire console: {url}")
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
