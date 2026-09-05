"""Unit tests for the CudyRouter class."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from cudypy import CudyRouter, CudyAuthError, CudyAPIError, CudyDiscoveryError, Device


class TestRouterInitialization:
    """Test CudyRouter initialization."""

    def test_init_valid_params(self):
        """Test initialization with valid parameters."""
        with patch.object(CudyRouter, "_discover_salt_and_devid"):
            router = CudyRouter("http://192.168.10.1", "password123")
            assert router.base_url == "http://192.168.10.1"
            assert router._password == "password123"
            assert router.router_ip == "192.168.10.1"
            assert router.session is not None

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is removed from URL."""
        with patch.object(CudyRouter, "_discover_salt_and_devid"):
            router = CudyRouter("http://192.168.10.1/", "password")
            assert router.base_url == "http://192.168.10.1"

    def test_init_empty_url_raises_error(self):
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CudyRouter("", "password")
        assert "password or authentication token" in str(exc_info.value)

    def test_init_empty_password_raises_error(self):
        """Test that empty password raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CudyRouter("http://192.168.10.1", "")
        assert "password or authentication token" in str(exc_info.value)

    def test_init_invalid_url_raises_error(self):
        """Test that invalid URL raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            CudyRouter("not_a_valid_url", "password")
        assert "HTTP(S) origin" in str(exc_info.value)


class TestContextManager:
    """Test context manager functionality."""

    def test_context_manager_enter_exit(self, mock_router):
        """Test context manager enter and exit."""
        with mock_router as router:
            assert router is not None
            assert router.session is not None
            assert router._closed is False

        # After exiting context, session should be closed
        assert router._closed is True

    def test_manual_close(self, mock_router):
        """Test manual close method."""
        assert mock_router._closed is False
        mock_router.close()
        assert mock_router._closed is True

    def test_double_close_safe(self, mock_router):
        """Test that closing twice doesn't cause errors."""
        mock_router.close()
        mock_router.close()  # Should not raise error
        assert mock_router._closed is True


class TestIPExtraction:
    """Test IP address extraction from URLs."""

    def test_extract_ip_from_http_url(self):
        """Test extracting IP from HTTP URL."""
        with patch.object(CudyRouter, "_discover_salt_and_devid"):
            router = CudyRouter("http://192.168.10.1", "password")
            assert router.router_ip == "192.168.10.1"

    def test_extract_ip_from_https_url(self):
        """Test extracting IP from HTTPS URL."""
        with patch.object(CudyRouter, "_discover_salt_and_devid"):
            router = CudyRouter("https://192.168.1.1", "password")
            assert router.router_ip == "192.168.1.1"

    def test_extract_hostname_from_url(self):
        """Test extracting hostname from URL."""
        with patch.object(CudyRouter, "_discover_salt_and_devid"):
            router = CudyRouter("http://router.local", "password")
            assert router.router_ip == "router.local"


class TestAuthentication:
    """Test authentication functionality."""

    @patch("requests.Session.post")
    def test_authenticate_success(self, mock_post, mock_router):
        """Test successful authentication."""
        # Mock the token request
        token_response = Mock()
        token_response.json.return_value = {"id": 1, "result": "challenge_token_123"}

        # Mock the login request
        login_response = Mock()
        login_response.json.return_value = {"id": 2, "result": "auth_token_456"}

        mock_post.side_effect = [token_response, login_response]

        result = mock_router.authenticate()

        assert result is True
        assert mock_router.auth_token == "auth_token_456"

    @patch("requests.Session.post")
    def test_authenticate_invalid_challenge(self, mock_post, mock_router):
        """Test authentication with invalid challenge."""
        # Mock invalid challenge
        token_response = Mock()
        token_response.json.return_value = {"id": 1, "result": "0"}

        mock_post.return_value = token_response

        result = mock_router.authenticate()

        assert result is False
        assert mock_router.auth_token is None

    def test_authenticate_already_authenticated(self, mock_router):
        """Test that authentication is skipped if already authenticated."""
        mock_router.auth_token = "existing_token"

        result = mock_router.authenticate()

        assert result is True
        assert mock_router.auth_token == "existing_token"

    @patch("requests.Session.post")
    def test_authenticate_force_reauth(self, mock_post, mock_router):
        """Test forced re-authentication."""
        mock_router.auth_token = "old_token_12345"

        # Mock responses
        token_response = Mock()
        token_response.json.return_value = {"id": 1, "result": "new_challenge_token"}

        login_response = Mock()
        login_response.json.return_value = {"id": 2, "result": "new_token_12345"}

        mock_post.side_effect = [token_response, login_response]

        result = mock_router.authenticate(force=True)

        assert result is True
        assert mock_router.auth_token == "new_token_12345"


