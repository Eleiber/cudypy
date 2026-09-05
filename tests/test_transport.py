"""Transport regressions; all responses are synthetic and never sent to routers."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter


def test_token_session_needs_neither_password_nor_discovery():
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router, "_discover_salt_and_devid") as discovery:
            with patch.object(router.session, "post") as post:
                post.return_value.json.return_value = {"result": {"model": "WR3000"}}
                assert router.get_system_info() == {"model": "WR3000"}
                discovery.assert_not_called()
                assert "devid" not in post.call_args.kwargs["json"]
                assert post.call_args.kwargs["params"] == {"auth": "session-token"}
                assert post.call_args.kwargs["allow_redirects"] is False
                assert router.session.trust_env is False


@pytest.mark.parametrize("body", [[], None, "text", {"error": "bad"}])
def test_invalid_envelope_is_api_error(body):
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = body
            with pytest.raises(CudyAPIError):
                router.call_api("system.info")


def test_token_expiry_does_not_attempt_password_login():
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {
                "id": -1,
                "error": {"code": -32003, "message": "expired"},
            }
            with pytest.raises(CudyAuthError):
                router.get_system_info()
            assert post.call_count == 1
            assert router.auth_token is None


def test_closed_session_cannot_be_reused():
    router = CudyRouter("http://192.0.2.1", auth_token="session-token")
    router.close()
    with pytest.raises(CudyAPIError, match="closed"):
        router.get_system_info()


@pytest.mark.parametrize(
    "url",
    [
        "ftp://router",
        "http://user:pass@router",
        "http://router/path",
        "http://router?auth=secret",
        "http://router#fragment",
    ],
)
def test_reject_non_origin_urls(url):
    with pytest.raises(ValueError):
        CudyRouter(url, auth_token="session-token")


def test_interface_payload_matches_app():
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router, "call_api", return_value={"result": {}}) as call:
            router.get_network_status("wisp")
            call.assert_called_once_with("net.iface_status", ["wisp"])


def test_reboot_is_not_replayed():
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router, "call_api", return_value={"result": True}) as call:
            assert router.reboot()
            call.assert_called_once_with("system.reboot", retry_auth=False)


def test_network_error_does_not_expose_token():
    import requests

    with CudyRouter("http://192.0.2.1", auth_token="secret-token") as router:
        with patch.object(
            router.session,
            "post",
            side_effect=requests.ConnectionError("failed http://192.0.2.1/?auth=secret-token"),
        ) as post:
            with pytest.raises(CudyAPIError) as exc:
                router.get_system_info()
            assert "secret-token" not in str(exc.value)
            assert post.call_count == 1


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirect_is_rejected(status):
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.status_code = status
            with pytest.raises(CudyAPIError, match="redirect"):
                router.get_system_info()
            post.return_value.json.assert_not_called()


def test_custom_method_auth_failure_is_never_replayed(mock_router):
    mock_router.auth_token = "token"
    with patch.object(mock_router.session, "post") as post:
        post.return_value.json.return_value = {"error": {"code": -32003}}
        with patch.object(mock_router, "authenticate") as authenticate:
            with pytest.raises(CudyAuthError):
                mock_router.call_api("custom.action")
            authenticate.assert_not_called()
            assert post.call_count == 1


def test_native_device_fields():
    from cudypy import Device

    device = Device.from_api_response(
        {
            "macaddr": "AA:BB:CC:DD:EE:FF",
            "ipaddr": "192.0.2.5",
            "rssi": "58",
            "internet": "0",
            "vpn": "false",
            "interface": "eth1",
            "name": "Office",
        }
    )
    assert device.mac_address == "aa:bb:cc:dd:ee:ff"
    assert device.signal_strength == -42
    assert device.device_name == "Office"
    assert device.connection_type == "ethernet"
    assert not device.has_internet
    assert not device.is_vpn


@pytest.mark.parametrize(
    "reader,method",
    [
        ("get_supported_features", "feature.supported"),
        ("get_ethernet_status", "eth.getstatus"),
        ("get_mesh_clients", "mesh.get_clients"),
        ("get_traffic_stats", "net.traffic_stat"),
    ],
)
def test_additional_read_payloads(reader, method):
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": {"firmware_field": [1, 2]}}
            assert getattr(router, reader)() == {"firmware_field": [1, 2]}
            assert post.call_args.kwargs["json"] == {"method": method, "params": []}


def test_discovery_timeout_closes_resources():
    from cudypy import CudyDiscoveryError

    with CudyRouter("http://192.0.2.1", "password") as router:
        with patch("cudypy.core.router.Zeroconf") as zc:
            with patch("cudypy.core.router.ServiceBrowser") as browser:
                with patch.object(
                    router._CudyServiceListener, "wait_for_discovery", return_value=False
                ):
                    with pytest.raises(CudyDiscoveryError):
                        router._discover_salt_and_devid()
                browser.return_value.cancel.assert_called_once()
                zc.return_value.close.assert_called_once()


def test_explicit_salt_avoids_mdns():
    with CudyRouter("http://192.0.2.1", "password", salt="known-salt") as router:
        with patch("cudypy.core.router.Zeroconf") as zc:
            assert router._discover_salt_and_devid()
            zc.assert_not_called()


@pytest.mark.parametrize("error", [{}, [], "", False, 0])
def test_falsey_rpc_errors_cannot_masquerade_as_success(error):
    with CudyRouter("http://192.0.2.1", auth_token="session-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": error, "result": {}}
            with pytest.raises(CudyAPIError, match="malformed RPC error"):
                router.get_system_info()


def test_failed_forced_login_clears_old_cookie(mock_router):
    mock_router.auth_token = "old-session-token"
    mock_router.session.cookies.set("sysauth", "old-session-token")
    with patch.object(mock_router.session, "post") as post:
        post.return_value.json.return_value = {"result": "000000"}
        assert mock_router.authenticate(force=True) is False
        assert mock_router.auth_token is None
        assert not mock_router.session.cookies
        assert post.call_count == 1


def test_unsupported_firmware_method_retains_rpc_code():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {
                "id": None,
                "result": None,
                "error": {"code": -32601, "message": "Method not found."},
            }
            with pytest.raises(CudyAPIError) as error:
                router.get_traffic_stats()
            assert error.value.code == -32601
            assert post.call_count == 1


def test_html_response_is_reported_as_invalid_json():
    import requests
    response = requests.Response()
    response.status_code = 200
    response._content = b"<html>Login required</html>"
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post", return_value=response):
            with pytest.raises(CudyAPIError, match="invalid JSON"):
                router.get_system_info()


@pytest.mark.parametrize(
    "interface,iface,rssi,expected_type",
    [
        ("vap8", "wlan10", 60, "wifi"),
        ("vap0", "wlan00", 43, "wifi"),
        ("eth2", "eth", None, "ethernet"),
    ],
)
def test_newer_firmware_client_layout(interface, iface, rssi, expected_type):
    from cudypy import Device

    device = Device.from_api_response(
        {
            "macaddr": "02:00:00:00:00:01",
            "ipaddr": "192.0.2.1",
            "interface": interface,
            "iface": iface,
            "rssi": rssi,
            "online": "120",
            "inactive": "0",
            "upspeed": "1024",
            "downspeed": "2048",
            "internet": True,
            "vpn": False,
        }
    )
    assert device.connection_type == expected_type
    assert device.signal_strength == (rssi - 100 if rssi is not None else None)
    assert device.bandwidth_up == 1024
    assert device.formatted_bandwidth_down == "2.0 KiB/s"
