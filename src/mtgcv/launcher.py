"""GraphMTG launcher: what GraphMTG.exe, GraphMTG.app and the `graphmtg` command run.

* If GraphMTG is already running, just opens the browser on it and exits.
* Otherwise starts the server on 127.0.0.1 (preferred port, or any free one),
  opens the browser once it responds, and keeps running until the user quits.
* The running port is recorded in <data dir>/server.json so a second launch finds it.

Two front ends:
* console (Windows exe, `graphmtg` in a terminal): close the window or Ctrl+C to quit.
* menu bar (the macOS app, see macapp.py): a menu-bar icon with Open / Quit.

Environment:
    GRAPHMTG_NO_BROWSER=1   don't open a browser (CI smoke test)
    GRAPHMTG_MENUBAR=1      use the menu-bar front end outside the packaged app (macOS only)
    GRAPHMTG_CONSOLE=1      force the console front end in the packaged macOS app (debugging)
    MTGCV_DATA_DIR / MTGCV_CACHE_DIR   as for `mtgcv serve`
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import httpx

from mtgcv import __version__
from mtgcv.store import default_data_dir

PREFERRED_PORT = 8737
HOST = "127.0.0.1"


def _state_file() -> Path:
    d = default_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "server.json"


def _is_graphmtg(port: int) -> bool:
    try:
        r = httpx.get(f"http://{HOST}:{port}/api/health", timeout=1.0)
        return r.status_code == 200 and r.json().get("app") == "graphmtg"
    except (httpx.HTTPError, ValueError):
        return False


def _running_port() -> int | None:
    """Port of an already-running GraphMTG, if any."""
    try:
        port = int(json.loads(_state_file().read_text(encoding="utf-8"))["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return port if _is_graphmtg(port) else None


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def _pick_port() -> int:
    if _port_free(PREFERRED_PORT):
        return PREFERRED_PORT
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _open_browser(url: str) -> None:
    if os.environ.get("GRAPHMTG_NO_BROWSER") != "1":
        webbrowser.open(url)


def _open_when_ready(port: int, url: str) -> None:
    for _ in range(200):  # up to ~20 s (first start unpacks the exe)
        if _is_graphmtg(port):
            _open_browser(url)
            return
        time.sleep(0.1)


def _write_state(port: int) -> Path:
    state = _state_file()
    state.write_text(json.dumps({"port": port, "pid": os.getpid(), "version": __version__}), encoding="utf-8")
    return state


def _clear_state(state: Path) -> None:
    """Remove server.json if it is still ours (another instance may have replaced it)."""
    try:
        if json.loads(state.read_text(encoding="utf-8")).get("pid") == os.getpid():
            state.unlink()
    except (OSError, ValueError):
        pass


def _make_server(port: int):
    import uvicorn

    from mtgcv.server import create_app

    return uvicorn.Server(uvicorn.Config(create_app(), host=HOST, port=port, log_level="warning"))


def _use_menubar() -> bool:
    if sys.platform != "darwin" or os.environ.get("GRAPHMTG_CONSOLE") == "1":
        return False
    return getattr(sys, "frozen", False) or os.environ.get("GRAPHMTG_MENUBAR") == "1"


def _pause_if_double_clicked() -> None:
    """Keep the console open on errors so the message can be read."""
    if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
        try:
            input("\nPress Enter to close this window.")
        except EOFError:
            pass


def main() -> int:
    if _use_menubar():
        from mtgcv.macapp import run_menubar

        return run_menubar()
    if hasattr(sys.stdout, "reconfigure"):
        # line_buffering: the startup message shows immediately even when output is redirected
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    try:
        existing = _running_port()
        if existing:
            url = f"http://{HOST}:{existing}"
            print(f"GraphMTG is already running at {url}. Opening it in your browser.")
            _open_browser(url)
            return 0

        port = _pick_port()
        url = f"http://{HOST}:{port}"
        state = _write_state(port)

        print(f"GraphMTG v{__version__} is running at {url}")
        print(f"Your collections are saved in: {default_data_dir()}")
        print("Keep this window open while you use GraphMTG. Close it (or press Ctrl+C) to quit.\n")

        threading.Thread(target=_open_when_ready, args=(port, url), daemon=True).start()

        try:
            _make_server(port).run()
        finally:
            _clear_state(state)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("GraphMTG hit an error and has to stop:\n")
        traceback.print_exc()
        _pause_if_double_clicked()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
