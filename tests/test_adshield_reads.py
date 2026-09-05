"""Ad-blocking contracts; all requests and provider responses are synthetic."""

from tests import response_raw

from unittest.mock import patch

import pytest
from requests.exceptions import Timeout

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

CASES = [
    (
        "get_adshield_providers",
        (),
        "adshield.get_providers",
        [],
        {"providers": ["shiild", "adguard"], "future": False},
    ),
    (
        "get_adshield_config",
        (),
        "adshield.get_conf",
        [],
        {"enable": "0", "adguard": {"token": "synthetic-secret"}},
    ),
    (
        "get_adshield_status",
        ("adguard",),
        "adshield.get_status",
        ["adguard"],
        {"adguard": {"code": 401, "requests": {"used": 0}}},
    ),
    (
        "get_adshield_stats",
        ("shiild",),
        "adshield.get_stats",
        ["shiild"],
        {"shiild": {"queries": {"future": [None, "0"]}}},
    ),
]


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_exact_payload_and_raw_wrapper(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert response_raw(getattr(router, reader)(*args)) == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {"method": method, "params": params}


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
@pytest.mark.parametrize("bad", [None, [], "synthetic-secret", 0, False])
def test_non_object_rejected_without_disclosing_values(reader, args, method, params, result, bad):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router, "call_api", return_value={"result": bad}):
            with pytest.raises(CudyAPIError) as error:
                getattr(router, reader)(*args)
            assert "synthetic-secret" not in str(error.value)


@pytest.mark.parametrize("reader,args,method,params,result", CASES)
def test_empty_is_preserved_and_unsupported_is_not_empty(reader, args, method, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": {}}
            assert response_raw(getattr(router, reader)(*args)) == {}
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError):
                getattr(router, reader)(*args)
            assert post.call_count == 2


@pytest.mark.parametrize("reader", ["get_adshield_status", "get_adshield_stats"])
@pytest.mark.parametrize("provider", [None, "", " ", 1, False, []])
def test_bad_provider_never_sends(reader, provider):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                getattr(router, reader)(provider)
            post.assert_not_called()


@pytest.mark.parametrize(
    "reader,method",
    [("get_adshield_status", "adshield.get_status"), ("get_adshield_stats", "adshield.get_stats")],
)
def test_provider_calls_do_not_reauthenticate_or_retry(reader, method):
    with CudyRouter("http://192.0.2.1", "synthetic-password", auth_token="old") as router:
        with patch.object(router, "authenticate") as auth:
            with patch.object(router, "_rpc_request", side_effect=CudyAuthError("expired")) as rpc:
                with pytest.raises(CudyAuthError):
                    getattr(router, reader)("future-provider")
                rpc.assert_called_once()
                auth.assert_not_called()
            router.auth_token = "fresh"
            with patch.object(
                router.session, "post", side_effect=Timeout("synthetic-secret")
            ) as post:
                with pytest.raises(CudyAPIError):
                    getattr(router, reader)("future-provider")
                post.assert_called_once()
        assert method not in router.READ_METHODS
        assert "adshield.oauth" not in router.READ_METHODS
        assert "adshield.get_dashboard" not in router.READ_METHODS
