"""Pytest configuration and shared fixtures for CudyPy tests."""

import pytest
from cudypy import Device, CudyRouter


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Unit tests must never contact a router, even when a mock is missing."""

    def blocked(*args, **kwargs):
        raise AssertionError("Network access is disabled in unit tests")

    monkeypatch.setattr("requests.sessions.Session.request", blocked)


@pytest.fixture
def wifi_device_data():
    """Sample WiFi device data from API response."""
    return {
        "mac": "aa:bb:cc:dd:ee:ff",
        "ip": "192.168.10.100",
        "hostname": "test-wifi-device",
        "name": "My Laptop",
        "interface": "rax0",
        "iface": "wlan10",
        "online": 3600,  # 1 hour connected
        "signal": -45,
        "upspeed": 512,  # bytes/s
        "downspeed": 1024,  # bytes/s
        "inactive": 5,  # Reported inactivity, below the legacy heuristic cutoff
        "internet": True,
        "vpn": False,
        "inbytes": 1048576,  # 1 MB
        "outbytes": 524288,  # 512 KB
    }


@pytest.fixture
def ethernet_device_data():
    """Sample Ethernet device data from API response."""
    return {
        "mac": "11:22:33:44:55:66",
        "ip": "192.168.10.50",
        "hostname": "desktop-pc",
        "interface": "eth0",
        "iface": "eth",
        "online": 7200,  # 2 hours connected
        "upspeed": 2048,
        "downspeed": 4096,
        "inactive": 2,
        "internet": True,
        "vpn": False,
        "inbytes": 10485760,  # 10 MB
        "outbytes": 5242880,  # 5 MB
    }


@pytest.fixture
def offline_device_data():
    """Sample offline device data."""
    return {
        "mac": "ff:ee:dd:cc:bb:aa",
        "ip": "192.168.10.200",
        "hostname": "offline-device",
        "interface": "rax0",
        "iface": "wlan10",
        "online": 0,
        "inactive": 60,  # Above the activity cutoff; not proof of disconnection
        "internet": False,
    }


@pytest.fixture
def minimal_device_data():
    """Minimal device data with only required fields."""
    return {"mac": "00:11:22:33:44:55", "ip": "192.168.10.10"}


@pytest.fixture
def mock_router(monkeypatch):
    """Create a mock router instance with mDNS discovery bypassed."""

    def mock_discover(self, service_type="_http._tcp.local."):
        """Mock mDNS discovery."""
        self.salt = "test_salt_value"
        self.devid = "test_device_id"
        return True

    # Patch the discovery method
    monkeypatch.setattr(CudyRouter, "_discover_salt_and_devid", mock_discover)

    # Create router instance
    router = CudyRouter("http://192.168.10.1", "test_password")
    # Ensure devid is set for tests that need it
    router.devid = "test_device_id"
    yield router
    router.close()


@pytest.fixture
def sample_api_response():
    """Sample API response with multiple devices."""
    return {
        "id": 1,
        "result": {
            "devlist": [
                {
                    "macaddr": "aa:bb:cc:dd:ee:ff",
                    "ipaddr": "192.168.10.100",
                    "hostname": "laptop",
                    "interface": "rax0",
                    "iface": "wlan10",
                    "online": 3600,
                    "signal": -45,
                    "upspeed": 512,
                    "downspeed": 1024,
                    "inactive": 5,
                    "internet": True,
                    "vpn": False,
                },
                {
                    "macaddr": "11:22:33:44:55:66",
                    "ipaddr": "192.168.10.50",
                    "hostname": "desktop",
                    "interface": "eth0",
                    "iface": "eth",
                    "online": 7200,
                    "inactive": 2,
                    "internet": True,
                    "vpn": False,
                },
            ]
        },
    }
