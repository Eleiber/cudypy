"""VPN/network read contracts using synthetic data and blocked real HTTP."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

CASES = [
    ("get_online_interfaces", (), "net.online_interfaces", [], ["wan", "future_iface"]),
    ("get_vpn_profiles", (), "vpn.get_conf", ["clients"], {"clients": [], "future": None}),
    (
        "get_vpn_profiles",
        ("wireguards",),
        "vpn.get_conf",
        ["wireguards"],
        {"wireguards": {"key": "synthetic-private"}},
    ),
    (
        "get_vpn_client_config",
        ("synthetic-id",),
        "vpn.get_conf",
        ["clients", "synthetic-id"],
        {"clients": [{"id": "synthetic-id", "future": False}]},
    ),
    (
        "get_vpn_connection_page",
        ("wireguards",),
        "vpn.get_connection",
        ["wireguards", 1, 100],
        {"connection_list": [], "total_cnt": 0},
    ),
    (
        "get_vpn_connection_page",
        ("openvpns", 2),
        "vpn.get_connection",
        ["openvpns", 101, 200],
        {
            "connection_list": [{"latest_handshake": "0", "future": []}],
            "total_cnt": 101,
            "future": None,
        },
    ),
]


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_wire_payload_and_raw_result(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert getattr(router, reader)(*args) == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {"method": method, "params": params}


@pytest.mark.parametrize(
    "reader", ["get_vpn_profiles", "get_vpn_client_config", "get_vpn_connection_page"]
)
@pytest.mark.parametrize("identifier", [None, "", " ", False, 1, []])
def test_invalid_identifier_never_sends(reader, identifier):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                getattr(router, reader)(identifier)
            post.assert_not_called()


@pytest.mark.parametrize("page", [None, 0, -1, True, 1.5, "2"])
def test_invalid_page_never_sends(page):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.get_vpn_connection_page("wireguards", page)
            post.assert_not_called()


@pytest.mark.parametrize(
    "reader,args,result",
    [
        ("get_online_interfaces", (), {}),
        ("get_online_interfaces", (), [1]),
        ("get_vpn_profiles", (), None),
        ("get_vpn_profiles", (), []),
        ("get_vpn_client_config", ("id",), None),
        ("get_vpn_client_config", ("id",), "synthetic-private"),
        ("get_vpn_connection_page", ("wireguards",), {}),
        ("get_vpn_connection_page", ("wireguards",), {"connection_list": None}),
        ("get_vpn_connection_page", ("wireguards",), {"connection_list": [1]}),
        ("get_vpn_connection_page", ("wireguards",), {"connection_list": [], "total_cnt": True}),
        ("get_vpn_connection_page", ("wireguards",), {"connection_list": [], "total_cnt": -1}),
        ("get_vpn_connection_page", ("wireguards",), {"connection_list": [], "total_cnt": "1"}),
    ],
)
def test_bad_response(reader, args, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError) as error:
                getattr(router, reader)(*args)
            assert "synthetic-private" not in str(error.value)


def test_empty_and_unknown_values():
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": None}):
            assert router.get_online_interfaces() == []
        with patch.object(router, "call_api", return_value={"result": {}}):
            assert router.get_vpn_profiles() == {}
        with patch.object(router, "call_api", return_value={"result": {"connection_list": []}}):
            assert router.get_vpn_connection_page("wireguards") == {"connection_list": []}


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_errors_and_bounded_replay(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", "synthetic-password", auth_token="old") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError):
                getattr(router, reader)(*args)
            post.assert_called_once()
        with patch.object(router, "_rpc_request", side_effect=CudyAuthError("expired")) as rpc:
            with patch.object(router, "authenticate") as auth:

                def refresh():
                    router.auth_token = "new"
                    return True

                auth.side_effect = refresh
                with pytest.raises(CudyAuthError):
                    getattr(router, reader)(*args)
                auth.assert_called_once()
                assert rpc.call_count == 2
                assert all(call.args[1] == method for call in rpc.call_args_list)
        assert "vpn.export_conf" not in router.READ_METHODS
        assert "net.online_check" not in router.READ_METHODS