class TestAPICall:
    """Test API call functionality."""

    @patch("requests.Session.post")
    def test_call_api_success(self, mock_post, mock_router):
        """Test successful API call."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "result": {"data": "test_data"}}
        mock_post.return_value = mock_response

        result = mock_router.call_api("test.method", ["param1"])

        assert result["result"]["data"] == "test_data"

    @patch("requests.Session.post")
    def test_call_api_error_response(self, mock_post, mock_router):
        """Test API call with error response."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.raise_for_status = Mock()  # Add this
        mock_response.json.return_value = {
            "id": 1,
            "error": {"code": -1000, "message": "Test error"},
        }
        mock_post.return_value = mock_response

        with pytest.raises(CudyAPIError) as exc_info:
            mock_router.call_api("test.method")

        assert "-1000" in str(exc_info.value)

    @patch("requests.Session.post")
    def test_call_api_auto_reauth_on_token_expired(self, mock_post, mock_router):
        """Test automatic re-authentication when token expires."""
        mock_router.auth_token = "expired_token_12345"

        # First call returns auth error
        error_response = Mock()
        error_response.raise_for_status = Mock()
        error_response.json.return_value = {
            "id": 1,
            "error": {"code": -32003, "message": "Auth failed"},
        }

        # Re-auth responses
        token_response = Mock()
        token_response.json.return_value = {"id": 2, "result": "new_challenge_token"}

        login_response = Mock()
        login_response.json.return_value = {"id": 3, "result": "new_token_67890"}

        # Retry with new token succeeds
        success_response = Mock()
        success_response.raise_for_status = Mock()
        success_response.json.return_value = {"id": 4, "result": {"data": "success"}}

        mock_post.side_effect = [error_response, token_response, login_response, success_response]

        result = mock_router.call_api("system.info")

        assert result["result"]["data"] == "success"
        assert mock_router.auth_token == "new_token_67890"

    def test_call_api_without_auth_raises_error(self, mock_router):
        """Test that API call without authentication raises error."""
        mock_router.auth_token = None

        with patch.object(mock_router, "authenticate", return_value=False):
            with pytest.raises(CudyAuthError):
                mock_router.call_api("test.method")


