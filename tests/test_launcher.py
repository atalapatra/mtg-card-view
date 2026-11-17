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
