"""Unit tests for the Device model."""

import pytest
from datetime import datetime, timedelta
from cudypy import Device


class TestDeviceCreation:
    """Test Device creation from API responses."""

    def test_create_wifi_device(self, wifi_device_data):
        """Test creating a WiFi device from API data."""
        device = Device.from_api_response(wifi_device_data)

        assert device.mac_address == "aa:bb:cc:dd:ee:ff"
        assert device.ip_address == "192.168.10.100"
        assert device.hostname == "test-wifi-device"
        assert device.device_name == "My Laptop"
        assert device.connection_type == "wifi"
        assert device.is_online is True
        assert device.signal_strength == -45
        assert device.bandwidth_up == 512
        assert device.bandwidth_down == 1024
        assert device.has_internet is True
        assert device.is_vpn is False

    def test_create_ethernet_device(self, ethernet_device_data):
        """Test creating an Ethernet device from API data."""
        device = Device.from_api_response(ethernet_device_data)

        assert device.mac_address == "11:22:33:44:55:66"
        assert device.ip_address == "192.168.10.50"
        assert device.connection_type == "ethernet"
        assert device.is_online is True
        assert device.signal_strength is None  # Ethernet has no signal

    def test_create_offline_device(self, offline_device_data):
        """Test creating an offline device."""
        device = Device.from_api_response(offline_device_data)

        assert device.is_online is False  # inactive > 30s
        assert device.has_internet is False

    def test_create_minimal_device(self, minimal_device_data):
        """Test creating device with only required fields."""
        device = Device.from_api_response(minimal_device_data)

        assert device.mac_address == "00:11:22:33:44:55"
        assert device.ip_address == "192.168.10.10"
        assert device.hostname is None
        assert device.device_name is None
        assert device.connection_type is None


class TestDeviceValidation:
    """Test Device input validation."""

    def test_invalid_data_type_string(self):
        """Test that string input raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            Device.from_api_response("not a dict")

        assert "must be a dictionary" in str(exc_info.value)
        assert "got str" in str(exc_info.value)

    def test_invalid_data_type_list(self):
        """Test that list input raises TypeError."""
        with pytest.raises(TypeError) as exc_info:
            Device.from_api_response([1, 2, 3])

        assert "must be a dictionary" in str(exc_info.value)
        assert "got list" in str(exc_info.value)

    def test_invalid_data_type_none(self):
        """Test that None input raises TypeError."""
        with pytest.raises(TypeError):
            Device.from_api_response(None)


class TestConnectionTypeDetection:
    """Test connection type detection logic."""

    def test_wifi_detection_rax0(self):
        """Test WiFi detection with rax0 interface."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "interface": "rax0"}
        device = Device.from_api_response(data)
        assert device.connection_type == "wifi"

    def test_wifi_detection_ra0(self):
        """Test WiFi detection with ra0 interface."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "interface": "ra0"}
        device = Device.from_api_response(data)
        assert device.connection_type == "wifi"

    def test_wifi_detection_wlan_iface(self):
        """Test WiFi detection with wlan iface."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "interface": "other", "iface": "wlan10"}
        device = Device.from_api_response(data)
        assert device.connection_type == "wifi"

    def test_ethernet_detection_eth0(self):
        """Test Ethernet detection with eth0 interface."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "interface": "eth0"}
        device = Device.from_api_response(data)
        assert device.connection_type == "ethernet"

    def test_ethernet_detection_eth_iface(self):
        """Test Ethernet detection with eth iface."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "interface": "other", "iface": "eth"}
        device = Device.from_api_response(data)
        assert device.connection_type == "ethernet"

    def test_unknown_connection_type(self):
        """Test unknown connection type."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "interface": "unknown"}
        device = Device.from_api_response(data)
        assert device.connection_type is None


class TestOnlineStatusDetection:
    """Test online status detection."""

    def test_online_device_low_inactive(self):
        """Test device is online with low inactive time."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "inactive": 5}
        device = Device.from_api_response(data)
        assert device.is_online is True

    def test_online_device_edge_case(self):
        """Test device is online at 29 seconds inactive."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "inactive": 29}
        device = Device.from_api_response(data)
        assert device.is_online is True

    def test_offline_device_high_inactive(self):
        """Test device is offline with high inactive time."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "inactive": 60}
        device = Device.from_api_response(data)
        assert device.is_online is False

    def test_offline_device_edge_case(self):
        """Test device is offline at 30 seconds inactive."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "inactive": 30}
        device = Device.from_api_response(data)
        assert device.is_online is False


class TestDeviceProperties:
    """Test Device computed properties."""

    def test_str_representation_with_name(self):
        """Test string representation with device name."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "name": "My Device"}
        device = Device.from_api_response(data)
        assert str(device) == "My Device (192.168.1.1)"

    def test_str_representation_with_hostname(self):
        """Test string representation with hostname."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "hostname": "laptop"}
        device = Device.from_api_response(data)
        assert str(device) == "laptop (192.168.1.1)"

    def test_str_representation_with_mac_only(self):
        """Test string representation with only MAC."""
        data = {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.1"}
        device = Device.from_api_response(data)
        assert str(device) == "aa:bb:cc:dd:ee:ff (192.168.1.1)"

    def test_connection_time_property(self, wifi_device_data):
        """Test connection time property."""
        device = Device.from_api_response(wifi_device_data)
        conn_time = device.connection_time

        assert conn_time is not None
        assert "h" in conn_time or "m" in conn_time or "d" in conn_time

    def test_connection_time_none(self):
        """Test connection time when not available."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1"}
        device = Device.from_api_response(data)
        assert device.connection_time is None


