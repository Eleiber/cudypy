"""Mutation wire contracts from the APK. Never contact hardware."""

from decimal import Decimal
from unittest.mock import patch

import pytest
import requests

from cudypy import CudyAPIError, CudyAuthError, CudyRouter

MAC = "02:00:00:00:00:01"


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("set_client_name", {"name": "Desk"}),
        ("set_client_internet_blocked", {"blocked": True}),
        ("set_client_rate_limit", {"download_mbps": 1, "upload_mbps": 1}),
        ("clear_client_rate_limit", {}),
    ],
)
def test_invalid_mac_never_sends(method, kwargs):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                getattr(router, method)("invalid", **kwargs)
            post.assert_not_called()


@pytest.mark.parametrize(
    "method,kwargs,rpc,params",
    [
        (
            "set_client_name",
            {"name": "Desk"},
            "devices.set_name",
            [MAC, "Desk", "other", "undefined"],
        ),
        (
            "set_client_name",
            {"name": "Desk", "device_type": "pc", "brand": "example"},
            "devices.set_name",
            [MAC, "Desk", "pc", "example"],
        ),
        (
            "set_client_internet_blocked",
            {"blocked": True, "name": "Desk"},
            "devices.internet_block",
            [1, MAC, "Desk"],
        ),
        ("set_client_internet_blocked", {"blocked": False}, "devices.internet_block", [0, MAC, ""]),
        (
            "set_client_rate_limit",
            {"download_mbps": Decimal("12.1250"), "upload_mbps": 0},
            "devices.rate_limit",
            [MAC, {"ddrate": "12.125", "uurate": "0"}],
        ),
        ("clear_client_rate_limit", {}, "devices.rate_limit", [MAC]),
    ],
)
def test_mutation_wire_contract(method, kwargs, rpc, params):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": None, "error": None}
            assert getattr(router, method)("020000000001", **kwargs) is None
            assert post.call_args.kwargs["json"] == {"method": rpc, "params": params}
            assert rpc not in router.READ_METHODS


@pytest.mark.parametrize("value", [True, None, "bad", "NaN", "Infinity", -1, "0.0001", [], {}])
def test_invalid_rates_never_send(value):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.set_client_rate_limit(MAC, download_mbps=value, upload_mbps=1)
            post.assert_not_called()


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("set_client_name", {"name": ""}),
        ("set_client_name", {"name": "bad\nname"}),
        ("set_client_internet_blocked", {"blocked": 1}),
        ("set_client_internet_blocked", {"blocked": True, "name": None}),
    ],
)
def test_invalid_control_inputs_never_send(method, kwargs):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                getattr(router, method)(MAC, **kwargs)
            post.assert_not_called()


@pytest.mark.parametrize("failure", ["auth", "timeout"])
@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("set_client_name", {"name": "Desk"}),
        ("set_client_internet_blocked", {"blocked": True}),
        ("set_client_rate_limit", {"download_mbps": 1, "upload_mbps": 1}),
        ("clear_client_rate_limit", {}),
    ],
)
def test_mutations_never_replay(method, kwargs, failure):
    with CudyRouter(
        "http://192.0.2.1", password="test-password", auth_token="test-token"
    ) as router:
        with (
            patch.object(router.session, "post") as post,
            patch.object(router, "authenticate") as auth,
        ):
            if failure == "auth":
                post.return_value.json.return_value = {"result": None, "error": {"code": -32003}}
                expected = CudyAuthError
            else:
                post.side_effect = requests.Timeout("synthetic timeout")
                expected = CudyAPIError
            with pytest.raises(expected):
                getattr(router, method)(MAC, **kwargs)
            post.assert_called_once()
            auth.assert_not_called()
