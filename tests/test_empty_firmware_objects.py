"""Observed empty-array variants, using synthetic responses only."""

from unittest.mock import patch
import pytest
from cudypy import CudyRouter, CudyAPIError, CudyUnsupportedError


@pytest.mark.parametrize("reader", ["get_auto_reboot_config", "get_firmware_update_info"])
@pytest.mark.parametrize(
    "value,expected", [([], None), ({}, {}), ({"future": "0"}, {"future": "0"})]
)
def test_available_and_unavailable_objects(reader, value, expected):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": value}
            assert getattr(router, reader)() == expected
            post.assert_called_once()


@pytest.mark.parametrize("reader", ["get_auto_reboot_config", "get_firmware_update_info"])
@pytest.mark.parametrize("bad", [None, False, "", [{}]])
def test_no_unobserved_coercion(reader, bad):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": bad}
            with pytest.raises(CudyAPIError):
                getattr(router, reader)()
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError):
                getattr(router, reader)()
