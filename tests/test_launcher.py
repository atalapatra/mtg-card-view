import json
import socket

from mtgcv import __version__, launcher
from mtgcv.server import find_web_dist


def test_find_web_dist_override(tmp_path, monkeypatch):
    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setenv("MTGCV_WEB_DIST", str(tmp_path))
    assert find_web_dist() == tmp_path
    # A folder without index.html is skipped.
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("MTGCV_WEB_DIST", str(empty))
    assert find_web_dist() != empty


def test_running_port_ignores_stale_state(tmp_path, monkeypatch):
    monkeypatch.setenv("MTGCV_DATA_DIR", str(tmp_path))
    assert launcher._running_port() is None  # no state file
    with socket.socket() as s:  # a port nobody is listening on
        s.bind(("127.0.0.1", 0))
        dead = s.getsockname()[1]
    (tmp_path / "server.json").write_text(json.dumps({"port": dead}), encoding="utf-8")
    assert launcher._running_port() is None
    (tmp_path / "server.json").write_text("not json", encoding="utf-8")
    assert launcher._running_port() is None


def test_running_port_detects_graphmtg(tmp_path, monkeypatch):
    monkeypatch.setenv("MTGCV_DATA_DIR", str(tmp_path))
    (tmp_path / "server.json").write_text(json.dumps({"port": 12345}), encoding="utf-8")
    monkeypatch.setattr(launcher, "_is_graphmtg", lambda port: port == 12345)
    assert launcher._running_port() == 12345


def test_pick_port_falls_back_when_preferred_busy(monkeypatch):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        monkeypatch.setattr(launcher, "PREFERRED_PORT", busy.getsockname()[1])
        port = launcher._pick_port()
        assert port != launcher.PREFERRED_PORT and launcher._port_free(port)


def test_health_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from mtgcv.server import create_app
    from mtgcv.store import DeckStore
    from test_scryfall_and_analyze import make_client

    monkeypatch.setattr("mtgcv.scryfall.MIN_INTERVAL", 0)
    app = create_app(store=DeckStore(tmp_path / "d.sqlite3"), client=make_client(tmp_path, []), web_dist=None)
    r = TestClient(app).get("/api/health")
    assert r.json() == {"app": "graphmtg", "version": __version__}


def test_mac_data_and_cache_dirs(monkeypatch, tmp_path):
    from mtgcv.cache import default_cache_dir
    from mtgcv.store import default_data_dir

    monkeypatch.delenv("MTGCV_DATA_DIR", raising=False)
    monkeypatch.delenv("MTGCV_CACHE_DIR", raising=False)
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert default_data_dir() == tmp_path / "Library" / "Application Support" / "mtg-card-view"
    assert default_cache_dir() == tmp_path / "Library" / "Caches" / "mtg-card-view"
    monkeypatch.setenv("MTGCV_DATA_DIR", str(tmp_path / "override"))
    assert default_data_dir() == tmp_path / "override"


def test_use_menubar(monkeypatch):
    monkeypatch.delenv("GRAPHMTG_CONSOLE", raising=False)
    monkeypatch.delenv("GRAPHMTG_MENUBAR", raising=False)
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    assert not launcher._use_menubar()
    monkeypatch.setattr("sys.platform", "darwin")
    assert launcher._use_menubar()
    monkeypatch.setenv("GRAPHMTG_CONSOLE", "1")
    assert not launcher._use_menubar()


def test_server_runs_and_stops_in_background_thread(tmp_path, monkeypatch):
    """The macOS app runs uvicorn off the main thread and stops it via should_exit."""
    import threading
    import time

    monkeypatch.setenv("MTGCV_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MTGCV_CACHE_DIR", str(tmp_path / "cache"))
    port = launcher._pick_port()
    state = launcher._write_state(port)
    assert json.loads(state.read_text(encoding="utf-8"))["port"] == port
    server = launcher._make_server(port)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if launcher._is_graphmtg(port):
            break
        time.sleep(0.05)
    assert launcher._running_port() == port
    server.should_exit = True
    t.join(timeout=10)
    assert not t.is_alive()
    launcher._clear_state(state)
    assert not state.exists()
