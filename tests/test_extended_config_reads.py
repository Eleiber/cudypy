"""Passive configuration RPC contracts, verified without hardware mutations."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

CASES = [
    ("get_iptv_config", (), "iptv.get_conf", [], {"enabled": "0", "modes": [{"future": None}]}),
    (
        "get_easymesh_config",
        (),
        "easymesh.get_conf",
        [],
        {"disabled": "1", "role": "agent", "future": False},
    ),
    (
        "get_multi_ssid_interfaces",
        (),
        "multi_ssid.get_all_multi_ssid_iface",
        [],
        ["custom_section"],
    ),
    (
        "get_multi_ssid_config",
        ("custom_section",),
        "multi_ssid.get_conf",
        ["wireless", "custom_section"],
        {"key": "synthetic-secret", "future": [0]},
    ),
    (
        "get_parental_control_config",
        (),
        "parental_control.get_conf",
        [],
        [{"name": "Synthetic group", "schedule": [], "future": None}],
    ),
    (
        "get_parental_control_config",
        ("Synthetic group",),
        "parental_control.get_conf",
        ["Synthetic group"],
        [],
    ),
]


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_exact_request_and_lossless_response(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert getattr(router, reader)(*args) == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {"method": method, "params": params}


@pytest.mark.parametrize(
    "reader,args,result,expected",
    [
        ("get_multi_ssid_interfaces", (), None, []),
        ("get_multi_ssid_interfaces", (), [], []),
        ("get_multi_ssid_config", ("missing",), None, None),
        ("get_multi_ssid_config", ("known",), {}, {}),
        ("get_parental_control_config", (), None, []),
        ("get_parental_control_config", ("missing",), None, []),
        ("get_iptv_config", (), {}, {}),
        ("get_easymesh_config", (), {}, {}),
    ],
)
def test_absent_and_empty_results(reader, args, result, expected):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            assert getattr(router, reader)(*args) == expected


@pytest.mark.parametrize(
    "reader,args",
    [
        ("get_multi_ssid_config", ("section",)),
        ("get_parental_control_config", ()),
        ("get_iptv_config", ()),
        ("get_easymesh_config", ()),
        ("get_multi_ssid_interfaces", ()),
    ],
)
@pytest.mark.parametrize("result", ["synthetic-private", 1, [1]])
def test_wrong_shapes_do_not_disclose_values(reader, args, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError) as error:
                getattr(router, reader)(*args)
            assert "synthetic-private" not in str(error.value)


@pytest.mark.parametrize("reader", ["get_multi_ssid_config", "get_parental_control_config"])
@pytest.mark.parametrize("identifier", ["", " ", 1, False, []])
def test_invalid_identifiers_do_not_send(reader, identifier):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                getattr(router, reader)(identifier)
            post.assert_not_called()


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_unsupported_stays_an_error(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError):
                getattr(router, reader)(*args)
            post.assert_called_once()


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_read_auth_replay_is_bounded(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", "synthetic-password", auth_token="old") as router:
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
                assert method in router.READ_METHODS
                assert all(call.args[1] == method for call in rpc.call_args_list)
