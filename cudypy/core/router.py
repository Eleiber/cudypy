"""Core router implementation for interacting with Cudy routers."""

import hashlib
import json
import logging
import re
import threading
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Any, Callable, Type, TypeVar
from urllib.parse import urlparse

import requests
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from ..exceptions.api_exceptions import (
    CudyAPIError,
    CudyAuthError,
    CudyDiscoveryError,
    CudyUnsupportedError,
)
from ..models.device import Device
from ..models.status import (
    EthernetPort,
    InterfaceStatus,
    LanConfig,
    RateLimit,
    SystemStatus,
    WirelessInterface,
)

from ..models.records import (
    AccessPoint,
    ClientName,
    ClientTraffic,
    Configuration,
    ConfigurationSections,
    FirmwareRecord,
    ParentalGroup,
    ProviderCatalog,
    ResponsePage,
    WdsStatus,
    WorkMode,
    ResponseValue,
    deserialize,
    validate_record,
)

T = TypeVar("T", bound=FirmwareRecord)
R = TypeVar("R")

# Libraries must not change the application's logging configuration.
logger = logging.getLogger(__name__)


class CudyRouter:
    """Main class for interacting with a Cudy router's local API."""

    AUTH_PATH = "/cgi-bin/luci/rpc/auth"
    API_PATH = "/cgi-bin/luci/rpc/app"
    DEFAULT_MDNS_TIMEOUT = 7
    DEFAULT_REQUEST_TIMEOUT: float = 10

    class _CudyServiceListener(ServiceListener):
        """Internal mDNS service discovery listener."""

        def __init__(self, router_instance: "CudyRouter"):
            self._router = router_instance
            self._found_event = threading.Event()

        def wait_for_discovery(self, timeout: float) -> bool:
            """Wait for service discovery."""
            return self._found_event.wait(timeout)

        def _process_service_info(self, zc: Zeroconf, type_: str, name: str) -> None:
            """Process discovered service information."""
            try:
                info = zc.get_service_info(type_, name, timeout=1000)
                if not info or self._router.router_ip not in info.parsed_addresses():
                    return

                properties = {
                    k.decode("utf-8"): v.decode("utf-8") if v else ""
                    for k, v in info.properties.items()
                }

                if "salt" in properties:
                    self._router.salt = properties["salt"]
                    self._router.devid = properties.get("devname") or properties.get("model")
                    self._found_event.set()

            except Exception as e:
                logger.warning(f"mDNS: Error processing service info: {e}")

        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            self._process_service_info(zc, type_, name)

        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            self._process_service_info(zc, type_, name)

        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            pass

    def __init__(
        self,
        base_url: str,
        password: Optional[str] = None,
        *,
        auth_token: Optional[str] = None,
        salt: Optional[str] = None,
        devid: Optional[str] = None,
        timeout: float = 10,
    ):
        """Initialize the router connection.

        Args:
            base_url: Base URL of the router (e.g., 'http://192.168.10.1')
            password: Optional router admin password
            auth_token: Existing session token; bypasses password login and mDNS
            salt: Known authentication salt; bypasses discovery for password login
            devid: Legacy parameter; not transmitted in local RPC requests
            timeout: HTTP request timeout in seconds

        Raises:
            ValueError: If base_url or password is empty
        """
        if not isinstance(base_url, str) or not base_url or not (password or auth_token):
            raise ValueError("Base URL and a password or authentication token are required")
        if password is not None and not isinstance(password, str):
            raise ValueError("password must be a string")
        if salt is not None and (not isinstance(salt, str) or not salt):
            raise ValueError("salt must be a nonempty string")
        parsed = urlparse(base_url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise ValueError("Base URL must be an HTTP(S) origin without credentials")
        # Accessing port also validates malformed or out-of-range port numbers.
        parsed.port
        if not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
            raise ValueError("timeout must be a finite positive number")
        if auth_token is not None and (not isinstance(auth_token, str) or not auth_token.strip()):
            raise ValueError("auth_token must be a nonempty string")

        self.base_url = base_url.rstrip("/")
        self._password = password
        self.router_ip = self._extract_ip(base_url)
        self.salt = salt
        self.auth_token = auth_token
        self.devid = devid
        self.DEFAULT_REQUEST_TIMEOUT = timeout
        self._closed = False

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update({"Connection": "close", "User-Agent": "CudyPy Client"})

    def __enter__(self) -> "CudyRouter":
        """Context manager entry - allows using 'with' statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures proper cleanup."""
        self.close()

    def close(self) -> None:
        """Close the session and cleanup resources.

        This should be called when you're done with the router instance,
        or use the router in a 'with' statement for automatic cleanup.
        """
        if not self._closed and self.session:
            self.session.close()
            self.session.cookies.clear()
            self.auth_token = None
            self._password = None
            self._closed = True
            logger.debug("Router session closed")

    def _extract_ip(self, url: str) -> str:
        """Extract IP address from URL.

        Args:
            url: The base URL to extract IP from

        Returns:
            The hostname/IP address from the URL

        Raises:
            ValueError: If URL is invalid or cannot be parsed
        """
        try:
            hostname = urlparse(url).hostname
            if not hostname:
                raise ValueError(f"No hostname found in URL: {url}")
            return hostname
        except Exception as e:
            raise ValueError(f"Invalid base URL: {url}") from e

    def _discover_salt_and_devid(self, service_type: str = "_http._tcp.local.") -> bool:
        """Discover router salt and device ID via mDNS.

        Args:
            service_type: mDNS service type to search for

        Returns:
            True if discovery was successful

        Raises:
            CudyDiscoveryError: If mDNS discovery fails or times out
        """
        if self.salt:
            logger.debug("Salt and devid already discovered")
            return True

        zeroconf = None
        browser = None
        try:
            logger.info(f"Starting mDNS discovery for {self.router_ip}")
            zeroconf = Zeroconf()
            listener = self._CudyServiceListener(self)
            browser = ServiceBrowser(zeroconf, service_type, listener)

            if not listener.wait_for_discovery(self.DEFAULT_MDNS_TIMEOUT):
                raise CudyDiscoveryError(
                    f"mDNS discovery timed out after {self.DEFAULT_MDNS_TIMEOUT}s for {self.router_ip}. "
                    "Ensure the router is on the same network and mDNS is not blocked."
                )

            if not self.salt:
                raise CudyDiscoveryError("mDNS discovery completed but 'salt' was not found")

            logger.info(f"Successfully discovered salt and devid: {self.devid}")
            return True

        except CudyDiscoveryError:
            raise
        except Exception as e:
            raise CudyDiscoveryError(f"Unexpected error during mDNS discovery: {e}") from e
        finally:
            if browser:
                browser.cancel()
            if zeroconf:
                zeroconf.close()

    def _rpc_request(
        self, path: str, method: str, params: Optional[List[Any]], authenticated: bool = False
    ) -> Dict[str, Any]:
        """Send one local RPC request. Never follow redirects or retry transport failures."""
        if self._closed:
            raise CudyAPIError("Router session is closed")
        payload = {"method": method, "params": params if params is not None else []}
        # The app omits the device ID from local transport requests.
        query = {"auth": self.auth_token} if authenticated else None
        try:
            response = self.session.post(
                self.base_url + path,
                json=payload,
                params=query,
                timeout=self.DEFAULT_REQUEST_TIMEOUT,
                allow_redirects=False,
            )
            if response.status_code in (401, 403):
                raise CudyAuthError("Router rejected authentication")
            if isinstance(response.status_code, int) and 300 <= response.status_code < 400:
                raise CudyAPIError("Router returned an unexpected redirect")
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            raise CudyAPIError("Router request timed out; it was not retried") from None
        except ValueError:
            raise CudyAPIError("Router returned invalid JSON") from None
        except requests.exceptions.RequestException:
            # requests exceptions can contain the full URL including the auth token.
            raise CudyAPIError("Router HTTP request failed") from None
        if not isinstance(data, dict):
            raise CudyAPIError("Router returned a non-object RPC response")
        error = data.get("error")
        if error is not None:
            if not isinstance(error, dict):
                raise CudyAPIError("Router returned a malformed RPC error")
            code = error.get("code")
            if not isinstance(code, int) or isinstance(code, bool):
                raise CudyAPIError("Router returned a malformed RPC error code")
            if code == -32003:
                raise CudyAuthError("Router rejected authentication", code=code)
            if code == -32601:
                raise CudyUnsupportedError(
                    "RPC method is not supported by this firmware", code=code
                )
            raise CudyAPIError("Router RPC failed (Code: %s)" % code, code=code)
        if "result" not in data:
            raise CudyAPIError("Router RPC response is missing result")
        return data

    def _make_auth_request(self, method: str, params: Optional[List[Any]] = None) -> dict:
        """Send an authentication RPC request."""
        return self._rpc_request(self.AUTH_PATH, method, params)

    def authenticate(self, force: bool = False) -> bool:
        """Authenticate with the router.

        Args:
            force: If True, force re-authentication even if already authenticated

        Returns:
            True if authentication succeeds, False otherwise
        """
        if self._closed:
            raise CudyAPIError("Router session is closed")
        if self.auth_token and not force:
            logger.debug("Already authenticated")
            return True

        if not self._password:
            raise CudyAuthError("A fresh token or password is required to authenticate")

        try:
            logger.info("Authenticating with router...")
            self._discover_salt_and_devid()

            # Get challenge token
            challenge_response = self._make_auth_request("token")
            challenge = challenge_response.get("result")

            if not isinstance(challenge, str) or not challenge or not challenge.strip("0"):
                raise CudyAuthError(
                    "Router returned invalid challenge token. "
                    "This may indicate the router is busy or the API has changed."
                )

            # Calculate authentication hash (matches web UI logic)
            hash1 = hashlib.sha256(f"{self._password}{self.salt}".encode()).hexdigest()
            final_hash = hashlib.sha256(f"{hash1}{challenge}".encode()).hexdigest()

            # Login with calculated hash
            self.auth_token = None
            self.session.cookies.clear()
            login_response = self._make_auth_request("login", ["admin", final_hash])

            # Try to get token from cookie or response body
            self.auth_token = (
                self.session.cookies.get("sysauth")
                or self.session.cookies.get("stok")
                or login_response.get("result")
            )

            if not isinstance(self.auth_token, str) or len(self.auth_token) < 10:
                raise CudyAuthError(
                    "No valid authentication token received. "
                    "This usually means incorrect password or the router rejected the login."
                )

            logger.info("Authentication successful")
            return True

        except (CudyAPIError, CudyAuthError, CudyDiscoveryError) as e:
            logger.error(f"Authentication failed: {e}")
            self.auth_token = None
            self.session.cookies.clear()
            return False

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid auth token, authenticate if needed.

        Raises:
            CudyAuthError: If authentication is required but fails
        """
        if not self.auth_token:
            logger.info("No auth token, authenticating...")
            if not self.authenticate():
                raise CudyAuthError("Authentication required but failed")

    # Only source-confirmed reads may be replayed after authentication rejection.
    READ_METHODS = frozenset(
        {
            "system.info",
            "devices.get_devlist_ex",
            "net.iface_status",
            "feature.supported",
            "eth.getstatus",
            "mesh.get_clients",
            "mesh.get_devices",
            "net.traffic_stat",
            "conf.get_workmodes",
            "wifi.get_schedule",
            "wifi.get_wds_status",
            "wifi.get_wps_status",
            "vpn.get_status",
            "conf.get_rate_limit",
            "conf.get_internet_schedule",
            "devices.get_devinfo",
            "conf.get_all",
            "conf.get_system",
            "conf.get_ipv6",
            "conf.get_defaults",
            "conf.get_ddns",
            "conf.get_pingcheck",
            "conf.get_autoreboot",
            "conf.get_qos",
            "devices.get_name",
            "devices.traffic_stat",
            "wifi.get_freqlist",
            "wifi.get_aplist",
            "iptv.get_conf",
            "easymesh.get_conf",
            "multi_ssid.get_all_multi_ssid_iface",
            "multi_ssid.get_conf",
            "parental_control.get_conf",
            "net.online_interfaces",
            "vpn.get_conf",
            "vpn.get_connection",
            "adshield.get_providers",
            "adshield.get_conf",
            "cellular.getstatus",
            "cellular.get_data",
            "cellular.get_statistics",
            "devices.get_devlist",
            "system.upgrade_fwinfo",
            "system.upgrade_checkstatus",
            "apply_status",
        }
    )

    def call_api(
        self, method: str, params: Optional[List[Any]] = None, retry_auth: bool = True
    ) -> Dict[str, Any]:
        """Return the RPC envelope. Custom methods may mutate router state.

        Only known reads are retried, once, after an authentication rejection.
        Timeouts, network failures and mutation requests are never replayed.
        """
        if self._closed:
            raise CudyAPIError("Router session is closed")
        if not isinstance(method, str) or not method.strip():
            raise ValueError("method must be a nonempty string")
        if params is not None and not isinstance(params, list):
            raise TypeError("params must be a list or None")
        self._ensure_authenticated()
        try:
            return self._rpc_request(self.API_PATH, method, params, authenticated=True)
        except CudyAuthError as error:
            self.auth_token = None
            self.session.cookies.clear()
            if retry_auth and self._password and method in self.READ_METHODS:
                if self.authenticate():
                    return self.call_api(method, params, retry_auth=False)
            raise CudyAuthError(
                "Authentication rejected; supply a fresh token or password", code=error.code
            ) from None

    def get_devices(self) -> List[Device]:
        """Return parsed clients; malformed responses raise CudyAPIError."""
        response = self.call_api("devices.get_devlist_ex")
        records = []
        expected_count = None
        while True:
            result = response["result"]
            if not isinstance(result, dict) or not isinstance(result.get("devlist"), list):
                raise CudyAPIError("Device response must contain a devlist array")
            count = result.get("devcnt")
            if count is not None and (type(count) is not int or count < 0):
                raise CudyAPIError("Device count must be a nonnegative integer")
            if expected_count is not None and count != expected_count:
                raise CudyAPIError("Device count changed during pagination; retry the read")
            expected_count = count
            batch = result["devlist"]
            records.extend(batch)
            if count is None or len(records) == count:
                break
            if len(records) > count or not batch:
                raise CudyAPIError("Device list does not match its reported count")
            # The app uses inclusive, one-based start/end indexes.
            response = self.call_api(
                "devices.get_devlist_ex", [len(records) + 1, min(len(records) + 100, count)]
            )
        devices = []
        seen = set()
        for index, item in enumerate(records):
            if not isinstance(item, dict):
                raise CudyAPIError("Device entry %d must be an object" % index)
            try:
                device = Device.from_api_response(item)
            except (TypeError, ValueError, OverflowError):
                raise CudyAPIError("Invalid device entry at index %d" % index) from None
            if device.mac_address != "unknown":
                if device.mac_address in seen:
                    raise CudyAPIError("Repeated client in device list; retry the read")
                seen.add(device.mac_address)
            devices.append(device)
        return devices

    def _read_supported_features(self) -> Any:
        """Return firmware feature declarations without guessing model capabilities."""
        return self.call_api("feature.supported")["result"]

    def _read_ethernet_status(self) -> Any:
        """Return raw Ethernet port status."""
        return self.call_api("eth.getstatus")["result"]

    def _read_mesh_clients(self) -> Any:
        """Return raw mesh client data; availability depends on firmware and mode."""
        return self.call_api("mesh.get_clients")["result"]

    def _read_traffic_stats(self) -> Any:
        """Return raw network traffic statistics."""
        return self.call_api("net.traffic_stat")["result"]

    def _read_client_names(self) -> List[Dict[str, Any]]:
        """Read raw named-client records; null means no records.

        This is not a MAC-to-name dictionary or evidence of physical identity.
        Unknown fields and identifiers are preserved without normalization.
        """
        return self._read_list("devices.get_name")

    def _read_legacy_devices(self) -> List[Dict[str, Any]]:
        """Read the legacy raw client array; null becomes no entries.

        Unlike get_devices(), this performs no extended-list pagination or
        typed conversion. It is not an automatic fallback for failed reads.
        """
        return self._read_list("devices.get_devlist")

    def _read_firmware_update_info(self) -> Optional[Dict[str, Any]]:
        """Read available firmware metadata; do not initiate an update check.

        Metadata may be stale. An empty-array response becomes None (unavailable).
        Does not download or install firmware.
        """
        return self._read_optional_firmware_object("system.upgrade_fwinfo")

    def get_firmware_check_status(self, device_id: str) -> Optional[str]:
        """Read an existing firmware-check state once for a known target ID.

        Does not initiate a check, poll, download or upgrade. No target is guessed.
        """
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must be a nonempty string")
        result = self.call_api("system.upgrade_checkstatus", [device_id])["result"]
        if result is not None and not isinstance(result, str):
            raise CudyAPIError("Firmware check status must be a string or null")
        return result

    def get_apply_status(self) -> Optional[str]:
        """Read configuration-application state once; never apply or poll changes."""
        result = self.call_api("apply_status")["result"]
        if result is not None and not isinstance(result, str):
            raise CudyAPIError("Apply status must be a string or null")
        return result

    def _read_client_traffic_page(self, page: int = 1) -> Dict[str, Any]:
        """Read one traffic page of up to 100 clients, retaining raw metadata.

        This is a current snapshot, not historical bandwidth usage. Pages are
        not atomic across calls. No counters are reset or converted.
        """
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        result = self.call_api("devices.traffic_stat", [(page - 1) * 100 + 1, page * 100])["result"]
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("devlist"), list)
            or not all(isinstance(item, dict) for item in result["devlist"])
        ):
            raise CudyAPIError("Client traffic page must contain a devlist array")
        count = result.get("devcnt")
        if count is not None and (type(count) is not int or count < 0):
            raise CudyAPIError("Client traffic count must be a nonnegative integer")
        return result

    def _read_wifi_frequencies(self) -> Dict[str, Any]:
        """Read raw per-interface frequency information without scanning.

        Firmware-specific interface names and nested fields remain unchanged.
        """
        return self._read_object("wifi.get_freqlist")

    def _read_wifi_scan_results(
        self, interface: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Read existing AP results once; never trigger or wait for a scan.

        Null means results are unavailable/not ready, distinct from an empty
        list. Results may be stale and may contain sensitive network details.
        """
        if interface is not None and (not isinstance(interface, str) or not interface.strip()):
            raise ValueError("interface must be a nonempty string")
        result = self.call_api("wifi.get_aplist", [] if interface is None else [interface])[
            "result"
        ]
        if result is not None and (
            not isinstance(result, list) or not all(isinstance(item, dict) for item in result)
        ):
            raise CudyAPIError("Wi-Fi scan results must be an array of objects or null")
        return result

    def _read_list(self, method: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        result = self.call_api(method, params)["result"]
        if result is None:
            return []
        if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
            raise CudyAPIError("Expected an array of objects from " + method)
        return result

    @staticmethod
    def _client_mac(mac: str) -> str:
        if not isinstance(mac, str):
            raise ValueError("MAC address must be a string")
        if re.fullmatch(r"[0-9a-fA-F]{12}", mac):
            return ":".join(mac[i : i + 2].lower() for i in range(0, 12, 2))
        if not re.fullmatch(r"[0-9a-fA-F]{2}([:-])[0-9a-fA-F]{2}(?:\1[0-9a-fA-F]{2}){4}", mac):
            raise ValueError("Invalid MAC address")
        return mac.lower().replace("-", ":")

    def get_ethernet_ports(self) -> List[EthernetPort]:
        """Read typed port status, normalizing firmware auto/autoneg variants."""
        data = self._read_ethernet_status()
        if not isinstance(data, list):
            raise CudyAPIError("Ethernet status must be an array")
        try:
            return [EthernetPort.from_api_response(item) for item in data]
        except (ValueError, TypeError):
            raise CudyAPIError("Malformed Ethernet port status") from None

    def _read_work_modes(self) -> List[Dict[str, Any]]:
        """Return available mode/name entries, not the currently selected mode."""
        return self._read_list("conf.get_workmodes")

    def _read_wifi_schedule(self) -> List[Dict[str, Any]]:
        """Read Wi-Fi schedules without modifying them; null means no entries."""
        return self._read_list("wifi.get_schedule")

    def _read_wds_status(self, interface: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Read WDS status, optionally for one interface; null stays unknown/absent."""
        if interface is not None and (not isinstance(interface, str) or not interface.strip()):
            raise ValueError("interface must be a nonempty string")
        result = self.call_api("wifi.get_wds_status", [interface] if interface else [])["result"]
        if result is not None and not isinstance(result, dict):
            raise CudyAPIError("WDS status must be an object or null")
        return result

    def get_wps_status(self) -> Optional[str]:
        """Read the firmware WPS state string; this does not start WPS."""
        result = self.call_api("wifi.get_wps_status")["result"]
        if result is not None and not isinstance(result, str):
            raise CudyAPIError("WPS status must be a string or null")
        return result

    def _read_vpn_status(self) -> Any:
        """Read firmware-specific VPN status; older firmware may reject the method."""
        return self.call_api("vpn.get_status")["result"]

    def get_online_interfaces(self) -> List[str]:
        """Read firmware-reported online interface names, without a reachability test."""
        result = self.call_api("net.online_interfaces")["result"]
        if result is None:
            return []
        if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
            raise CudyAPIError("Online interfaces must be an array of strings")
        return result

    def _read_vpn_profiles(self, category: str = "clients") -> Dict[str, Any]:
        """Read a VPN configuration category, preserving its outer object.

        Distinct from get_vpn_config(), which reads general VPN settings.
        May contain private keys and credentials; do not log the result.
        """
        if not isinstance(category, str) or not category.strip():
            raise ValueError("category must be a nonempty string")
        return self._read_object("vpn.get_conf", [category])

    def _read_vpn_client_config(self, client_id: str) -> Dict[str, Any]:
        """Read a known VPN client profile; retain the firmware response wrapper.

        May contain private keys and credentials. Does not enable the client.
        """
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be a nonempty string")
        return self._read_object("vpn.get_conf", ["clients", client_id])

    def _read_vpn_connection_page(self, vpn_type: str, page: int = 1) -> Dict[str, Any]:
        """Read one connection page of up to 100 entries; not historical usage.

        Preserve native handshake values and count metadata. Does not connect,
        disconnect, export profiles or generate keys. Pages are not atomic.
        """
        if not isinstance(vpn_type, str) or not vpn_type.strip():
            raise ValueError("vpn_type must be a nonempty string")
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        result = self._read_object(
            "vpn.get_connection", [vpn_type, (page - 1) * 100 + 1, page * 100]
        )
        entries = result.get("connection_list")
        if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
            raise CudyAPIError("VPN connection page must contain a connection_list array")
        count = result.get("total_cnt")
        if count is not None and (type(count) is not int or count < 0):
            raise CudyAPIError("VPN connection count must be a nonnegative integer")
        return result

    def _read_vpn_config(self) -> Dict[str, Any]:
        """Read VPN enabled/policy/protocol configuration; may contain private fields.

        This does not establish tunnel connectivity. Do not log the raw result.
        """
        return self._read_config(["vpn", "config"])

    def _read_mesh_device_page(self, node_id: str, page: int = 1) -> Dict[str, Any]:
        """Read a mesh node's client page (up to 100), retaining devcnt metadata.

        Select the actual node identifier from mesh data. This does not discover,
        add, roam, scan, or modify mesh nodes. Result devlist entries stay raw.
        """
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be nonempty text")
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        result = self.call_api("mesh.get_devices", [node_id, (page - 1) * 100 + 1, page * 100])[
            "result"
        ]
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("devlist"), list)
            or not all(isinstance(item, dict) for item in result["devlist"])
        ):
            raise CudyAPIError("Mesh client page must contain a devlist array")
        count = result.get("devcnt")
        if count is not None and (type(count) is not int or count < 0):
            raise CudyAPIError("Mesh client count must be a nonnegative integer")
        return result

    def get_system_status(self) -> SystemStatus:
        """Read a system snapshot; alias of get_system_info."""
        try:
            return SystemStatus.from_api_response(self._read_system_info())
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed system status") from None

    def get_interface_status(self, interface: str = "wan") -> InterfaceStatus:
        """Read an interface snapshot; alias of get_network_status."""
        # Validate before parsing, retaining the raw reader's argument errors.
        result = self._read_network_status(interface)
        try:
            return InterfaceStatus.from_api_response(result)
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed interface status") from None

    def _read_object(self, method: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        result = self.call_api(method, params)["result"]
        if not isinstance(result, dict):
            raise CudyAPIError("Expected an object from " + method)
        return result

    def _read_config(self, sections: List[str]) -> Dict[str, Any]:
        return self._read_object("conf.get_all", sections)

    def _read_optional_firmware_object(self, method: str) -> Optional[Dict[str, Any]]:
        result = self.call_api(method)["result"]
        if isinstance(result, list) and not result:
            return None
        if not isinstance(result, dict):
            raise CudyAPIError("Expected an object or empty array from " + method)
        return result

    def _read_system_config(self) -> Dict[str, Any]:
        """Read system settings, not runtime system status; preserve raw fields."""
        return self._read_object("conf.get_system")

    def _read_ipv6_config(self) -> Dict[str, Any]:
        """Read IPv6 settings without testing connectivity or changing interfaces."""
        return self._read_object("conf.get_ipv6")

    def _read_default_config(self) -> Dict[str, Any]:
        """Read firmware defaults without restoring them; may contain credentials."""
        return self._read_object("conf.get_defaults")

    def _read_ddns_config(self) -> Dict[str, Any]:
        """Read DDNS settings; may include account credentials. Do not log them."""
        return self._read_object("conf.get_ddns")

    def _read_connectivity_check_config(self) -> Dict[str, Any]:
        """Read configured connectivity-check targets; does not run a check."""
        return self._read_object("conf.get_pingcheck")

    def _read_auto_reboot_config(self) -> Optional[Dict[str, Any]]:
        """Read reboot settings; empty-array responses become None (unavailable).

        Does not schedule or cause a reboot. None does not imply disabled.
        """
        return self._read_optional_firmware_object("conf.get_autoreboot")

    def _read_qos_config(self) -> Any:
        """Read firmware-defined QoS JSON; preserve null and all result shapes."""
        return self.call_api("conf.get_qos")["result"]

    def _read_iptv_config(self) -> Dict[str, Any]:
        """Read IPTV settings and available profiles without applying a profile."""
        return self._read_object("iptv.get_conf")

    @staticmethod
    def _cellular_interface(interface: str) -> List[str]:
        if not isinstance(interface, str) or not interface.strip():
            raise ValueError("interface must be a nonempty string")
        return [interface]

    def _read_cellular_status(self, interface: str) -> Dict[str, Any]:
        """Read raw modem status for a known interface; may contain SIM identifiers.

        Does not enable the modem, select a SIM or initiate a connection.
        """
        return self._read_object("cellular.getstatus", self._cellular_interface(interface))

    def _read_cellular_data_config(self, interface: str) -> List[Dict[str, Any]]:
        """Read raw data-plan settings as a list; null becomes no entries.

        No limits, billing dates or counters are changed. Units remain raw.
        """
        return self._read_list("cellular.get_data", self._cellular_interface(interface))

    def _read_cellular_statistics(self, interface: str) -> Dict[str, Any]:
        """Read native cellular statistics without clearing or converting counters.

        Accounting periods and firmware-specific nested fields remain raw.
        """
        return self._read_object("cellular.get_statistics", self._cellular_interface(interface))

    def _read_adshield_providers(self) -> Dict[str, Any]:
        """Read the raw provider-catalog object, retaining its providers field."""
        return self._read_object("adshield.get_providers")

    def _read_adshield_config(self) -> Dict[str, Any]:
        """Read ad-blocking settings; may contain account credentials. Do not log."""
        return self._read_object("adshield.get_conf")

    def _read_adshield_provider(self, method: str, provider: str) -> Dict[str, Any]:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider must be a nonempty string")
        # Provider services may be contacted; never automatically replay these reads.
        result = self.call_api(method, [provider], retry_auth=False)["result"]
        if not isinstance(result, dict):
            raise CudyAPIError("Expected an object from " + method)
        return result

    def _read_adshield_status(self, provider: str) -> Dict[str, Any]:
        """Read provider status once, retaining nested provider error codes.

        May contact an external provider through the router. No automatic auth
        replay, OAuth initialization or configuration changes are performed.
        """
        return self._read_adshield_provider("adshield.get_status", provider)

    def _read_adshield_stats(self, provider: str) -> Dict[str, Any]:
        """Read raw provider statistics once; do not infer periods or reset counts.

        May contact an external provider through the router. Sensitive account
        and DNS-usage data remain raw. Do not log the result.
        """
        return self._read_adshield_provider("adshield.get_stats", provider)

    def _read_easymesh_config(self) -> Dict[str, Any]:
        """Read EasyMesh settings, not topology; never initiate enrollment."""
        return self._read_object("easymesh.get_conf")

    def get_multi_ssid_interfaces(self) -> List[str]:
        """Read firmware multi-SSID section identifiers; null means no entries."""
        result = self.call_api("multi_ssid.get_all_multi_ssid_iface")["result"]
        if result is None:
            return []
        if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
            raise CudyAPIError("Multi-SSID interfaces must be an array of strings")
        return result

    def _read_multi_ssid_config(self, section: str) -> Optional[Dict[str, Any]]:
        """Read one known multi-SSID section; null remains absent/unknown.

        May contain Wi-Fi or RADIUS credentials. Do not log the raw result.
        This does not add, remove or enable an SSID.
        """
        if not isinstance(section, str) or not section.strip():
            raise ValueError("section must be a nonempty string")
        result = self.call_api("multi_ssid.get_conf", ["wireless", section])["result"]
        if result is not None and not isinstance(result, dict):
            raise CudyAPIError("Multi-SSID configuration must be an object or null")
        return result

    def _read_parental_control_config(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """Read raw parental groups, optionally selecting one by its name.

        Even a selected group returns a list. Null means no records. Device
        lists and schedules are private; no policy or schedule is changed.
        """
        if group is not None and (not isinstance(group, str) or not group.strip()):
            raise ValueError("group must be a nonempty string")
        return self._read_list("parental_control.get_conf", [] if group is None else [group])

    def get_lan_config(self) -> LanConfig:
        """Read configured LAN fields; this is not live interface status."""
        result = self._read_config(["network", "lan"])
        try:
            return LanConfig.from_api_response(result)
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed LAN configuration") from None

    def _read_dhcp_config(self) -> Dict[str, Any]:
        """Read DHCP sections verbatim, including firmware-specific entries.

        May contain private client/network configuration. Do not log the result.
        """
        return self._read_config(["dhcp"])

    def _read_wireless_config(self) -> Dict[str, Any]:
        """Read wireless sections, including credentials when firmware returns them.

        This does not scan, activate WPS, or change Wi-Fi. Do not log the result.
        Section names vary by firmware; no radio/interface list is hardcoded.
        """
        return self._read_config(["wireless"])

    def get_wireless_interface(self, section: str) -> Optional[WirelessInterface]:
        """Read one selected wireless section; absent sections return None.

        Choose a section from get_wireless_config, not an OS interface name.
        This downloads the configuration once and does not scan Wi-Fi.
        """
        if not isinstance(section, str) or not section.strip():
            raise ValueError("section must be nonempty text")
        config = self._read_wireless_config()
        if section not in config:
            return None
        try:
            return WirelessInterface.from_api_response(section, config[section])
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed wireless interface configuration") from None

    def set_wifi_config(self, config: Dict[str, Any]) -> Any:
        """Submit a firmware-specific Wi-Fi configuration object; never replay.

        APK format: {"iface": {section: fields}, "radio": {...}, "mld": {...},
        optionally "access_filter". Only supplied fields are transmitted; no
        merge or firmware validation is implied. Do not pass the flat result
        of get_wireless_config directly. Changes can disconnect this session.
        """
        allowed = {"iface", "radio", "mld", "access_filter"}
        if not isinstance(config, dict) or not config or not set(config) <= allowed:
            raise ValueError("Expected a nonempty Wi-Fi configuration object")
        for key, value in config.items():
            if key == "access_filter":
                if type(value) is not int:
                    raise ValueError("access_filter must be an integer")
            elif not isinstance(value, dict) or not value:
                raise ValueError("Wi-Fi configuration groups must be nonempty objects")
            else:
                for section, fields in value.items():
                    if not isinstance(section, str) or not section.strip():
                        raise ValueError("Wi-Fi section names must be nonempty text")
                    if not isinstance(fields, dict) or not fields:
                        raise ValueError("Wi-Fi sections must contain configuration fields")
        try:

            def validate_keys(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if not isinstance(key, str):
                            raise ValueError("Configuration keys must be strings")
                        validate_keys(item)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        validate_keys(item)

            # JSON otherwise silently converts integer/boolean keys to text.
            validate_keys(config)
            # Validate JSON compatibility and detach the submitted snapshot.
            snapshot = json.loads(json.dumps(config, allow_nan=False))
        except (TypeError, ValueError, OverflowError, RecursionError):
            raise ValueError("Wi-Fi configuration must contain finite JSON values") from None
        return self.call_api("wifi.set_conf", [snapshot], retry_auth=False)["result"]

    def get_client_info(self, mac: str) -> Optional[Device]:
        """Read one client's details directly, without downloading the full list."""
        result = self.call_api("devices.get_devinfo", [self._client_mac(mac)])["result"]
        if result is None:
            return None
        try:
            return Device.from_api_response(result)
        except (TypeError, ValueError, OverflowError):
            raise CudyAPIError("Malformed client information") from None

    def get_client_rate_limit(self, mac: str) -> Optional[RateLimit]:
        """Read a client's configured Mbps limits; null means no configuration."""
        result = self.call_api("conf.get_rate_limit", [self._client_mac(mac)])["result"]
        if result is None:
            return None
        try:
            return RateLimit.from_api_response(result)
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed client rate limit") from None

    def _read_client_internet_schedule(self, mac: str) -> List[Dict[str, Any]]:
        """Read per-client schedules; unsupported firmware raises an RPC error."""
        return self._read_list("conf.get_internet_schedule", [self._client_mac(mac)])

    def set_client_name(
        self, mac: str, name: str, *, device_type: str = "other", brand: str = "undefined"
    ) -> Any:
        """Change client name and metadata. Defaults reset type/brand to app defaults.

        This mutates router configuration and is never automatically replayed.
        Returns the firmware result verbatim, including null acknowledgements.
        """
        mac = self._client_mac(mac)
        for label, value in (("name", name), ("device_type", device_type), ("brand", brand)):
            if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
                raise ValueError(f"{label} must be nonempty text without control characters")
        return self.call_api("devices.set_name", [mac, name, device_type, brand], retry_auth=False)[
            "result"
        ]

    def set_client_internet_blocked(self, mac: str, blocked: bool, *, name: str = "") -> Any:
        """Block/unblock a client's Internet access (a configuration write).

        The optional name is sent as client metadata, as in the app.
        Blocking your own client can interrupt access. No automatic replay.
        """
        mac = self._client_mac(mac)
        if type(blocked) is not bool:
            raise ValueError("blocked must be a boolean")
        if not isinstance(name, str) or any(ord(c) < 32 for c in name):
            raise ValueError("name must be text without control characters")
        return self.call_api("devices.internet_block", [int(blocked), mac, name], retry_auth=False)[
            "result"
        ]

    @staticmethod
    def _rate_limit_text(value: Any) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError("rate must be a nonnegative finite Mbps value")
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("rate must be a nonnegative finite Mbps value") from None
        if not number.is_finite() or number < 0:
            raise ValueError("rate must be a nonnegative finite Mbps value")
        # Match the app's three-decimal wire precision without silent rounding.
        result = format(number, "f")
        if "." in result:
            result = result.rstrip("0").rstrip(".")
        if "." in result and len(result.split(".")[1]) > 3:
            raise ValueError("rate supports at most three decimal places in Mbps")
        return "0" if number == 0 else result

    def set_client_rate_limit(self, mac: str, *, download_mbps: Any, upload_mbps: Any) -> Any:
        """Write both Mbps limits, with up to three decimal places; never replay.

        Zero is sent literally, as in the app. Use clear_client_rate_limit to
        remove the configuration rather than assuming zero clears it.
        """
        mac = self._client_mac(mac)
        limits = {
            "ddrate": self._rate_limit_text(download_mbps),
            "uurate": self._rate_limit_text(upload_mbps),
        }
        return self.call_api("devices.rate_limit", [mac, limits], retry_auth=False)["result"]

    def clear_client_rate_limit(self, mac: str) -> Any:
        """Remove the client's rate-limit configuration; never automatically replay."""
        return self.call_api("devices.rate_limit", [self._client_mac(mac)], retry_auth=False)[
            "result"
        ]

    def get_online_devices(self) -> List[Device]:
        """Get clients passing the legacy inactivity-below-30 heuristic.

        Returns:
            Recently active clients; unknown activity is excluded. This does
            not test reachability or establish whether a client is connected.
        """
        return [device for device in self.get_devices() if device.is_online is True]

    def get_wifi_devices(self) -> List[Device]:
        """Get list of devices connected via WiFi.

        Returns:
            List of Device objects connected via WiFi
        """
        return [device for device in self.get_devices() if device.connection_type == "wifi"]

    def get_ethernet_devices(self) -> List[Device]:
        """Get list of devices connected via Ethernet.

        Returns:
            List of Device objects connected via Ethernet
        """
        return [device for device in self.get_devices() if device.connection_type == "ethernet"]

    def get_device_by_mac(self, mac: str) -> Optional[Device]:
        """Find a device by its MAC address.

        Args:
            mac: MAC address to search for (case-insensitive, with or without separators)

        Returns:
            Device object if found, None otherwise
        """
        # Normalize MAC address for comparison
        normalized_mac = mac.lower().replace(":", "").replace("-", "").replace(".", "")

        for device in self.get_devices():
            device_mac = (
                device.mac_address.lower().replace(":", "").replace("-", "").replace(".", "")
            )
            if device_mac == normalized_mac:
                return device
        return None

    def get_device_by_ip(self, ip: str) -> Optional[Device]:
        """Find a device by its IP address.

        Args:
            ip: IP address to search for

        Returns:
            Device object if found, None otherwise
        """
        for device in self.get_devices():
            if device.ip_address == ip:
                return device
        return None

    def get_device_by_hostname(
        self, hostname: str, case_sensitive: bool = False
    ) -> Optional[Device]:
        """Find a device by its hostname.

        Args:
            hostname: Hostname to search for
            case_sensitive: If True, perform case-sensitive search

        Returns:
            Device object if found, None otherwise
        """
        if not case_sensitive:
            hostname = hostname.lower()

        for device in self.get_devices():
            device_hostname = device.hostname or device.device_name or ""
            if not case_sensitive:
                device_hostname = device_hostname.lower()
            if device_hostname == hostname:
                return device
        return None

    def _read_system_info(self) -> Dict[str, Any]:
        """Get router system information.

        Returns:
            Dictionary containing system information such as:
            - model: Router model name
            - firmware_version: Current firmware version
            - uptime: System uptime
            - And other system-related information

        Raises:
            CudyAPIError: If the API call fails
            CudyAuthError: If not authenticated
        """
        response = self.call_api("system.info")
        if not isinstance(response["result"], dict):
            raise CudyAPIError("System information must be an object")
        return response["result"]

    def _read_network_status(self, interface: str = "wan") -> Dict[str, Any]:
        """Get network interface status.

        Returns:
            Dictionary containing status for the requested interface

        Raises:
            CudyAPIError: If the API call fails
            CudyAuthError: If not authenticated
        """
        if not isinstance(interface, str) or not interface.strip():
            raise ValueError("interface must be a nonempty string")
        response = self.call_api("net.iface_status", [interface])
        if not isinstance(response["result"], dict):
            raise CudyAPIError("Network status must be an object")
        return response["result"]

    def reboot(self) -> bool:
        """Reboot the router.

        Warning:
            This will immediately reboot the router, disconnecting all devices.
            The router will be unavailable for 1-2 minutes during reboot.

        Returns:
            True if reboot command was accepted

        Raises:
            CudyAPIError: If the API call fails
            CudyAuthError: If not authenticated
        """
        logger.warning("Initiating router reboot")
        response = self.call_api("system.reboot", retry_auth=False)
        return bool(response.get("result"))

    def _convert(self, value: Any, factory: Callable[[Any], R]) -> R:
        try:
            result = factory(value)
            if isinstance(result, FirmwareRecord):
                validate_record(result)
            return result
        except (ValueError, TypeError):
            raise CudyAPIError("Malformed response model") from None

    def _record(self, model: Type[T], reader: str, *args: Any) -> T:
        return self._convert(getattr(self, reader)(*args), model)

    def _optional(self, model: Type[T], reader: str, *args: Any) -> Optional[T]:
        value = getattr(self, reader)(*args)
        return None if value is None else self._convert(value, model)

    def _records(self, model: Type[T], reader: str, *args: Any) -> List[T]:
        return [self._convert(value, model) for value in getattr(self, reader)(*args)]

    def get_system_info(self) -> SystemStatus:
        """Read SystemStatus; see the model reference for fields and limits."""
        return self.get_system_status()

    def get_network_status(self, interface: str = "wan") -> InterfaceStatus:
        """Read InterfaceStatus; see the model reference for fields and limits."""
        return self.get_interface_status(interface)

    def get_ethernet_status(self) -> List[EthernetPort]:
        """Read List[EthernetPort]; see the model reference for fields and limits."""
        return self.get_ethernet_ports()

    def get_supported_features(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(self._read_supported_features(), deserialize)

    def get_mesh_clients(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(self._read_mesh_clients(), deserialize)

    def get_traffic_stats(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(self._read_traffic_stats(), deserialize)

    def get_vpn_status(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(self._read_vpn_status(), deserialize)

    def get_qos_config(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(self._read_qos_config(), deserialize)

    def get_client_names(self) -> List[ClientName]:
        """Read List[ClientName]; see the model reference for fields and limits."""
        return self._records(ClientName, "_read_client_names")

    def get_legacy_devices(self) -> List[FirmwareRecord]:
        """Read List[FirmwareRecord]; see the model reference for fields and limits."""
        return self._records(FirmwareRecord, "_read_legacy_devices")

    def get_work_modes(self) -> List[WorkMode]:
        """Read List[WorkMode]; see the model reference for fields and limits."""
        return self._records(WorkMode, "_read_work_modes")

    def get_wifi_schedule(self) -> List[Configuration]:
        """Read List[Configuration]; see the model reference for fields and limits."""
        return self._records(Configuration, "_read_wifi_schedule")

    def get_client_internet_schedule(self, mac: str) -> List[Configuration]:
        """Read List[Configuration]; see the model reference for fields and limits."""
        return self._records(Configuration, "_read_client_internet_schedule", mac)

    def get_wifi_frequencies(self) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return self._record(FirmwareRecord, "_read_wifi_frequencies")

    def get_wifi_scan_results(self, interface: Optional[str] = None) -> Optional[List[AccessPoint]]:
        """Read Optional[List[AccessPoint]]; see the model reference for fields and limits."""
        values = self._read_wifi_scan_results(interface)
        return None if values is None else [self._convert(value, AccessPoint) for value in values]

    def get_wds_status(self, interface: Optional[str] = None) -> Optional[WdsStatus]:
        """Read Optional[WdsStatus]; see the model reference for fields and limits."""
        return self._optional(WdsStatus, "_read_wds_status", interface)

    def get_firmware_update_info(self) -> Optional[FirmwareRecord]:
        """Read Optional[FirmwareRecord]; see the model reference for fields and limits."""
        return self._optional(FirmwareRecord, "_read_firmware_update_info")

    def get_client_traffic_page(self, page: int = 1) -> ResponsePage[ClientTraffic]:
        """Read ResponsePage[ClientTraffic]; see the model reference for fields and limits."""
        data = self._read_client_traffic_page(page)
        return self._convert(
            data, lambda value: ResponsePage(value, "devlist", "devcnt", ClientTraffic)
        )

    def get_mesh_device_page(self, node_id: str, page: int = 1) -> ResponsePage[FirmwareRecord]:
        """Read ResponsePage[FirmwareRecord]; see the model reference for fields and limits."""
        data = self._read_mesh_device_page(node_id, page)
        return self._convert(
            data, lambda value: ResponsePage(value, "devlist", "devcnt", FirmwareRecord)
        )

    def get_vpn_connection_page(self, vpn_type: str, page: int = 1) -> ResponsePage[FirmwareRecord]:
        """Read ResponsePage[FirmwareRecord]; see the model reference for fields and limits."""
        data = self._read_vpn_connection_page(vpn_type, page)
        return self._convert(
            data, lambda value: ResponsePage(value, "connection_list", "total_cnt", FirmwareRecord)
        )

    def get_system_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_system_config")

    def get_ipv6_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_ipv6_config")

    def get_default_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_default_config")

    def get_ddns_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_ddns_config")

    def get_connectivity_check_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_connectivity_check_config")

    def get_auto_reboot_config(self) -> Optional[Configuration]:
        """Read Optional[Configuration]; see the model reference for fields and limits."""
        return self._optional(Configuration, "_read_auto_reboot_config")

    def get_iptv_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_iptv_config")

    def get_easymesh_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_easymesh_config")

    def get_multi_ssid_config(self, section: str) -> Optional[WirelessInterface]:
        """Read Optional[WirelessInterface]; see the model reference for fields and limits."""
        value = self._read_multi_ssid_config(section)
        return (
            None
            if value is None
            else self._convert(
                value, lambda data: WirelessInterface.from_api_response(section, data)
            )
        )

    def get_parental_control_config(self, group: Optional[str] = None) -> List[ParentalGroup]:
        """Read List[ParentalGroup]; see the model reference for fields and limits."""
        return self._records(ParentalGroup, "_read_parental_control_config", group)

    def get_vpn_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_vpn_config")

    def get_vpn_profiles(self, category: str = "clients") -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_vpn_profiles", category)

    def get_vpn_client_config(self, client_id: str) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_vpn_client_config", client_id)

    def get_dhcp_config(self) -> ConfigurationSections:
        """Read ConfigurationSections; see the model reference for fields and limits."""
        return self._record(ConfigurationSections, "_read_dhcp_config")

    def get_wireless_config(self) -> ConfigurationSections:
        """Read ConfigurationSections; see the model reference for fields and limits."""
        return self._record(ConfigurationSections, "_read_wireless_config")

    def get_cellular_status(self, interface: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return self._record(FirmwareRecord, "_read_cellular_status", interface)

    def get_cellular_data_config(self, interface: str) -> List[Configuration]:
        """Read List[Configuration]; see the model reference for fields and limits."""
        return self._records(Configuration, "_read_cellular_data_config", interface)

    def get_cellular_statistics(self, interface: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return self._record(FirmwareRecord, "_read_cellular_statistics", interface)

    def get_adshield_providers(self) -> ProviderCatalog:
        """Read ProviderCatalog; see the model reference for fields and limits."""
        return self._record(ProviderCatalog, "_read_adshield_providers")

    def get_adshield_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return self._record(Configuration, "_read_adshield_config")

    def get_adshield_status(self, provider: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return self._record(FirmwareRecord, "_read_adshield_status", provider)

    def get_adshield_stats(self, provider: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return self._record(FirmwareRecord, "_read_adshield_stats", provider)