class TestBandwidthFormatting:
    """Test bandwidth formatting properties."""

    def test_format_bandwidth_up_kb(self):
        """Test upload bandwidth formatting in KB/s."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "upspeed": 512}
        device = Device.from_api_response(data)
        assert device.formatted_bandwidth_up == "512.0 B/s"

    def test_format_bandwidth_up_mb(self):
        """Test upload bandwidth formatting in MB/s."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "upspeed": 2048}
        device = Device.from_api_response(data)
        assert device.formatted_bandwidth_up == "2.0 KiB/s"

    def test_format_bandwidth_down_kb(self):
        """Test download bandwidth formatting in KB/s."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "downspeed": 1024}
        device = Device.from_api_response(data)
        assert device.formatted_bandwidth_down == "1.0 KiB/s"

    def test_format_bandwidth_none(self):
        """Test bandwidth formatting when not available."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1"}
        device = Device.from_api_response(data)
        assert device.formatted_bandwidth_up is None
        assert device.formatted_bandwidth_down is None


class TestBytesFormatting:
    """Test bytes formatting properties."""

    def test_format_bytes_received_kb(self):
        """Test bytes received formatting in KB."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "inbytes": 2048}
        device = Device.from_api_response(data)
        assert device.formatted_bytes_received == "2.0 KB"

    def test_format_bytes_received_mb(self):
        """Test bytes received formatting in MB."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "inbytes": 1048576}
        device = Device.from_api_response(data)
        assert device.formatted_bytes_received == "1.0 MB"

    def test_format_bytes_sent_gb(self):
        """Test bytes sent formatting in GB."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1", "outbytes": 1073741824}
        device = Device.from_api_response(data)
        assert device.formatted_bytes_sent == "1.0 GB"

    def test_format_bytes_none(self):
        """Test bytes formatting when not available."""
        data = {"mac": "aa:bb:cc", "ip": "192.168.1.1"}
        device = Device.from_api_response(data)
        assert device.formatted_bytes_received is None
        assert device.formatted_bytes_sent is None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dict(self):
        """Test handling of empty dictionary."""
        device = Device.from_api_response({})
        assert device.mac_address == "unknown"
        assert device.ip_address == "unknown"

    def test_none_values(self):
        """Test handling of None values in fields."""
        data = {"mac": None, "ip": None, "hostname": None, "signal": None, "upspeed": None}
        device = Device.from_api_response(data)
        assert device.mac_address == "unknown"
        assert device.ip_address == "unknown"
        assert device.signal_strength is None
        assert device.bandwidth_up is None

    def test_invalid_numeric_values(self):
        """Test handling of invalid numeric values."""
        data = {
            "mac": "aa:bb:cc",
            "ip": "192.168.1.1",
            "signal": "invalid",
            "upspeed": "not_a_number",
            "inactive": "bad",
        }
        device = Device.from_api_response(data)
        assert device.signal_strength is None
        assert device.bandwidth_up is None
