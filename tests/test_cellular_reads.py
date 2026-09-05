"""Synthetic cellular wire contracts; never enable a modem or reset counters."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

CASES = [
    (
        "get_cellular_status",
        "cellular.getstatus",
        {"rx_bytes": 0, "imsi": "synthetic-private", "future": False},
    ),
    (
        "get_cellular_data_config",
        "cellular.get_data",
        [{"simslot": "1", "monthly_data": "0", "future": None}],
    ),
    (
        "get_cellular_statistics",
        "cellular.get_statistics",
        {"cur_traffic": 0, "his_traffic": 2**60, "future": []},
    ),
]


@pytest.mark.parametrize("reader,method,result", CASES)
def test_payload_and_raw_values(reader, method, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert getattr(router, reader)("synthetic-modem") == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {
                "method": method,
                "params": ["synthetic-modem"],
            }


@pytest.mark.parametrize("reader,method,result", CASES)
@pytest.mark.parametrize("interface", [None, "", " ", False, 1, []])
def test_invalid_interface_never_sends(reader, method, result, interface):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                getattr(router, reader)(interface)
            post.assert_not_called()


@pytest.mark.parametrize(
    "reader,bad",
    [
        ("get_cellular_status", None),
        ("get_cellular_status", []),
        ("get_cellular_statistics", None),
        ("get_cellular_statistics", []),
        ("get_cellular_data_config", {}),
        ("get_cellular_data_config", ["synthetic-private"]),
    ],
)
def test_malformed_results(reader, bad):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": bad}):
            with pytest.raises(CudyAPIError) as error:
                getattr(router, reader)("synthetic-modem")
            assert "synthetic-private" not in str(error.value)


def test_empty_and_absent():
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": None}):
            assert router.get_cellular_data_config("synthetic-modem") == []
        with patch.object(router, "call_api", return_value={"result": {}}):
            assert router.get_cellular_status("synthetic-modem") == {}
            assert router.get_cellular_statistics("synthetic-modem") == {}


@pytest.mark.parametrize("reader,method,result", CASES)
def test_unsupported_and_bounded_auth_replay(reader, method, result):
    with CudyRouter("http://192.0.2.1", "synthetic-password", auth_token="old") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError):
                getattr(router, reader)("synthetic-modem")
            post.assert_called_once()
        with patch.object(router, "_rpc_request", side_effect=CudyAuthError("expired")) as rpc:
            with patch.object(router, "authenticate") as auth:

                def refresh():
                    router.auth_token = "new"
                    return True

                auth.side_effect = refresh
                with pytest.raises(CudyAuthError):
                    getattr(router, reader)("synthetic-modem")
                auth.assert_called_once()
                assert rpc.call_count == 2
                assert all(call.args[1] == method for call in rpc.call_args_list)
        assert "cellular.clear_statistics" not in router.READ_METHODS
        assert "cellular.read_sms" not in router.READ_METHODS
