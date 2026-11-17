"""GraphMTG launcher: what GraphMTG.exe (and the `graphmtg` command) runs.

* If GraphMTG is already running, just opens the browser on it and exits.
* Otherwise starts the server on 127.0.0.1 (preferred port, or any free one),
  opens the browser once it responds, and keeps running until the window is closed
  (or Ctrl+C).
* The running port is recorded in <data dir>/server.json so a second launch finds it.

Environment:
    GRAPHMTG_NO_BROWSER=1   don't open a browser (CI smoke test)
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


def _pause_if_double_clicked() -> None:
    """Keep the console open on errors so the message can be read."""
    if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
        try:
            input("\nPress Enter to close this window.")
        except EOFError:
            pass


def main() -> int:
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
        state = _state_file()
        state.write_text(json.dumps({"port": port, "pid": os.getpid(), "version": __version__}), encoding="utf-8")

        print(f"GraphMTG v{__version__} is running at {url}")
        print(f"Your collections are saved in: {default_data_dir()}")
        print("Keep this window open while you use GraphMTG. Close it (or press Ctrl+C) to quit.\n")

        threading.Thread(target=_open_when_ready, args=(port, url), daemon=True).start()

        import uvicorn

        from mtgcv.server import create_app

        try:
            uvicorn.run(create_app(), host=HOST, port=port, log_level="warning")
        finally:
            try:
                if json.loads(state.read_text(encoding="utf-8")).get("pid") == os.getpid():
                    state.unlink()
            except (OSError, ValueError):
                pass
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
