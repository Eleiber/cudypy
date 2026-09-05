"""Synthetic system-status shapes; no captured router identifiers or responses."""

from unittest.mock import patch

import pytest

from cudypy import CudyAPIError, CudyRouter, ResourceUsage, SystemStatus
from cudypy.models import ResourceUsage as ExportedResourceUsage


def test_extended_system_snapshot():
    data = {
        "model": "Synthetic router",
        "firmware": "synthetic-v2",
        "board_name": "test-board",
        "processor": "2",
        "revision": "test-revision",
        "rom": "test-rom",
        "country": "US",
        "type": "ap",
        "uptime": "120",
        "sn": "synthetic-private-serial",
        "macaddr": "020000000001",
        "lan_ip": "192.0.2.1",
        "timestamp": 1700000000,
        "localtime": 1700000001,
        "memory": {
            "total": 1000,
            "free": 100,
            "available": "400",
            "shared": 10,
            "cached": 200,
            "buffered": 0,
            "future": [1],
        },
        "swap": {"total": 500, "free": 500},
        "root": {"total": 80, "used": 20, "avail": 55, "free": 60},
        "tmp": {"total": 50, "used": 0, "avail": 50},
        "cpu_usage": 20,
        "load": [65536, 32768, 0],
        "future": {"nested": [1]},
    }
    status = SystemStatus.from_api_response(data)
    assert status.model == "Synthetic router"
    assert status.uptime_seconds == 120
    assert status.memory.available == 400
    assert status.memory.used is None  # Not calculated from total minus free.
    assert status.memory.buffered == 0
    assert status.swap.free == 500
    assert status.root.available == 55 and status.root.free == 60
    assert status.tmp.used == 0
    assert status.cpu_usage == 20 and status.load == (65536, 32768, 0)
    for attribute, key in (
        ("processor", "processor"),
        ("revision", "revision"),
        ("rom", "rom"),
        ("country", "country"),
        ("device_type", "type"),
        ("serial_number", "sn"),
        ("mac_address", "macaddr"),
        ("lan_ip", "lan_ip"),
        ("timestamp", "timestamp"),
        ("localtime", "localtime"),
    ):
        assert getattr(status, attribute) == data[key]
    assert status.raw == data
    assert status.memory.raw == data["memory"]
    for private in (data["sn"], data["macaddr"], data["lan_ip"]):
        assert private not in repr(status)
    data["memory"]["future"].append(2)
    data["future"]["nested"].append(2)
    assert status.raw["future"]["nested"] == [1]
    assert status.memory.raw["future"] == [1]
    status.raw["memory"]["future"].append(3)
    assert status.memory.raw["future"] == [1]


def test_sparse_older_firmware_shape():
    status = SystemStatus.from_api_response({"firmware": "synthetic-v1", "uptime": "5"})
    assert status.model is None
    assert status.memory is None and status.root is None
    assert status.cpu_usage is None and status.load is None
    assert status.serial_number is None
    assert status.uptime_seconds == 5


def test_empty_null_and_zero_are_distinct():
    status = SystemStatus.from_api_response(
        {"memory": {}, "swap": None, "load": [], "cpu_usage": "0", "root": {"free": "0"}}
    )
    assert isinstance(status.memory, ResourceUsage)
    assert status.memory.total is None
    assert status.swap is None
    assert status.load == () and status.cpu_usage == 0 and status.root.free == 0


def test_resource_alias_and_exports():
    assert ResourceUsage is ExportedResourceUsage
    result = ResourceUsage.from_api_response({"avail": "10", "available": 20})
    assert result.available == 20
    assert result.raw["avail"] == "10"
    assert ResourceUsage.from_api_response({"available": None, "avail": 10}).available is None


@pytest.mark.parametrize("key", ["memory", "swap", "root", "tmp"])
@pytest.mark.parametrize("value", [[], "bad", 0, True])
def test_invalid_nested_shapes(key, value):
    with pytest.raises(ValueError):
        SystemStatus.from_api_response({key: value})


@pytest.mark.parametrize(
    "data",
    [
        {"memory": {"total": -1}},
        {"memory": {"free": True}},
        {"root": {"avail": 1.5}},
        {"tmp": {"used": "bad"}},
        {"cpu_usage": True},
        {"cpu_usage": -1},
        {"cpu_usage": float("nan")},
        {"load": "bad"},
        {"load": [None]},
        {"load": [True]},
        {"load": [-1]},
        {"load": [1.5]},
        {"processor": 2},
        {"sn": 1},
        {"timestamp": -1},
    ],
)
def test_malformed_fields_raise_library_error(data):
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as router:
        with patch.object(router, "call_api", return_value={"result": data}):
            with pytest.raises(CudyAPIError, match="Malformed system status"):
                router.get_system_status()
            assert router.call_api("system.info")["result"] == data  # Explicit raw escape hatch.


def test_snapshot_access_does_not_request_again():
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as router:
        with patch.object(
            router, "call_api", return_value={"result": {"memory": {"available": 0}}}
        ) as rpc:
            status = router.get_system_status()
            assert status.memory.available == 0
            assert status.memory.available == 0
            assert status.raw["memory"]["available"] == 0
            rpc.assert_called_once_with("system.info")


def test_existing_positional_constructor_is_compatible():
    status = SystemStatus("Synthetic", "v1", None, 10, {})
    assert status.model == "Synthetic" and status.memory is None
