"""macOS menu-bar front end for GraphMTG.app (D-022).

The packaged Mac app has no window: the server runs in a background thread and a
menu-bar icon offers Open / Show data folder / Quit. Output goes to
<data dir>/graphmtg.log (a windowed app has no console). If the server stops
unexpectedly, an alert points at that log.

Only imported on macOS (rumps needs PyObjC); see launcher._use_menubar.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import traceback
from pathlib import Path

import rumps

from mtgcv import __version__, launcher
from mtgcv.store import default_data_dir


def _log_file() -> Path:
    d = default_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "graphmtg.log"


def _redirect_output() -> Path:
    log = _log_file()
    f = open(log, "w", encoding="utf-8", buffering=1)  # noqa: SIM115 - lives for the whole process
    sys.stdout = sys.stderr = f
    return log


def _menubar_icon() -> str | None:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2] / "packaging"))
    icon = base / "graphmtg-menubar.png"
    return str(icon) if icon.is_file() else None


class GraphMTGApp(rumps.App):
    def __init__(self, url: str, server, thread: threading.Thread, log: Path):
        icon = _menubar_icon()
        super().__init__(
            "GraphMTG",
            title=None if icon else "GraphMTG",
            icon=icon,
            template=True,  # black-on-transparent icon, recolored by macOS for light/dark menu bars
            quit_button=None,
        )
        self.url, self.server, self.thread, self.log = url, server, thread, log
        self.quitting = False
        self.menu = [
            rumps.MenuItem("Open GraphMTG", callback=self.open_app),
            rumps.MenuItem("Show data folder", callback=self.show_data),
            None,
            rumps.MenuItem(f"GraphMTG v{__version__}"),
            rumps.MenuItem("Quit GraphMTG", callback=self.quit_app, key="q"),
        ]
        self.watchdog = rumps.Timer(self.check_server, 1)
        self.watchdog.start()

    def open_app(self, _sender=None) -> None:
        launcher._open_browser(self.url)

    def show_data(self, _sender=None) -> None:
        subprocess.run(["open", str(default_data_dir())], check=False)

    def check_server(self, _timer=None) -> None:
        if self.quitting or self.thread.is_alive():
            return
        self.quitting = True
        rumps.alert(
            title="GraphMTG stopped",
            message=f"The GraphMTG server stopped unexpectedly.\n\nDetails are in {self.log}",
        )
        rumps.quit_application()

    def quit_app(self, _sender=None) -> None:
        self.quitting = True
        self.server.should_exit = True
        self.thread.join(timeout=5)
        rumps.quit_application()


def run_menubar() -> int:
    log = _redirect_output()
    print(f"GraphMTG v{__version__} (menu bar)")

    existing = launcher._running_port()
    if existing:  # rare: LaunchServices normally keeps the .app to one copy
        launcher._open_browser(f"http://{launcher.HOST}:{existing}")
        return 0

    port = launcher._pick_port()
    url = f"http://{launcher.HOST}:{port}"
    state = launcher._write_state(port)
    print(f"Running at {url}; data in {default_data_dir()}")

    server = launcher._make_server(port)

    def serve() -> None:
        try:
            server.run()  # uvicorn skips signal handlers off the main thread
        except BaseException:  # noqa: BLE001 - includes uvicorn's SystemExit on bind errors
            traceback.print_exc()

    thread = threading.Thread(target=serve, name="graphmtg-server", daemon=True)
    thread.start()
    threading.Thread(target=launcher._open_when_ready, args=(port, url), daemon=True).start()
    try:
        GraphMTGApp(url, server, thread, log).run()
    finally:
        launcher._clear_state(state)
    return 0
