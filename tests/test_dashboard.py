"""Optional Flask UI checks; no server or router is started."""

from unittest.mock import Mock
from cudypy import SystemStatus, InterfaceStatus

import pytest

pytest.importorskip("flask")
from dashboard import app as dashboard


@pytest.fixture
def client(monkeypatch):
    router = Mock()
    router.authenticate.return_value = True
    router.get_system_info.return_value = SystemStatus.from_api_response({"model": "WR3000"})
    router.get_network_status.return_value = InterfaceStatus.from_api_response({"is_up": True})
    router.get_devices.return_value = []
    monkeypatch.setattr(dashboard, "router_instance", router)
    monkeypatch.setattr(dashboard, "ROUTER_URL", "http://192.0.2.1")
    monkeypatch.setattr(dashboard, "ROUTER_PASSWORD", "")
    monkeypatch.setattr(dashboard, "ROUTER_TOKEN", "secret")
    return dashboard.app.test_client()


def test_local_reads(client):
    response = client.get("/api/system", base_url="http://127.0.0.1:5000")
    assert response.status_code == 200
    assert response.json == {"system": {"model": "WR3000"}}
    response = client.get("/api/network", base_url="http://127.0.0.1:5000")
    assert response.status_code == 200
    assert response.json == {"network": {"is_up": True}}


def test_host_and_origin_checks(client):
    assert client.get("/api/system", base_url="http://evil.example:5000").status_code == 403
    response = client.post(
        "/api/refresh", base_url="http://127.0.0.1:5000", headers={"Origin": "http://evil.example"}
    )
    assert response.status_code == 403
    dashboard.router_instance.close.assert_not_called()


def test_router_change_does_not_forward_old_token(client):
    response = client.post(
        "/api/config", base_url="http://127.0.0.1:5000", json={"url": "http://192.0.2.2"}
    )
    assert response.status_code == 400
    assert dashboard.ROUTER_URL == "http://192.0.2.1"
    dashboard.router_instance.close.assert_not_called()


def test_config_does_not_return_credentials(client):
    response = client.get("/api/config", base_url="http://127.0.0.1:5000")
    assert "secret" not in response.get_data(as_text=True)


def test_page_renders_without_connecting(client):
    response = client.get("/", base_url="http://127.0.0.1:5000")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="trafficGraph"' in html
    assert "/static/js/history.js" in html
    assert "fonts.googleapis.com" not in html
    dashboard.router_instance.authenticate.assert_not_called()
