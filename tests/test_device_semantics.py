"""Device observations distinguish unknown data from inactivity heuristics."""

from datetime import datetime, timedelta

import pytest

from cudypy import Device


@pytest.mark.parametrize("value", [None, "bad", -1, "-1", True, False, 1.5, "1.5"])
def test_invalid_inactivity_is_unknown(value):
    device = Device.from_api_response({"macaddr": "020000000001", "inactive": value})
    assert device.inactive_time is None
    assert device.is_online is None
    assert device.recently_active is None


def test_missing_inactivity_is_not_assumed_online():
    assert Device.from_api_response({"macaddr": "020000000001"}).recently_active is None
    assert Device("020000000001", "192.0.2.1").recently_active is None


@pytest.mark.parametrize("value,expected", [(0, True), ("29", True), (30, False), ("60", False)])
def test_legacy_cutoff_is_explicit_activity_only(value, expected):
    device = Device.from_api_response({"macaddr": "020000000001", "inactive": value})
    assert device.recently_active is expected
    assert device.is_online is expected


def test_native_counters_are_not_reinterpreted():
    data = {
        "macaddr": "020000000001",
        "inbytes": "123",
        "outbytes": "456",
        "upbytes": "789",
        "downbytes": "987",
        "extra": "synthetic-private",
    }
    device = Device.from_api_response(data)
    assert device.reported_inbytes == device.bytes_received == 123
    assert device.reported_outbytes == device.bytes_sent == 456
    assert device.reported_upbytes == 789
    assert device.reported_downbytes == 987
    assert device.raw == data and device.raw is not data
    assert "synthetic-private" not in repr(device)


@pytest.mark.parametrize("value", [True, -1, "-1", 1.5, None, "bad"])
def test_invalid_duration_and_counters_do_not_become_valid_observations(value):
    device = Device.from_api_response(
        {"macaddr": "020000000001", "online": value, "inbytes": value, "upspeed": value}
    )
    assert device.reported_online_seconds is None
    assert device.connected_since is None
    assert device.bytes_received is None
    assert device.bandwidth_up is None


def test_duration_is_seconds_with_estimated_start_time():
    before = datetime.now() - timedelta(seconds=3600)
    device = Device.from_api_response({"macaddr": "020000000001", "online": "3600"})
    after = datetime.now() - timedelta(seconds=3600)
    assert device.reported_online_seconds == 3600
    assert before <= device.connected_since <= after


def test_huge_duration_retained_without_invalid_timestamp():
    device = Device.from_api_response({"macaddr": "020000000001", "online": str(10**30)})
    assert device.reported_online_seconds == 10**30
    assert device.connected_since is None
