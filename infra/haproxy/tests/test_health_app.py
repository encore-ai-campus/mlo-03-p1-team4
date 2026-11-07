"""F-70: 업무 HTTP 응답성·과부하 격리·primary 장애 판정 회귀."""

import importlib.util
import socket
from http.client import HTTPConnection as RealHTTPConnection
from http.client import RemoteDisconnected
from pathlib import Path
from threading import Event, Thread
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def probe(monkeypatch):
    path = Path(__file__).parents[1] / "health_app.py"
    spec = importlib.util.spec_from_file_location("isolated_health_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connection = MagicMock()
    connection.getresponse.return_value.status = 200
    factory = MagicMock(return_value=connection)
    storage = MagicMock(return_value={"status": "ok"})
    monkeypatch.setattr(module, "HTTPConnection", factory)
    monkeypatch.setattr(module, "get_health", storage)
    for name in ("stop_health_checks", "close_mongo", "close_databases"):
        monkeypatch.setattr(module, name, lambda: None)
    with TestClient(module.app) as client:
        yield module, client, connection, factory, storage


@pytest.mark.parametrize("status", [200, 503])
def test_responsive_or_overloaded_api_keeps_independent_storage_check(probe, status):
    _, client, connection, factory, storage = probe
    connection.getresponse.return_value.status = status
    response = client.get("/health")
    assert response.status_code == 200
    factory.assert_called_once_with("127.0.0.1", 8000, timeout=0.2)
    connection.sock.settimeout.assert_called_once_with(0.3)
    connection.request.assert_called_once_with(
        "HEAD", "/openapi.json", headers={"Connection": "close"}
    )
    storage.assert_called_once_with()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize("status", [301, 404, 500, 502])
def test_unexpected_api_status_is_unavailable(probe, status):
    _, client, connection, _, storage = probe
    connection.getresponse.return_value.status = status
    assert client.get("/health").status_code == 503
    storage.assert_not_called()
    connection.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("operation", "error"),
    [
        ("connect", ConnectionRefusedError()),
        ("getresponse", TimeoutError()),
        ("getresponse", RemoteDisconnected()),
        ("request", BrokenPipeError()),
    ],
)
def test_connection_or_http_failure_is_unavailable(probe, operation, error):
    _, client, connection, _, storage = probe
    getattr(connection, operation).side_effect = error
    assert client.get("/health").status_code == 503
    storage.assert_not_called()
    connection.close.assert_called_once_with()


def test_overload_does_not_hide_primary_failure(probe):
    module, client, connection, _, storage = probe
    connection.getresponse.return_value.status = 503
    storage.side_effect = module.fail("SERVICE_UNAVAILABLE", 503)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"


def test_degraded_storage_response_is_preserved(probe):
    _, client, _, _, storage = probe
    storage.return_value = {"status": "degraded", "mongo": "down"}
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == storage.return_value


def test_tcp_accept_without_http_response_is_unavailable(probe, monkeypatch):
    module, client, _, _, storage = probe
    accepted = Event()
    release = Event()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(2)
        port = listener.getsockname()[1]

        def stalled_server():
            with listener.accept()[0]:
                accepted.set()
                release.wait(2)

        worker = Thread(target=stalled_server, daemon=True)
        worker.start()
        monkeypatch.setattr(
            module,
            "HTTPConnection",
            lambda host, port_ignored, timeout: RealHTTPConnection(host, port, timeout=timeout),
        )
        try:
            assert client.get("/health").status_code == 503
            assert accepted.is_set()
            storage.assert_not_called()
        finally:
            release.set()
            worker.join(timeout=3)
        assert not worker.is_alive()