class TestGetDevices:
    """Test device retrieval functionality."""

    @patch("requests.Session.post")
    def test_get_devices_success(self, mock_post, mock_router, sample_api_response):
        """Test successful device retrieval."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.json.return_value = sample_api_response
        mock_post.return_value = mock_response

        devices = mock_router.get_devices()

        assert len(devices) == 2
        assert isinstance(devices[0], Device)
        assert devices[0].mac_address == "aa:bb:cc:dd:ee:ff"
        assert devices[1].mac_address == "11:22:33:44:55:66"

    @patch("requests.Session.post")
    def test_get_devices_empty_list(self, mock_post, mock_router):
        """Test device retrieval with empty device list."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "result": {"devlist": []}}
        mock_post.return_value = mock_response

        devices = mock_router.get_devices()

        assert devices == []

    @patch("requests.Session.post")
    def test_get_devices_invalid_response(self, mock_post, mock_router):
        """Test device retrieval with invalid response."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.json.return_value = {"id": 1}  # No 'result'
        mock_post.return_value = mock_response

        with pytest.raises(CudyAPIError):
            mock_router.get_devices()


class TestDeviceFiltering:
    """Test device filtering methods."""

    @patch.object(CudyRouter, "get_devices")
    def test_get_online_devices(self, mock_get_devices, mock_router):
        """Test filtering for online devices."""
        # Create mock devices
        online_device = Mock(spec=Device)
        online_device.is_online = True

        offline_device = Mock(spec=Device)
        offline_device.is_online = False

        mock_get_devices.return_value = [online_device, offline_device]

        online_devices = mock_router.get_online_devices()

        assert len(online_devices) == 1
        assert online_devices[0].is_online is True

    @patch.object(CudyRouter, "get_devices")
    def test_get_wifi_devices(self, mock_get_devices, mock_router):
        """Test filtering for WiFi devices."""
        wifi_device = Mock(spec=Device)
        wifi_device.connection_type = "wifi"

        ethernet_device = Mock(spec=Device)
        ethernet_device.connection_type = "ethernet"

        mock_get_devices.return_value = [wifi_device, ethernet_device]

        wifi_devices = mock_router.get_wifi_devices()

        assert len(wifi_devices) == 1
        assert wifi_devices[0].connection_type == "wifi"

    @patch.object(CudyRouter, "get_devices")
    def test_get_ethernet_devices(self, mock_get_devices, mock_router):
        """Test filtering for Ethernet devices."""
        wifi_device = Mock(spec=Device)
        wifi_device.connection_type = "wifi"

        ethernet_device = Mock(spec=Device)
        ethernet_device.connection_type = "ethernet"

        mock_get_devices.return_value = [wifi_device, ethernet_device]

        ethernet_devices = mock_router.get_ethernet_devices()

        assert len(ethernet_devices) == 1
        assert ethernet_devices[0].connection_type == "ethernet"


class TestDeviceSearch:
    """Test device search methods."""

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_mac(self, mock_get_devices, mock_router):
        """Test finding device by MAC address."""
        device1 = Mock(spec=Device)
        device1.mac_address = "aa:bb:cc:dd:ee:ff"

        device2 = Mock(spec=Device)
        device2.mac_address = "11:22:33:44:55:66"

        mock_get_devices.return_value = [device1, device2]

        found = mock_router.get_device_by_mac("aa:bb:cc:dd:ee:ff")

        assert found is not None
        assert found.mac_address == "aa:bb:cc:dd:ee:ff"

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_mac_different_formats(self, mock_get_devices, mock_router):
        """Test MAC search with different formats."""
        device = Mock(spec=Device)
        device.mac_address = "aa:bb:cc:dd:ee:ff"

        mock_get_devices.return_value = [device]

        # Test different MAC formats
        assert mock_router.get_device_by_mac("AA:BB:CC:DD:EE:FF") is not None
        assert mock_router.get_device_by_mac("aa-bb-cc-dd-ee-ff") is not None
        assert mock_router.get_device_by_mac("aabbccddeeff") is not None

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_mac_not_found(self, mock_get_devices, mock_router):
        """Test MAC search when device not found."""
        mock_get_devices.return_value = []

        found = mock_router.get_device_by_mac("ff:ff:ff:ff:ff:ff")

        assert found is None

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_ip(self, mock_get_devices, mock_router):
        """Test finding device by IP address."""
        device1 = Mock(spec=Device)
        device1.ip_address = "192.168.10.100"

        device2 = Mock(spec=Device)
        device2.ip_address = "192.168.10.50"

        mock_get_devices.return_value = [device1, device2]

        found = mock_router.get_device_by_ip("192.168.10.100")

        assert found is not None
        assert found.ip_address == "192.168.10.100"

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_hostname(self, mock_get_devices, mock_router):
        """Test finding device by hostname."""
        device1 = Mock(spec=Device)
        device1.hostname = "laptop"
        device1.device_name = None

        device2 = Mock(spec=Device)
        device2.hostname = "desktop"
        device2.device_name = None

        mock_get_devices.return_value = [device1, device2]

        found = mock_router.get_device_by_hostname("laptop")

        assert found is not None
        assert found.hostname == "laptop"

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_hostname_case_insensitive(self, mock_get_devices, mock_router):
        """Test hostname search is case-insensitive by default."""
        device = Mock(spec=Device)
        device.hostname = "MyLaptop"
        device.device_name = None

        mock_get_devices.return_value = [device]

        found = mock_router.get_device_by_hostname("mylaptop")

        assert found is not None

    @patch.object(CudyRouter, "get_devices")
    def test_get_device_by_hostname_case_sensitive(self, mock_get_devices, mock_router):
        """Test hostname search with case sensitivity."""
        device = Mock(spec=Device)
        device.hostname = "MyLaptop"
        device.device_name = None

        mock_get_devices.return_value = [device]

        found = mock_router.get_device_by_hostname("mylaptop", case_sensitive=True)

        assert found is None  # Should not match due to case


class TestSystemMethods:
    """Test system information methods."""

    @patch("requests.Session.post")
    def test_get_system_info(self, mock_post, mock_router):
        """Test getting system information."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 1,
            "result": {"model": "WR3000", "firmware_version": "1.2.3"},
        }
        mock_post.return_value = mock_response

        info = mock_router.get_system_info()

        assert info.model == "WR3000"
        assert info.raw["firmware_version"] == "1.2.3"

    @patch("requests.Session.post")
    def test_get_network_status(self, mock_post, mock_router):
        """Test getting network status."""
        mock_router.auth_token = "test_token"

        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "result": {"wan": "connected", "lan": "up"}}
        mock_post.return_value = mock_response

        status = mock_router.get_network_status()

        assert status.raw["wan"] == "connected"
        assert status.raw["lan"] == "up"
