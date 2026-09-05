"""Passive client/Wi-Fi read contracts using synthetic fixtures only."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

CASES = [
    (
        "get_client_names",
        (),
        "devices.get_name",
        [],
        [{"macaddr": "020000000001", "name": "Synthetic", "future": None}],
    ),
    (
        "get_client_traffic_page",
        (),
        "devices.traffic_stat",
        [1, 100],
        {"devcnt": 101, "devlist": [{"upspeed": "0", "downspeed": "123", "future": {"x": False}}]},
    ),
    (
        "get_client_traffic_page",
        (2,),
        "devices.traffic_stat",
        [101, 200],
        {"devcnt": 101, "devlist": [], "future": True},
    ),
    (
        "get_wifi_frequencies",
        (),
        "wifi.get_freqlist",
        [],
        {"future-radio": [{"channel": 1, "future": "0"}]},
    ),
    ("get_wifi_scan_results", (), "wifi.get_aplist", [], None),
    (
        "get_wifi_scan_results",
        ("test-radio",),
        "wifi.get_aplist",
        ["test-radio"],
        [{"ssid": "Synthetic", "rssi": 50, "future": []}],
    ),
    ("get_wifi_scan_results", (), "wifi.get_aplist", [], []),
]


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_wire_shapes_and_raw_preservation(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert getattr(router, reader)(*args) == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {"method": method, "params": params}


@pytest.mark.parametrize("page", [0, -1, True, 1.5, "1", None])
def test_bad_page_never_sends(page):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.get_client_traffic_page(page)
            post.assert_not_called()


@pytest.mark.parametrize("interface", ["", " ", 0, False, []])
def test_bad_interface_never_sends(interface):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.get_wifi_scan_results(interface)
            post.assert_not_called()


@pytest.mark.parametrize(
    "reader,result",
    [
        ("get_client_names", {}),
        ("get_client_names", [1]),
        ("get_client_traffic_page", None),
        ("get_client_traffic_page", {}),
        ("get_client_traffic_page", {"devlist": None}),
        ("get_client_traffic_page", {"devlist": ["private"]}),
        ("get_client_traffic_page", {"devlist": [], "devcnt": -1}),
        ("get_client_traffic_page", {"devlist": [], "devcnt": True}),
        ("get_client_traffic_page", {"devlist": [], "devcnt": "1"}),
        ("get_wifi_frequencies", None),
        ("get_wifi_frequencies", []),
        ("get_wifi_scan_results", {}),
        ("get_wifi_scan_results", ["private"]),
    ],
)
def test_malformed_results(reader, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError) as error:
                getattr(router, reader)()
            assert "private" not in str(error.value)


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_unsupported_and_token_expiry_do_not_fallback_or_scan(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError):
                getattr(router, reader)(*args)
            post.assert_called_once()
        with patch.object(router, "_rpc_request", side_effect=CudyAuthError("expired")) as rpc:
            with patch.object(router, "authenticate") as auth:
                with pytest.raises(CudyAuthError):
                    getattr(router, reader)(*args)
                rpc.assert_called_once()
                auth.assert_not_called()
        assert method in router.READ_METHODS
        assert "wifi.trigger_scan" not in router.READ_METHODS


def test_null_names_and_missing_count():
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": None}):
            assert router.get_client_names() == []
        with patch.object(router, "call_api", return_value={"result": {"devlist": []}}):
            assert router.get_client_traffic_page() == {"devlist": []}
