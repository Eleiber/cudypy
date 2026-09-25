"""Native asyncio transport for the local Cudy app RPC interface."""

import asyncio
import hashlib
import json
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from urllib.parse import urlparse

from zeroconf import ServiceStateChange

from ..exceptions.api_exceptions import (
    CudyAPIError,
    CudyAuthError,
    CudyDiscoveryError,
    CudyUnsupportedError,
)
from ..models.device import Device
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
    ResponseValue,
    WdsStatus,
    WorkMode,
    deserialize,
)
from ..models.status import (
    EthernetPort,
    InterfaceStatus,
    LanConfig,
    RateLimit,
    SystemStatus,
    WirelessInterface,
)
from .router import CudyRouter, logger

T = TypeVar("T", bound=FirmwareRecord)

try:
    import aiohttp
except ImportError:  # The synchronous package remains usable without the async extra.
    aiohttp = None


class AsyncCudyRouter:
    """Async local RPC client. One instance owns one aiohttp session and router token."""

    AUTH_PATH = CudyRouter.AUTH_PATH
    API_PATH = CudyRouter.API_PATH
    READ_METHODS = CudyRouter.READ_METHODS
    DEFAULT_MDNS_TIMEOUT = CudyRouter.DEFAULT_MDNS_TIMEOUT

    def __init__(
        self,
        base_url: str,
        password: Optional[str] = None,
        *,
        auth_token: Optional[str] = None,
        salt: Optional[str] = None,
        timeout: float = 10,
    ):
        if aiohttp is None:
            raise ImportError("AsyncCudyRouter requires aiohttp; install cudypy[async]")
        if not isinstance(base_url, str) or not base_url or not (password or auth_token):
            raise ValueError("Base URL and a password or authentication token are required")
        if password is not None and not isinstance(password, str):
            raise ValueError("password must be a string")
        if auth_token is not None and (not isinstance(auth_token, str) or not auth_token.strip()):
            raise ValueError("auth_token must be a nonempty string")
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
        parsed.port
        if not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
            raise ValueError("timeout must be a finite positive number")

        self.base_url = base_url.rstrip("/")
        self.router_ip = parsed.hostname
        self._password = password
        self.auth_token = auth_token
        self.salt = salt
        self.timeout = timeout
        self._session = None
        self._auth_lock = asyncio.Lock()
        self._closed = False

    async def __aenter__(self) -> "AsyncCudyRouter":
        await self._get_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _get_session(self):
        if self._closed:
            raise CudyAPIError("Router session is closed")
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
                trust_env=False,
                headers={"Connection": "close", "User-Agent": "CudyPy Client"},
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session and discard local credentials."""
        if not self._closed:
            self._closed = True
            if self._session is not None:
                await self._session.close()
            self._session = None
            self.auth_token = None
            self._password = None

    async def _discover_salt(self) -> None:
        if self.salt:
            return
        from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

        found = asyncio.Event()
        tasks = set()
        azc = AsyncZeroconf()

        async def inspect_service(type_: str, name: str) -> None:
            info = await azc.async_get_service_info(type_, name, timeout=1000)
            if info and self.router_ip in info.parsed_addresses():
                salt = info.properties.get(b"salt")
                if salt:
                    self.salt = salt.decode("utf-8")
                    found.set()

        def on_change(zeroconf, service_type, name, state_change) -> None:
            if state_change in (ServiceStateChange.Added, ServiceStateChange.Updated):
                task = asyncio.create_task(inspect_service(service_type, name))
                tasks.add(task)
                task.add_done_callback(tasks.discard)

        browser = AsyncServiceBrowser(azc.zeroconf, "_http._tcp.local.", handlers=[on_change])
        try:
            await asyncio.wait_for(found.wait(), self.DEFAULT_MDNS_TIMEOUT)
        except asyncio.TimeoutError:
            raise CudyDiscoveryError("mDNS discovery timed out") from None
        except Exception:
            raise CudyDiscoveryError("mDNS discovery failed") from None
        finally:
            await browser.async_cancel()
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await azc.async_close()

    async def _rpc_request(
        self, path: str, method: str, params: Optional[List[Any]] = None, *, authenticated=False
    ) -> Dict[str, Any]:
        session = await self._get_session()
        payload = {"method": method, "params": params if params is not None else []}
        query = {"auth": self.auth_token} if authenticated else None
        try:
            async with session.post(
                self.base_url + path, json=payload, params=query, allow_redirects=False
            ) as response:
                if response.status in (401, 403):
                    raise CudyAuthError("Router rejected authentication")
                if 300 <= response.status < 400:
                    raise CudyAPIError("Router returned an unexpected redirect")
                if response.status >= 400:
                    raise CudyAPIError("Router HTTP request failed")
                data = await response.json(content_type=None)
        except asyncio.TimeoutError:
            raise CudyAPIError("Router request timed out; it was not retried") from None
        except (aiohttp.ClientError, OSError, ValueError, json.JSONDecodeError):
            raise CudyAPIError("Router HTTP request failed or returned invalid JSON") from None
        if not isinstance(data, dict):
            raise CudyAPIError("Router returned a non-object RPC response")
        error = data.get("error")
        if error is not None:
            if not isinstance(error, dict) or type(error.get("code")) is not int:
                raise CudyAPIError("Router returned a malformed RPC error")
            code = error["code"]
            if code == -32003:
                raise CudyAuthError("Router rejected authentication", code=code)
            if code == -32601:
                raise CudyUnsupportedError("RPC method is not supported", code=code)
            raise CudyAPIError("Router RPC failed (Code: %s)" % code, code=code)
        if "result" not in data:
            raise CudyAPIError("Router RPC response is missing result")
        return data

    async def _authenticate_locked(self) -> bool:
        try:
            await self._discover_salt()
            challenge = (await self._rpc_request(self.AUTH_PATH, "token"))["result"]
            if not isinstance(challenge, str) or not challenge or not challenge.strip("0"):
                raise CudyAuthError("Router returned an invalid challenge token")
            first = hashlib.sha256(f"{self._password}{self.salt}".encode()).hexdigest()
            digest = hashlib.sha256(f"{first}{challenge}".encode()).hexdigest()
            self.auth_token = None
            session = await self._get_session()
            session.cookie_jar.clear()
            result = (await self._rpc_request(self.AUTH_PATH, "login", ["admin", digest]))["result"]
            token = session.cookie_jar.filter_cookies(self.base_url).get("sysauth")
            if token is None:
                token = session.cookie_jar.filter_cookies(self.base_url).get("stok")
            self.auth_token = token.value if token is not None else result
            if not isinstance(self.auth_token, str) or len(self.auth_token) < 10:
                raise CudyAuthError("No valid authentication token received")
            return True
        except (CudyAPIError, CudyDiscoveryError):
            self.auth_token = None
            if self._session is not None:
                self._session.cookie_jar.clear()
            return False

    async def authenticate(self, force: bool = False) -> bool:
        """Log in with a password; return False for a rejected login."""
        if self._closed:
            raise CudyAPIError("Router session is closed")
        async with self._auth_lock:
            if self.auth_token and not force:
                return True
            if not self._password:
                raise CudyAuthError("A fresh token or password is required to authenticate")
            return await self._authenticate_locked()

    async def call_api(
        self, method: str, params: Optional[List[Any]] = None, retry_auth: bool = True
    ) -> Dict[str, Any]:
        """Return the full RPC envelope. Custom methods may mutate router state."""
        if self._closed:
            raise CudyAPIError("Router session is closed")
        if not isinstance(method, str) or not method.strip():
            raise ValueError("method must be a nonempty string")
        if params is not None and not isinstance(params, list):
            raise TypeError("params must be a list or None")
        if not self.auth_token and not await self.authenticate():
            raise CudyAuthError("Authentication required but failed")
        token_used = self.auth_token
        try:
            return await self._rpc_request(self.API_PATH, method, params, authenticated=True)
        except CudyAuthError as error:
            if not (retry_auth and self._password and method in self.READ_METHODS):
                if self.auth_token == token_used:
                    self.auth_token = None
                    session = await self._get_session()
                    session.cookie_jar.clear()
                raise CudyAuthError(
                    "Authentication rejected; supply a fresh token or password", code=error.code
                ) from None
            async with self._auth_lock:
                if self.auth_token == token_used:
                    self.auth_token = None
                    session = await self._get_session()
                    session.cookie_jar.clear()
                    if not await self._authenticate_locked():
                        raise CudyAuthError("Authentication required but failed") from None
            return await self._rpc_request(self.API_PATH, method, params, authenticated=True)

    _client_mac = staticmethod(CudyRouter._client_mac)
    _cellular_interface = staticmethod(CudyRouter._cellular_interface)
    _rate_limit_text = staticmethod(CudyRouter._rate_limit_text)
    _convert = CudyRouter._convert

    async def _record(self, model: Type[T], reader: str, *args: Any) -> T:
        return self._convert(await getattr(self, reader)(*args), model)

    async def _optional(self, model: Type[T], reader: str, *args: Any) -> Optional[T]:
        value = await getattr(self, reader)(*args)
        return None if value is None else self._convert(value, model)

    async def _records(self, model: Type[T], reader: str, *args: Any) -> List[T]:
        return [self._convert(value, model) for value in await getattr(self, reader)(*args)]

    async def get_devices(self) -> List[Device]:
        """Return parsed clients; malformed responses raise CudyAPIError."""
        response = await self.call_api("devices.get_devlist_ex")
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
            response = await self.call_api(
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

    async def _read_supported_features(self) -> Any:
        """Return firmware feature declarations without guessing model capabilities."""
        return (await self.call_api("feature.supported"))["result"]

    async def _read_ethernet_status(self) -> Any:
        """Return raw Ethernet port status."""
        return (await self.call_api("eth.getstatus"))["result"]

    async def _read_mesh_clients(self) -> Any:
        """Return raw mesh client data; availability depends on firmware and mode."""
        return (await self.call_api("mesh.get_clients"))["result"]

    async def _read_traffic_stats(self) -> Any:
        """Return raw network traffic statistics."""
        return (await self.call_api("net.traffic_stat"))["result"]

    async def _read_client_names(self) -> List[Dict[str, Any]]:
        """Read raw named-client records; null means no records.

        This is not a MAC-to-name dictionary or evidence of physical identity.
        Unknown fields and identifiers are preserved without normalization.
        """
        return await self._read_list("devices.get_name")

    async def _read_firmware_update_info(self) -> Optional[Dict[str, Any]]:
        """Read available firmware metadata; do not initiate an update check.

        Metadata may be stale. An empty-array response becomes None (unavailable).
        Does not download or install firmware.
        """
        return await self._read_optional_firmware_object("system.upgrade_fwinfo")

    async def get_firmware_check_status(self, device_id: str) -> Optional[str]:
        """Read an existing firmware-check state once for a known target ID.

        Does not initiate a check, poll, download or upgrade. No target is guessed.
        """
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("device_id must be a nonempty string")
        result = (await self.call_api("system.upgrade_checkstatus", [device_id]))["result"]
        if result is not None and (not isinstance(result, str)):
            raise CudyAPIError("Firmware check status must be a string or null")
        return result

    async def get_apply_status(self) -> Optional[str]:
        """Read configuration-application state once; never apply or poll changes."""
        result = (await self.call_api("apply_status"))["result"]
        if result is not None and (not isinstance(result, str)):
            raise CudyAPIError("Apply status must be a string or null")
        return result

    async def _read_client_traffic_page(self, page: int = 1) -> Dict[str, Any]:
        """Read one traffic page of up to 100 clients, retaining raw metadata.

        This is a current snapshot, not historical bandwidth usage. Pages are
        not atomic across calls. No counters are reset or converted.
        """
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        result = (await self.call_api("devices.traffic_stat", [(page - 1) * 100 + 1, page * 100]))[
            "result"
        ]
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("devlist"), list)
            or (not all((isinstance(item, dict) for item in result["devlist"])))
        ):
            raise CudyAPIError("Client traffic page must contain a devlist array")
        count = result.get("devcnt")
        if count is not None and (type(count) is not int or count < 0):
            raise CudyAPIError("Client traffic count must be a nonnegative integer")
        return result

    async def _read_wifi_frequencies(self) -> Dict[str, Any]:
        """Read raw per-interface frequency information without scanning.

        Firmware-specific interface names and nested fields remain unchanged.
        """
        return await self._read_object("wifi.get_freqlist")

    async def _read_wifi_scan_results(
        self, interface: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """Read existing AP results once; never trigger or wait for a scan.

        Null means results are unavailable/not ready, distinct from an empty
        list. Results may be stale and may contain sensitive network details.
        """
        if interface is not None and (not isinstance(interface, str) or not interface.strip()):
            raise ValueError("interface must be a nonempty string")
        result = (await self.call_api("wifi.get_aplist", [] if interface is None else [interface]))[
            "result"
        ]
        if result is not None and (
            not isinstance(result, list) or not all((isinstance(item, dict) for item in result))
        ):
            raise CudyAPIError("Wi-Fi scan results must be an array of objects or null")
        return result

    async def _read_list(
        self, method: str, params: Optional[List[Any]] = None
    ) -> List[Dict[str, Any]]:
        result = (await self.call_api(method, params))["result"]
        if result is None:
            return []
        if not isinstance(result, list) or not all((isinstance(item, dict) for item in result)):
            raise CudyAPIError("Expected an array of objects from " + method)
        return result

    async def get_ethernet_ports(self) -> List[EthernetPort]:
        """Read typed port status, normalizing firmware auto/autoneg variants."""
        data = await self._read_ethernet_status()
        if not isinstance(data, list):
            raise CudyAPIError("Ethernet status must be an array")
        try:
            return [EthernetPort.from_api_response(item) for item in data]
        except (ValueError, TypeError):
            raise CudyAPIError("Malformed Ethernet port status") from None

    async def _read_work_modes(self) -> List[Dict[str, Any]]:
        """Return available mode/name entries, not the currently selected mode."""
        return await self._read_list("conf.get_workmodes")

    async def _read_wifi_schedule(self) -> List[Dict[str, Any]]:
        """Read Wi-Fi schedules without modifying them; null means no entries."""
        return await self._read_list("wifi.get_schedule")

    async def _read_wds_status(self, interface: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Read WDS status, optionally for one interface; null stays unknown/absent."""
        if interface is not None and (not isinstance(interface, str) or not interface.strip()):
            raise ValueError("interface must be a nonempty string")
        result = (await self.call_api("wifi.get_wds_status", [interface] if interface else []))[
            "result"
        ]
        if result is not None and (not isinstance(result, dict)):
            raise CudyAPIError("WDS status must be an object or null")
        return result

    async def get_wps_status(self) -> Optional[str]:
        """Read the firmware WPS state string; this does not start WPS."""
        result = (await self.call_api("wifi.get_wps_status"))["result"]
        if result is not None and (not isinstance(result, str)):
            raise CudyAPIError("WPS status must be a string or null")
        return result

    async def _read_vpn_status(self) -> Any:
        """Read firmware-specific VPN status; older firmware may reject the method."""
        return (await self.call_api("vpn.get_status"))["result"]

    async def get_online_interfaces(self) -> List[str]:
        """Read firmware-reported online interface names, without a reachability test."""
        result = (await self.call_api("net.online_interfaces"))["result"]
        if result is None:
            return []
        if not isinstance(result, list) or not all((isinstance(item, str) for item in result)):
            raise CudyAPIError("Online interfaces must be an array of strings")
        return result

    async def _read_vpn_profiles(self, category: str = "clients") -> Dict[str, Any]:
        """Read a VPN configuration category, preserving its outer object.

        Distinct from get_vpn_config(), which reads general VPN settings.
        May contain private keys and credentials; do not log the result.
        """
        if not isinstance(category, str) or not category.strip():
            raise ValueError("category must be a nonempty string")
        return await self._read_object("vpn.get_conf", [category])

    async def _read_vpn_client_config(self, client_id: str) -> Dict[str, Any]:
        """Read a known VPN client profile; retain the firmware response wrapper.

        May contain private keys and credentials. Does not enable the client.
        """
        if not isinstance(client_id, str) or not client_id.strip():
            raise ValueError("client_id must be a nonempty string")
        return await self._read_object("vpn.get_conf", ["clients", client_id])

    async def _read_vpn_connection_page(self, vpn_type: str, page: int = 1) -> Dict[str, Any]:
        """Read one connection page of up to 100 entries; not historical usage.

        Preserve native handshake values and count metadata. Does not connect,
        disconnect, export profiles or generate keys. Pages are not atomic.
        """
        if not isinstance(vpn_type, str) or not vpn_type.strip():
            raise ValueError("vpn_type must be a nonempty string")
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        result = await self._read_object(
            "vpn.get_connection", [vpn_type, (page - 1) * 100 + 1, page * 100]
        )
        entries = result.get("connection_list")
        if not isinstance(entries, list) or not all((isinstance(item, dict) for item in entries)):
            raise CudyAPIError("VPN connection page must contain a connection_list array")
        count = result.get("total_cnt")
        if count is not None and (type(count) is not int or count < 0):
            raise CudyAPIError("VPN connection count must be a nonnegative integer")
        return result

    async def _read_vpn_config(self) -> Dict[str, Any]:
        """Read VPN enabled/policy/protocol configuration; may contain private fields.

        This does not establish tunnel connectivity. Do not log the raw result.
        """
        return await self._read_config(["vpn", "config"])

    async def _read_mesh_device_page(self, node_id: str, page: int = 1) -> Dict[str, Any]:
        """Read a mesh node's client page (up to 100), retaining devcnt metadata.

        Select the actual node identifier from mesh data. This does not discover,
        add, roam, scan, or modify mesh nodes. Result devlist entries stay raw.
        """
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError("node_id must be nonempty text")
        if type(page) is not int or page < 1:
            raise ValueError("page must be a positive integer")
        result = (
            await self.call_api("mesh.get_devices", [node_id, (page - 1) * 100 + 1, page * 100])
        )["result"]
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("devlist"), list)
            or (not all((isinstance(item, dict) for item in result["devlist"])))
        ):
            raise CudyAPIError("Mesh client page must contain a devlist array")
        count = result.get("devcnt")
        if count is not None and (type(count) is not int or count < 0):
            raise CudyAPIError("Mesh client count must be a nonnegative integer")
        return result

    async def get_system_status(self) -> SystemStatus:
        """Read a system snapshot; alias of get_system_info."""
        try:
            return SystemStatus.from_api_response(await self._read_system_info())
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed system status") from None

    async def get_interface_status(self, interface: str = "wan") -> InterfaceStatus:
        """Read an interface snapshot; alias of get_network_status."""
        result = await self._read_network_status(interface)
        try:
            return InterfaceStatus.from_api_response(result)
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed interface status") from None

    async def _read_object(self, method: str, params: Optional[List[Any]] = None) -> Dict[str, Any]:
        result = (await self.call_api(method, params))["result"]
        if not isinstance(result, dict):
            raise CudyAPIError("Expected an object from " + method)
        return result

    async def _read_config(self, sections: List[str]) -> Dict[str, Any]:
        return await self._read_object("conf.get_all", sections)

    async def _read_optional_firmware_object(self, method: str) -> Optional[Dict[str, Any]]:
        result = (await self.call_api(method))["result"]
        if isinstance(result, list) and (not result):
            return None
        if not isinstance(result, dict):
            raise CudyAPIError("Expected an object or empty array from " + method)
        return result

    async def _read_system_config(self) -> Dict[str, Any]:
        """Read system settings, not runtime system status; preserve raw fields."""
        return await self._read_object("conf.get_system")

    async def _read_ipv6_config(self) -> Dict[str, Any]:
        """Read IPv6 settings without testing connectivity or changing interfaces."""
        return await self._read_object("conf.get_ipv6")

    async def _read_default_config(self) -> Dict[str, Any]:
        """Read firmware defaults without restoring them; may contain credentials."""
        return await self._read_object("conf.get_defaults")

    async def _read_ddns_config(self) -> Dict[str, Any]:
        """Read DDNS settings; may include account credentials. Do not log them."""
        return await self._read_object("conf.get_ddns")

    async def _read_connectivity_check_config(self) -> Dict[str, Any]:
        """Read configured connectivity-check targets; does not run a check."""
        return await self._read_object("conf.get_pingcheck")

    async def _read_auto_reboot_config(self) -> Optional[Dict[str, Any]]:
        """Read reboot settings; empty-array responses become None (unavailable).

        Does not schedule or cause a reboot. None does not imply disabled.
        """
        return await self._read_optional_firmware_object("conf.get_autoreboot")

    async def _read_qos_config(self) -> Any:
        """Read firmware-defined QoS JSON; preserve null and all result shapes."""
        return (await self.call_api("conf.get_qos"))["result"]

    async def _read_iptv_config(self) -> Dict[str, Any]:
        """Read IPTV settings and available profiles without applying a profile."""
        return await self._read_object("iptv.get_conf")

    async def _read_cellular_status(self, interface: str) -> Dict[str, Any]:
        """Read raw modem status for a known interface; may contain SIM identifiers.

        Does not enable the modem, select a SIM or initiate a connection.
        """
        return await self._read_object("cellular.getstatus", self._cellular_interface(interface))

    async def _read_cellular_data_config(self, interface: str) -> List[Dict[str, Any]]:
        """Read raw data-plan settings as a list; null becomes no entries.

        No limits, billing dates or counters are changed. Units remain raw.
        """
        return await self._read_list("cellular.get_data", self._cellular_interface(interface))

    async def _read_cellular_statistics(self, interface: str) -> Dict[str, Any]:
        """Read native cellular statistics without clearing or converting counters.

        Accounting periods and firmware-specific nested fields remain raw.
        """
        return await self._read_object(
            "cellular.get_statistics", self._cellular_interface(interface)
        )

    async def _read_adshield_providers(self) -> Dict[str, Any]:
        """Read the raw provider-catalog object, retaining its providers field."""
        return await self._read_object("adshield.get_providers")

    async def _read_adshield_config(self) -> Dict[str, Any]:
        """Read ad-blocking settings; may contain account credentials. Do not log."""
        return await self._read_object("adshield.get_conf")

    async def _read_adshield_provider(self, method: str, provider: str) -> Dict[str, Any]:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("provider must be a nonempty string")
        result = (await self.call_api(method, [provider], retry_auth=False))["result"]
        if not isinstance(result, dict):
            raise CudyAPIError("Expected an object from " + method)
        return result

    async def _read_adshield_status(self, provider: str) -> Dict[str, Any]:
        """Read provider status once, retaining nested provider error codes.

        May contact an external provider through the router. No automatic auth
        replay, OAuth initialization or configuration changes are performed.
        """
        return await self._read_adshield_provider("adshield.get_status", provider)

    async def _read_adshield_stats(self, provider: str) -> Dict[str, Any]:
        """Read raw provider statistics once; do not infer periods or reset counts.

        May contact an external provider through the router. Sensitive account
        and DNS-usage data remain raw. Do not log the result.
        """
        return await self._read_adshield_provider("adshield.get_stats", provider)

    async def _read_easymesh_config(self) -> Dict[str, Any]:
        """Read EasyMesh settings, not topology; never initiate enrollment."""
        return await self._read_object("easymesh.get_conf")

    async def get_multi_ssid_interfaces(self) -> List[str]:
        """Read firmware multi-SSID section identifiers; null means no entries."""
        result = (await self.call_api("multi_ssid.get_all_multi_ssid_iface"))["result"]
        if result is None:
            return []
        if not isinstance(result, list) or not all((isinstance(item, str) for item in result)):
            raise CudyAPIError("Multi-SSID interfaces must be an array of strings")
        return result

    async def _read_multi_ssid_config(self, section: str) -> Optional[Dict[str, Any]]:
        """Read one known multi-SSID section; null remains absent/unknown.

        May contain Wi-Fi or RADIUS credentials. Do not log the raw result.
        This does not add, remove or enable an SSID.
        """
        if not isinstance(section, str) or not section.strip():
            raise ValueError("section must be a nonempty string")
        result = (await self.call_api("multi_ssid.get_conf", ["wireless", section]))["result"]
        if result is not None and (not isinstance(result, dict)):
            raise CudyAPIError("Multi-SSID configuration must be an object or null")
        return result

    async def _read_parental_control_config(
        self, group: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Read raw parental groups, optionally selecting one by its name.

        Even a selected group returns a list. Null means no records. Device
        lists and schedules are private; no policy or schedule is changed.
        """
        if group is not None and (not isinstance(group, str) or not group.strip()):
            raise ValueError("group must be a nonempty string")
        return await self._read_list("parental_control.get_conf", [] if group is None else [group])

    async def get_lan_config(self) -> LanConfig:
        """Read configured LAN fields; this is not live interface status."""
        result = await self._read_config(["network", "lan"])
        try:
            return LanConfig.from_api_response(result)
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed LAN configuration") from None

    async def _read_dhcp_config(self) -> Dict[str, Any]:
        """Read DHCP sections verbatim, including firmware-specific entries.

        May contain private client/network configuration. Do not log the result.
        """
        return await self._read_config(["dhcp"])

    async def _read_wireless_config(self) -> Dict[str, Any]:
        """Read wireless sections, including credentials when firmware returns them.

        This does not scan, activate WPS, or change Wi-Fi. Do not log the result.
        Section names vary by firmware; no radio/interface list is hardcoded.
        """
        return await self._read_config(["wireless"])

    async def get_wireless_interface(self, section: str) -> Optional[WirelessInterface]:
        """Read one selected wireless section; absent sections return None.

        Choose a section from get_wireless_config, not an OS interface name.
        This downloads the configuration once and does not scan Wi-Fi.
        """
        if not isinstance(section, str) or not section.strip():
            raise ValueError("section must be nonempty text")
        config = await self._read_wireless_config()
        if section not in config:
            return None
        try:
            return WirelessInterface.from_api_response(section, config[section])
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed wireless interface configuration") from None

    async def set_wifi_config(self, config: Dict[str, Any]) -> Any:
        """Submit a firmware-specific Wi-Fi configuration object; never replay.

        APK format: {"iface": {section: fields}, "radio": {...}, "mld": {...},
        optionally "access_filter". Only supplied fields are transmitted; no
        merge or firmware validation is implied. Do not pass the flat result
        of get_wireless_config directly. Changes can disconnect this session.
        """
        allowed = {"iface", "radio", "mld", "access_filter"}
        if not isinstance(config, dict) or not config or (not set(config) <= allowed):
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

            validate_keys(config)
            snapshot = json.loads(json.dumps(config, allow_nan=False))
        except (TypeError, ValueError, OverflowError, RecursionError):
            raise ValueError("Wi-Fi configuration must contain finite JSON values") from None
        return (await self.call_api("wifi.set_conf", [snapshot], retry_auth=False))["result"]

    async def get_client_info(self, mac: str) -> Optional[Device]:
        """Read one client's details directly, without downloading the full list."""
        result = (await self.call_api("devices.get_devinfo", [self._client_mac(mac)]))["result"]
        if result is None:
            return None
        try:
            return Device.from_api_response(result)
        except (TypeError, ValueError, OverflowError):
            raise CudyAPIError("Malformed client information") from None

    async def get_client_rate_limit(self, mac: str) -> Optional[RateLimit]:
        """Read a client's configured Mbps limits; null means no configuration."""
        result = (await self.call_api("conf.get_rate_limit", [self._client_mac(mac)]))["result"]
        if result is None:
            return None
        try:
            return RateLimit.from_api_response(result)
        except (TypeError, ValueError):
            raise CudyAPIError("Malformed client rate limit") from None

    async def _read_client_internet_schedule(self, mac: str) -> List[Dict[str, Any]]:
        """Read per-client schedules; unsupported firmware raises an RPC error."""
        return await self._read_list("conf.get_internet_schedule", [self._client_mac(mac)])

    async def set_client_name(
        self, mac: str, name: str, *, device_type: str = "other", brand: str = "undefined"
    ) -> Any:
        """Change client name and metadata. Defaults reset type/brand to app defaults.

        This mutates router configuration and is never automatically replayed.
        Returns the firmware result verbatim, including null acknowledgements.
        """
        mac = self._client_mac(mac)
        for label, value in (("name", name), ("device_type", device_type), ("brand", brand)):
            if not isinstance(value, str) or not value.strip() or any((ord(c) < 32 for c in value)):
                raise ValueError(f"{label} must be nonempty text without control characters")
        return (
            await self.call_api(
                "devices.set_name", [mac, name, device_type, brand], retry_auth=False
            )
        )["result"]

    async def set_client_internet_blocked(self, mac: str, blocked: bool, *, name: str = "") -> Any:
        """Block/unblock a client's Internet access (a configuration write).

        The optional name is sent as client metadata, as in the app.
        Blocking your own client can interrupt access. No automatic replay.
        """
        mac = self._client_mac(mac)
        if type(blocked) is not bool:
            raise ValueError("blocked must be a boolean")
        if not isinstance(name, str) or any((ord(c) < 32 for c in name)):
            raise ValueError("name must be text without control characters")
        return (
            await self.call_api(
                "devices.internet_block", [int(blocked), mac, name], retry_auth=False
            )
        )["result"]

    async def set_client_rate_limit(self, mac: str, *, download_mbps: Any, upload_mbps: Any) -> Any:
        """Write both Mbps limits, with up to three decimal places; never replay.

        Zero is sent literally, as in the app. Use clear_client_rate_limit to
        remove the configuration rather than assuming zero clears it.
        """
        mac = self._client_mac(mac)
        limits = {
            "ddrate": self._rate_limit_text(download_mbps),
            "uurate": self._rate_limit_text(upload_mbps),
        }
        return (await self.call_api("devices.rate_limit", [mac, limits], retry_auth=False))[
            "result"
        ]

    async def clear_client_rate_limit(self, mac: str) -> Any:
        """Remove the client's rate-limit configuration; never automatically replay."""
        return (
            await self.call_api("devices.rate_limit", [self._client_mac(mac)], retry_auth=False)
        )["result"]

    async def get_online_devices(self) -> List[Device]:
        """Get clients passing the legacy inactivity-below-30 heuristic.

        Returns:
            Recently active clients; unknown activity is excluded. This does
            not test reachability or establish whether a client is connected.
        """
        return [device for device in await self.get_devices() if device.is_online is True]

    async def get_wifi_devices(self) -> List[Device]:
        """Get list of devices connected via WiFi.

        Returns:
            List of Device objects connected via WiFi
        """
        return [device for device in await self.get_devices() if device.connection_type == "wifi"]

    async def get_ethernet_devices(self) -> List[Device]:
        """Get list of devices connected via Ethernet.

        Returns:
            List of Device objects connected via Ethernet
        """
        return [
            device for device in await self.get_devices() if device.connection_type == "ethernet"
        ]

    async def get_device_by_mac(self, mac: str) -> Optional[Device]:
        """Find a device by its MAC address.

        Args:
            mac: MAC address to search for (case-insensitive, with or without separators)

        Returns:
            Device object if found, None otherwise
        """
        normalized_mac = mac.lower().replace(":", "").replace("-", "").replace(".", "")
        for device in await self.get_devices():
            device_mac = (
                device.mac_address.lower().replace(":", "").replace("-", "").replace(".", "")
            )
            if device_mac == normalized_mac:
                return device
        return None

    async def get_device_by_ip(self, ip: str) -> Optional[Device]:
        """Find a device by its IP address.

        Args:
            ip: IP address to search for

        Returns:
            Device object if found, None otherwise
        """
        for device in await self.get_devices():
            if device.ip_address == ip:
                return device
        return None

    async def get_device_by_hostname(
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
        for device in await self.get_devices():
            device_hostname = device.hostname or device.device_name or ""
            if not case_sensitive:
                device_hostname = device_hostname.lower()
            if device_hostname == hostname:
                return device
        return None

    async def _read_system_info(self) -> Dict[str, Any]:
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
        response = await self.call_api("system.info")
        if not isinstance(response["result"], dict):
            raise CudyAPIError("System information must be an object")
        return response["result"]

    async def _read_network_status(self, interface: str = "wan") -> Dict[str, Any]:
        """Get network interface status.

        Returns:
            Dictionary containing status for the requested interface

        Raises:
            CudyAPIError: If the API call fails
            CudyAuthError: If not authenticated
        """
        if not isinstance(interface, str) or not interface.strip():
            raise ValueError("interface must be a nonempty string")
        response = await self.call_api("net.iface_status", [interface])
        if not isinstance(response["result"], dict):
            raise CudyAPIError("Network status must be an object")
        return response["result"]

    async def reboot(self) -> bool:
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
        response = await self.call_api("system.reboot", retry_auth=False)
        return bool(response.get("result"))

    async def get_system_info(self) -> SystemStatus:
        """Read SystemStatus; see the model reference for fields and limits."""
        return await self.get_system_status()

    async def get_network_status(self, interface: str = "wan") -> InterfaceStatus:
        """Read InterfaceStatus; see the model reference for fields and limits."""
        return await self.get_interface_status(interface)

    async def get_ethernet_status(self) -> List[EthernetPort]:
        """Read List[EthernetPort]; see the model reference for fields and limits."""
        return await self.get_ethernet_ports()

    async def get_supported_features(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(await self._read_supported_features(), deserialize)

    async def get_mesh_clients(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(await self._read_mesh_clients(), deserialize)

    async def get_traffic_stats(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(await self._read_traffic_stats(), deserialize)

    async def get_vpn_status(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(await self._read_vpn_status(), deserialize)

    async def get_qos_config(self) -> ResponseValue:
        """Read ResponseValue; see the model reference for fields and limits."""
        return self._convert(await self._read_qos_config(), deserialize)

    async def get_client_names(self) -> List[ClientName]:
        """Read List[ClientName]; see the model reference for fields and limits."""
        return await self._records(ClientName, "_read_client_names")

    async def get_work_modes(self) -> List[WorkMode]:
        """Read List[WorkMode]; see the model reference for fields and limits."""
        return await self._records(WorkMode, "_read_work_modes")

    async def get_wifi_schedule(self) -> List[Configuration]:
        """Read List[Configuration]; see the model reference for fields and limits."""
        return await self._records(Configuration, "_read_wifi_schedule")

    async def get_client_internet_schedule(self, mac: str) -> List[Configuration]:
        """Read List[Configuration]; see the model reference for fields and limits."""
        return await self._records(Configuration, "_read_client_internet_schedule", mac)

    async def get_wifi_frequencies(self) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return await self._record(FirmwareRecord, "_read_wifi_frequencies")

    async def get_wifi_scan_results(
        self, interface: Optional[str] = None
    ) -> Optional[List[AccessPoint]]:
        """Read Optional[List[AccessPoint]]; see the model reference for fields and limits."""
        values = await self._read_wifi_scan_results(interface)
        return None if values is None else [self._convert(value, AccessPoint) for value in values]

    async def get_wds_status(self, interface: Optional[str] = None) -> Optional[WdsStatus]:
        """Read Optional[WdsStatus]; see the model reference for fields and limits."""
        return await self._optional(WdsStatus, "_read_wds_status", interface)

    async def get_firmware_update_info(self) -> Optional[FirmwareRecord]:
        """Read Optional[FirmwareRecord]; see the model reference for fields and limits."""
        return await self._optional(FirmwareRecord, "_read_firmware_update_info")

    async def get_client_traffic_page(self, page: int = 1) -> ResponsePage[ClientTraffic]:
        """Read ResponsePage[ClientTraffic]; see the model reference for fields and limits."""
        data = await self._read_client_traffic_page(page)
        return self._convert(
            data, lambda value: ResponsePage(value, "devlist", "devcnt", ClientTraffic)
        )

    async def get_mesh_device_page(
        self, node_id: str, page: int = 1
    ) -> ResponsePage[FirmwareRecord]:
        """Read ResponsePage[FirmwareRecord]; see the model reference for fields and limits."""
        data = await self._read_mesh_device_page(node_id, page)
        return self._convert(
            data, lambda value: ResponsePage(value, "devlist", "devcnt", FirmwareRecord)
        )

    async def get_vpn_connection_page(
        self, vpn_type: str, page: int = 1
    ) -> ResponsePage[FirmwareRecord]:
        """Read ResponsePage[FirmwareRecord]; see the model reference for fields and limits."""
        data = await self._read_vpn_connection_page(vpn_type, page)
        return self._convert(
            data, lambda value: ResponsePage(value, "connection_list", "total_cnt", FirmwareRecord)
        )

    async def get_system_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_system_config")

    async def get_ipv6_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_ipv6_config")

    async def get_default_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_default_config")

    async def get_ddns_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_ddns_config")

    async def get_connectivity_check_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_connectivity_check_config")

    async def get_auto_reboot_config(self) -> Optional[Configuration]:
        """Read Optional[Configuration]; see the model reference for fields and limits."""
        return await self._optional(Configuration, "_read_auto_reboot_config")

    async def get_iptv_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_iptv_config")

    async def get_easymesh_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_easymesh_config")

    async def get_multi_ssid_config(self, section: str) -> Optional[WirelessInterface]:
        """Read Optional[WirelessInterface]; see the model reference for fields and limits."""
        value = await self._read_multi_ssid_config(section)
        return (
            None
            if value is None
            else self._convert(
                value, lambda data: WirelessInterface.from_api_response(section, data)
            )
        )

    async def get_parental_control_config(self, group: Optional[str] = None) -> List[ParentalGroup]:
        """Read List[ParentalGroup]; see the model reference for fields and limits."""
        return await self._records(ParentalGroup, "_read_parental_control_config", group)

    async def get_vpn_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_vpn_config")

    async def get_vpn_profiles(self, category: str = "clients") -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_vpn_profiles", category)

    async def get_vpn_client_config(self, client_id: str) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_vpn_client_config", client_id)

    async def get_dhcp_config(self) -> ConfigurationSections:
        """Read ConfigurationSections; see the model reference for fields and limits."""
        return await self._record(ConfigurationSections, "_read_dhcp_config")

    async def get_wireless_config(self) -> ConfigurationSections:
        """Read ConfigurationSections; see the model reference for fields and limits."""
        return await self._record(ConfigurationSections, "_read_wireless_config")

    async def get_cellular_status(self, interface: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return await self._record(FirmwareRecord, "_read_cellular_status", interface)

    async def get_cellular_data_config(self, interface: str) -> List[Configuration]:
        """Read List[Configuration]; see the model reference for fields and limits."""
        return await self._records(Configuration, "_read_cellular_data_config", interface)

    async def get_cellular_statistics(self, interface: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return await self._record(FirmwareRecord, "_read_cellular_statistics", interface)

    async def get_adshield_providers(self) -> ProviderCatalog:
        """Read ProviderCatalog; see the model reference for fields and limits."""
        return await self._record(ProviderCatalog, "_read_adshield_providers")

    async def get_adshield_config(self) -> Configuration:
        """Read Configuration; see the model reference for fields and limits."""
        return await self._record(Configuration, "_read_adshield_config")

    async def get_adshield_status(self, provider: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return await self._record(FirmwareRecord, "_read_adshield_status", provider)

    async def get_adshield_stats(self, provider: str) -> FirmwareRecord:
        """Read FirmwareRecord; see the model reference for fields and limits."""
        return await self._record(FirmwareRecord, "_read_adshield_stats", provider)
