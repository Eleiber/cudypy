from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyRouter, InterfaceStatus, SystemStatus


def test_system_firmware_variants():
    old = SystemStatus.from_api_response({"firmware": "synthetic-v1", "uptime": "120"})
    assert old.model is None and old.uptime_seconds == 120
    new = SystemStatus.from_api_response({"model": "Synthetic", "firmware": "synthetic-v2"})
    assert new.model == "Synthetic" and new.uptime_seconds is None


def test_interface_observations_preserve_missing_and_unknown_fields():
    data = {"is_up": False, "rx_bytes": "0", "tx_bytes": 120, "extra": "synthetic-private"}
    status = InterfaceStatus.from_api_response(data)
    assert status.is_up is False and status.rx_bytes == 0 and status.tx_bytes == 120
    assert status.ip_address is None
    assert status.raw == data and status.raw is not data
    assert "synthetic-private" not in repr(status)


@pytest.mark.parametrize(
    "reader,rpc,params,result",
    [
        ("get_system_status", "system.info", [], {"uptime": 10}),
        ("get_interface_status", "net.iface_status", ["wan"], {"is_up": True}),
        ("get_vpn_config", "conf.get_all", ["vpn", "config"], {"enabled": "0", "proto": []}),
    ],
)
def test_status_wire_contracts(reader, rpc, params, result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            post.return_value.json.return_value = {"result": result}
            value = getattr(router, reader)()
            assert (value if isinstance(value, dict) else value.raw) == result
            assert post.call_args.kwargs["json"] == {"method": rpc, "params": params}


@pytest.mark.parametrize(
    "reader,result",
    [
        ("get_system_status", {"uptime": -1}),
        ("get_system_status", {"firmware": 1}),
        ("get_interface_status", {"is_up": "bad"}),
        ("get_interface_status", {"rx_bytes": True}),
        ("get_vpn_config", None),
    ],
)
def test_malformed_status(reader, result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError):
                getattr(router, reader)()


def test_mesh_inclusive_page_bounds_and_total_preserved():
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            result = {"devlist": [{"macaddr": "020000000001"}], "devcnt": 101}
            post.return_value.json.return_value = {"result": result}
            assert router.get_mesh_device_page("synthetic-node", 2) == result
            assert post.call_args.kwargs["json"] == {
                "method": "mesh.get_devices",
                "params": ["synthetic-node", 101, 200],
            }


@pytest.mark.parametrize(
    "node,page", [("", 1), (None, 1), ("node", 0), ("node", True), ("node", 1.5)]
)
def test_mesh_invalid_input_never_sends(node, page):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router.session, "post") as post:
            with pytest.raises(ValueError):
                router.get_mesh_device_page(node, page)
            post.assert_not_called()


@pytest.mark.parametrize("result", [None, {}, {"devlist": [1]}, {"devlist": [], "devcnt": -1}])
def test_bad_mesh_page(result):
    with CudyRouter("http://192.0.2.1", auth_token="test-token") as router:
        with patch.object(router, "call_api", return_value={"result": result}):
            with pytest.raises(CudyAPIError):
                router.get_mesh_device_page("synthetic-node")
