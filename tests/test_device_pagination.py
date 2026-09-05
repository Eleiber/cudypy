"""Firmware regression: [1, 1] is one client, not two boolean flags."""

from unittest.mock import call, patch

import pytest

from cudypy import CudyAPIError, CudyRouter


def entry(index):
    return {"macaddr": f"02:00:00:00:00:{index:02x}", "ipaddr": f"192.0.2.{index}"}


def response(count, entries):
    return {"result": {"devcnt": count, "devlist": entries}}


def test_full_list_does_not_request_one_client():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(
            router, "call_api", return_value=response(4, [entry(i) for i in range(4)])
        ) as rpc:
            assert len(router.get_devices()) == 4
            rpc.assert_called_once_with("devices.get_devlist_ex")


def test_partial_list_fetches_remaining_inclusive_range():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(
            router,
            "call_api",
            side_effect=[response(4, [entry(1), entry(2)]), response(4, [entry(3), entry(4)])],
        ) as rpc:
            assert len(router.get_devices()) == 4
            assert rpc.call_args_list == [
                call("devices.get_devlist_ex"),
                call("devices.get_devlist_ex", [3, 4]),
            ]


@pytest.mark.parametrize(
    "last", [response(4, []), response(3, [entry(3)]), response(4, [entry(1), entry(2)])]
)
def test_inconsistent_pages_are_errors(last):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(
            router, "call_api", side_effect=[response(4, [entry(1), entry(2)]), last]
        ):
            with pytest.raises(CudyAPIError):
                router.get_devices()
