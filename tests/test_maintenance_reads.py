"""Read-only maintenance and legacy-client contracts; no firmware actions."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

CASES = [
    (
        "get_legacy_devices",
        (),
        "devices.get_devlist",
        [],
        [{"macaddr": "020000000001", "future": None}],
    ),
    (
        "get_firmware_update_info",
        (),
        "system.upgrade_fwinfo",
        [],
        {"current_firmware": "synthetic", "future": {"x": False}},
    ),
    (
        "get_firmware_check_status",
        ("synthetic-target",),
        "system.upgrade_checkstatus",
        ["synthetic-target"],
        "unknown-future-state",
    ),
    ("get_apply_status", (), "apply_status", [], "unknown-future-state"),
]


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_exact_single_request(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert getattr(router, reader)(*args) == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {"method": method, "params": params}


@pytest.mark.parametrize(
    "reader,args,result,expected",
    [
        ("get_legacy_devices", (), None, []),
        ("get_firmware_update_info", (), {}, {}),
        ("get_firmware_check_status", ("known",), None, None),
        ("get_firmware_check_status", ("known",), "", ""),
        ("get_apply_status", (), None, None),
        ("get_apply_status", (), "", ""),
    ],
)
def test_absent_and_empty(reader, args, result, expected):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            assert getattr(router, reader)(*args) == expected


@pytest.mark.parametrize(
    "reader,args,result",
    [
        ("get_legacy_devices", (), {}),
        ("get_legacy_devices", (), ["private"]),
        ("get_firmware_update_info", (), None),
        ("get_firmware_update_info", (), []),
        ("get_firmware_check_status", ("known",), {}),
        ("get_firmware_check_status", ("known",), 1),
        ("get_apply_status", (), False),
        ("get_apply_status", (), []),
    ],
)
def test_malformed_results(reader, args, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError) as error:
                getattr(router, reader)(*args)
            assert "private" not in str(error.value)


@pytest.mark.parametrize("target", [None, "", " ", 0, False, []])
def test_bad_target_never_sends(target):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.get_firmware_check_status(target)
            post.assert_not_called()


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_unsupported_and_bounded_auth_replay(reader, args, method, params, result):
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
        assert (
            not {
                "system.zonename",
                "system.upgrade_check",
                "system.upgrade",
                "system.upgrade_download",
            }
            & router.READ_METHODS
        )
