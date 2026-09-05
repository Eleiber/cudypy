"""Source-backed feature reads and firmware result variants."""

from decimal import Decimal
from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyRouter, CudyUnsupportedError, EthernetPort, RateLimit


@pytest.mark.parametrize(
    "reader,args,method,params,result",
    [
        ("get_work_modes", (), "conf.get_workmodes", [], [{"mode": "ap", "name": "Access Point"}]),
        ("get_wifi_schedule", (), "wifi.get_schedule", [], []),
        ("get_wds_status", (), "wifi.get_wds_status", [], None),
        ("get_wds_status", ("wlan10",), "wifi.get_wds_status", ["wlan10"], {"up": True}),
        ("get_wps_status", (), "wifi.get_wps_status", [], "idle"),
        ("get_vpn_status", (), "vpn.get_status", [], []),
        (
            "get_client_info",
            ("02-00-00-00-00-01",),
            "devices.get_devinfo",
            ["02:00:00:00:00:01"],
            None,
        ),
        (
            "get_client_rate_limit",
            ("020000000001",),
            "conf.get_rate_limit",
            ["02:00:00:00:00:01"],
            None,
        ),
        (
            "get_client_internet_schedule",
            ("02:00:00:00:00:01",),
            "conf.get_internet_schedule",
            ["02:00:00:00:00:01"],
            [],
        ),
    ],
)
def test_wire_payloads(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"id": None, "result": result, "error": None}
            assert getattr(router, reader)(*args) == result
            assert post.call_args.kwargs["json"] == {"method": method, "params": params}


@pytest.mark.parametrize("mac", ["", "00:11", "00:11-22:33:44:55", "00:11:22:33:44:gg", None])
def test_invalid_client_identifier_never_sends(mac):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.get_client_info(mac)
            post.assert_not_called()


@pytest.mark.parametrize(
    "reader,result",
    [
        ("get_work_modes", {}),
        ("get_wifi_schedule", ["bad"]),
        ("get_wds_status", []),
        ("get_wps_status", {}),
    ],
)
def test_malformed_result(reader, result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError):
                getattr(router, reader)()


def test_absent_schedule_is_empty_but_unsupported_is_error():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": None, "error": None}
            assert router.get_wifi_schedule() == []
            post.return_value.json.return_value = {"result": None, "error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError) as error:
                router.get_client_internet_schedule("020000000001")
            assert error.value.code == -32601


@pytest.mark.parametrize("field", ["auto", "autoneg"])
def test_port_firmware_variants(field):
    data = {
        "port": 1,
        "label": "LAN1",
        "link": True,
        "speed": 1000,
        "duplex": "1",
        field: "0",
        "txbyte": 0,
        "rxbyte": 2**55,
        "future": 1,
    }
    port = EthernetPort.from_api_response(data)
    assert port.auto_negotiation is False
    assert port.full_duplex is True
    assert port.speed_mbps == 1000
    assert port.rx_bytes == 2**55
    assert port.tx_bytes == 0
    assert port.raw["future"] == 1
    assert "future" not in repr(port)


def test_missing_port_fields_are_unknown():
    port = EthernetPort.from_api_response({"port": 0})
    assert port.link_up is None
    assert port.auto_negotiation is None


def test_decimal_rate_limits_and_zero_preserved():
    limit = RateLimit.from_api_response({"ddrate": "12.345", "uurate": "0"})
    assert limit.download_mbps == Decimal("12.345")
    assert limit.upload_mbps == Decimal(0)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", -1, True, {}])
def test_invalid_rates(bad):
    with pytest.raises(ValueError):
        RateLimit.from_api_response({"ddrate": bad})


def test_typed_router_results():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router, "call_api", return_value={"result": [{"port": 0, "auto": True}]}):
            assert router.get_ethernet_ports()[0].auto_negotiation is True
        with patch.object(router, "call_api", return_value={"result": {"ddrate": "2.5"}}):
            assert router.get_client_rate_limit("020000000001").download_mbps == Decimal("2.5")
        with patch.object(
            router,
            "call_api",
            return_value={"result": {"macaddr": "02:00:00:00:00:01", "iface": "wlan10"}},
        ):
            assert router.get_client_info("020000000001").connection_type == "wifi"
