"""Configuration reads: source-derived payloads, synthetic private values only."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyRouter, CudyUnsupportedError, LanConfig


@pytest.mark.parametrize(
    "method,params,result",
    [
        ("get_lan_config", ["network", "lan"], {"proto": "static", "ipaddr": "192.0.2.1"}),
        ("get_dhcp_config", ["dhcp"], {"lan": {"ignore": "1"}, "custom": {}}),
        ("get_wireless_config", ["wireless"], {"radio9": {}, "wlan99": {"key": "synthetic"}}),
    ],
)
def test_configuration_payload(method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result, "error": None}
            parsed = getattr(router, method)()
            assert (parsed.raw if isinstance(parsed, LanConfig) else parsed) == result
            assert post.call_args.kwargs["json"] == {"method": "conf.get_all", "params": params}


@pytest.mark.parametrize("method", ["get_lan_config", "get_dhcp_config", "get_wireless_config"])
@pytest.mark.parametrize("result", [None, [], "", False])
def test_configuration_malformed_result(method, result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError):
                getattr(router, method)()


def test_lan_missing_fields_and_private_raw():
    data = {"proto": "dhcp", "extra": "synthetic-secret"}
    config = LanConfig.from_api_response(data)
    assert config.protocol == "dhcp"
    assert config.ip_address is None
    assert config.gateway is None
    assert config.raw == data and config.raw is not data
    assert "synthetic-secret" not in repr(config)


def test_lan_bad_field_has_sanitized_error():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(
            router, "call_api", return_value={"result": {"ipaddr": ["synthetic-secret"]}}
        ):
            with pytest.raises(CudyAPIError, match="Malformed LAN configuration") as error:
                router.get_lan_config()
            assert "synthetic-secret" not in str(error.value)


def test_configuration_unsupported_remains_distinct():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": {"code": -32601}, "result": None}
            with pytest.raises(CudyUnsupportedError):
                router.get_dhcp_config()
