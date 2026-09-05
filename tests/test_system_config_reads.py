"""Configuration read contracts; synthetic responses, never router writes."""

from tests import response_raw

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError

READERS = [
    ("get_system_config", "conf.get_system"),
    ("get_ipv6_config", "conf.get_ipv6"),
    ("get_default_config", "conf.get_defaults"),
    ("get_ddns_config", "conf.get_ddns"),
    ("get_connectivity_check_config", "conf.get_pingcheck"),
    ("get_auto_reboot_config", "conf.get_autoreboot"),
    ("get_qos_config", "conf.get_qos"),
]


@pytest.mark.parametrize("reader,method", READERS)
@pytest.mark.parametrize("result", [{}, {"enabled": "0", "future": {"items": [None, 0, False]}}])
def test_exact_payload_and_lossless_result(reader, method, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            assert response_raw(getattr(router, reader)()) == result
            post.assert_called_once()
            assert post.call_args.kwargs["json"] == {"method": method, "params": []}


@pytest.mark.parametrize("reader,method", READERS[:-1])
@pytest.mark.parametrize("result", [None, [1], "private-value", 0, False])
def test_object_contract_rejects_wrong_shapes_without_disclosing_values(reader, method, result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            with pytest.raises(CudyAPIError, match="Expected an object") as error:
                getattr(router, reader)()
            assert "private-value" not in str(error.value)


@pytest.mark.parametrize("result", [None, [], "0", 0, False, {"guest": {"enabled": "1"}}])
def test_qos_keeps_firmware_defined_json(result):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            assert response_raw(router.get_qos_config()) == result


@pytest.mark.parametrize("reader,method", READERS)
def test_unsupported_is_not_empty_configuration(reader, method):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"error": {"code": -32601}}
            with pytest.raises(CudyUnsupportedError) as error:
                getattr(router, reader)()
            assert error.value.code == -32601
            post.assert_called_once()


@pytest.mark.parametrize("reader,method", READERS)
def test_known_read_reauthenticates_at_most_once(reader, method):
    with CudyRouter("http://192.0.2.1", "synthetic-password", auth_token="old") as router:
        with patch.object(router, "_rpc_request", side_effect=CudyAuthError("expired")) as rpc:
            with patch.object(router, "authenticate") as authenticate:

                def refresh():
                    router.auth_token = "new"
                    return True

                authenticate.side_effect = refresh
                with pytest.raises(CudyAuthError):
                    getattr(router, reader)()
                assert rpc.call_count == 2
                authenticate.assert_called_once()
                assert method in router.READ_METHODS
