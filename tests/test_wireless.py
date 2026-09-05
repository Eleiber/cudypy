"""Wi-Fi configuration contracts; mutations are mocked, never sent to hardware."""

from unittest.mock import patch

import pytest
import requests

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, WirelessInterface


def test_wireless_model_preserves_unknown_fields_without_password_repr():
    data = {"ssid": "Example", "disabled": "0", "hidden": 1, "key": "synthetic-secret", "extra": 4}
    model = WirelessInterface.from_api_response("wlan99", data)
    assert model.disabled is False and model.hidden is True
    assert model.encryption is None
    assert model.raw == data and model.raw is not data
    assert "synthetic-secret" not in repr(model)


def test_selected_section_read_uses_configuration_payload():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": {"custom": {"ssid": "Example"}}}
            assert router.get_wireless_interface("custom").ssid == "Example"
            assert post.call_args.kwargs["json"] == {
                "method": "conf.get_all",
                "params": ["wireless"],
            }
            assert router.get_wireless_interface("absent") is None


@pytest.mark.parametrize("data", [None, [], {"disabled": "bad"}, {"ssid": 5}])
def test_bad_wireless_section(data):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router, "get_wireless_config", return_value={"custom": data}):
            with pytest.raises(CudyAPIError):
                router.get_wireless_interface("custom")


@pytest.mark.parametrize(
    "config",
    [
        {"iface": {"wlan00": {"disabled": 1}}},
        {"iface": {"wlan00": {"ssid": "Example", "encryption": "psk2", "key": "synthetic-secret"}}},
        {"radio": {"radio0": {"channel": "auto"}}, "mld": {"mld0": {"disabled": 1}}},
    ],
)
def test_wifi_config_wire_snapshot(config):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": None}
            assert router.set_wifi_config(config) is None
            payload = post.call_args.kwargs["json"]
            assert payload == {"method": "wifi.set_conf", "params": [config]}
            assert payload["params"][0] is not config
            assert "wifi.set_conf" not in router.READ_METHODS


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        [],
        {"wlan00": {"disabled": 1}},
        {"iface": {}},
        {"iface": {"": {"disabled": 1}}},
        {"iface": {"wlan00": {}}},
        {"access_filter": True},
        {"iface": {"wlan00": {"key": object()}}},
        {"radio": {"radio0": {"channel": float("nan")}}},
    ],
)
def test_invalid_wifi_config_never_sends(config):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.set_wifi_config(config)
            post.assert_not_called()


@pytest.mark.parametrize("failure", ["auth", "timeout"])
def test_wifi_write_never_replays(failure):
    with CudyRouter(
        "http://192.0.2.1", password="test-password", auth_token="test-token"
    ) as router:
        with (
            patch.object(router.session, "post") as post,
            patch.object(router, "authenticate") as auth,
        ):
            if failure == "auth":
                post.return_value.json.return_value = {"error": {"code": -32003}}
                expected = CudyAuthError
            else:
                post.side_effect = requests.Timeout("synthetic timeout")
                expected = CudyAPIError
            with pytest.raises(expected):
                router.set_wifi_config({"iface": {"wlan00": {"disabled": 1}}})
            post.assert_called_once()
            auth.assert_not_called()


def test_nonstring_configuration_keys_are_not_silently_rewritten():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.set_wifi_config({"iface": {"wlan00": {1: "unexpected"}}})
            post.assert_not_called()


def test_recursive_configuration_fails_without_sending():
    fields = {"disabled": 1}
    fields["cycle"] = fields
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.set_wifi_config({"iface": {"wlan00": fields}})
            post.assert_not_called()
