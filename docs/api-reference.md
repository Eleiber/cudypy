# API reference

`CudyRouter` and `AsyncCudyRouter` expose the same named operations. The
signatures and return types below apply to both. `CudyRouter` calls are
synchronous; every `AsyncCudyRouter` operation is a coroutine that requires
`await`. Both use the same [response models](models.md) and exceptions.

## Construct a client

### `CudyRouter(base_url, password=None, *, auth_token=None, salt=None, timeout=10)`
### `AsyncCudyRouter(base_url, password=None, *, auth_token=None, salt=None, timeout=10)`

`base_url` is the router's HTTP(S) origin without a path or credentials. Supply
a password or an existing session token. The token is used first when both are
given. `salt` skips mDNS discovery for password login. `timeout` is the
per-request limit in seconds. Construction does not connect. Install the async
client with `python -m pip install -e ".[async]"` from this repository.

```python
import asyncio
import os
from cudypy import AsyncCudyRouter

async def main():
    async with AsyncCudyRouter(
        os.environ["CUDY_ROUTER_URL"],
        password=os.environ["CUDY_ROUTER_PASSWORD"],
    ) as router:
        system, wan, devices = await asyncio.gather(
            router.get_system_status(),
            router.get_interface_status("wan"),
            router.get_devices(),
        )
        print(system.model, wan.is_up, len(devices))

asyncio.run(main())
```

Use `with CudyRouter(...) as router:` and omit `await` for synchronous code.
Closing either client releases local resources and discards local credentials.

## Authentication and RPC transport

### `authenticate(force=False) -> bool`

Use an existing token or log in with the configured password. `force=True`
requires a password and requests a fresh login. A rejected password login
returns `False`; an authenticated read raises `CudyAuthError` if login fails.

### `call_api(method, params=None, retry_auth=True) -> dict`

Send an RPC method and return the complete envelope, including `result`.
`params` must be a positional list or `None`. Arbitrary methods can change
router state. A known read may retry once after authentication rejection when
a password is available; writes and transport failures are not replayed.

### `close() -> None`

Close the HTTP session. Context managers call this automatically. The async
variant uses `async with` and `await router.close()`.

## Named operations

Return types show response models rather than raw wire dictionaries. Models
are detached snapshots; `.raw` exports a copy of their original response.
`call_api()` remains available when the original RPC envelope is required.
Firmware-specific availability is recorded in [compatibility](compatibility.md).

### Status and clients

#### `get_system_info() -> SystemStatus`

Return a [system snapshot](#systemstatus), including resource counters and
router-reported identity. `get_system_status()` is an alias.

#### `get_system_status() -> SystemStatus`

Read a system snapshot; alias of get_system_info.

#### `get_network_status(interface: str='wan') -> InterfaceStatus`

Return the selected interface's [runtime status](#interfacestatus). The
interface name must be nonempty. `get_interface_status()` is an alias.

#### `get_interface_status(interface: str='wan') -> InterfaceStatus`

Read an interface snapshot; alias of get_network_status.

#### `get_devices() -> List[Device]`

Return parsed [client records](#device), fetching additional pages when the
router reports more clients than its first response contains. Malformed or
inconsistent pagination raises `CudyAPIError`.

#### `get_client_info(mac: str) -> Optional[Device]`

Read one client's details directly, without downloading the full list.

#### `get_online_devices() -> List[Device]`

Get clients passing the legacy inactivity-below-30 heuristic.

#### `get_wifi_devices() -> List[Device]`

Get list of devices connected via WiFi.

#### `get_ethernet_devices() -> List[Device]`

Get list of devices connected via Ethernet.

#### `get_device_by_mac(mac: str) -> Optional[Device]`

Find a device by its MAC address.

#### `get_device_by_ip(ip: str) -> Optional[Device]`

Find a device by its IP address.

#### `get_device_by_hostname(hostname: str, case_sensitive: bool=False) -> Optional[Device]`

Find a device by its hostname.

#### `get_client_names() -> List[ClientName]`

Read List[ClientName]; see the model reference for fields and limits.

#### `get_client_traffic_page(page: int=1) -> ResponsePage[ClientTraffic]`

Read one traffic page of up to 100 clients, retaining raw metadata.

#### `get_client_rate_limit(mac: str) -> Optional[RateLimit]`

Read a client's configured Mbps limits; null means no configuration.

#### `get_client_internet_schedule(mac: str) -> List[Configuration]`

Read List[Configuration]; see the model reference for fields and limits.

### Network and wireless

#### `get_supported_features() -> ResponseValue`

Return firmware feature declarations without guessing model capabilities.

#### `get_ethernet_status() -> List[EthernetPort]`

Read List[EthernetPort]; see the model reference for fields and limits.

#### `get_ethernet_ports() -> List[EthernetPort]`

Read typed port status, normalizing firmware auto/autoneg variants.

#### `get_traffic_stats() -> ResponseValue`

Return raw network traffic statistics.

#### `get_online_interfaces() -> List[str]`

Read firmware-reported online interface names, without a reachability test.

#### `get_work_modes() -> List[WorkMode]`

Read List[WorkMode]; see the model reference for fields and limits.

#### `get_wifi_schedule() -> List[Configuration]`

Read List[Configuration]; see the model reference for fields and limits.

#### `get_wds_status(interface: Optional[str]=None) -> Optional[WdsStatus]`

Read Optional[WdsStatus]; see the model reference for fields and limits.

#### `get_wps_status() -> Optional[str]`

Read the firmware WPS state string; this does not start WPS.

#### `get_wifi_frequencies() -> FirmwareRecord`

Read FirmwareRecord; see the model reference for fields and limits.

#### `get_wifi_scan_results(interface: Optional[str]=None) -> Optional[List[AccessPoint]]`

Read existing AP results once; never trigger or wait for a scan.

#### `get_lan_config() -> LanConfig`

Read configured LAN fields; this is not live interface status.

#### `get_dhcp_config() -> ConfigurationSections`

Read ConfigurationSections; see the model reference for fields and limits.

#### `get_wireless_config() -> ConfigurationSections`

Read ConfigurationSections; see the model reference for fields and limits.

#### `get_wireless_interface(section: str) -> Optional[WirelessInterface]`

Read one selected wireless section; absent sections return None.

### Mesh, VPN, and services

#### `get_mesh_clients() -> ResponseValue`

Return raw mesh client data; availability depends on firmware and mode.

#### `get_mesh_device_page(node_id: str, page: int=1) -> ResponsePage[FirmwareRecord]`

Read a mesh node's client page (up to 100), retaining devcnt metadata.

#### `get_vpn_status() -> ResponseValue`

Read firmware-specific VPN status; older firmware may reject the method.

#### `get_vpn_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_vpn_profiles(category: str='clients') -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_vpn_client_config(client_id: str) -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_vpn_connection_page(vpn_type: str, page: int=1) -> ResponsePage[FirmwareRecord]`

Read one connection page of up to 100 entries; not historical usage.

#### `get_iptv_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_easymesh_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_multi_ssid_interfaces() -> List[str]`

Read firmware multi-SSID section identifiers; null means no entries.

#### `get_multi_ssid_config(section: str) -> Optional[WirelessInterface]`

Read one known multi-SSID section; null remains absent/unknown.

#### `get_parental_control_config(group: Optional[str]=None) -> List[ParentalGroup]`

Read List[ParentalGroup]; see the model reference for fields and limits.

### System and provider configuration

#### `get_system_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_ipv6_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_default_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_ddns_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_connectivity_check_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_auto_reboot_config() -> Optional[Configuration]`

Read Optional[Configuration]; see the model reference for fields and limits.

#### `get_qos_config() -> ResponseValue`

Read firmware-defined QoS JSON; preserve null and all result shapes.

#### `get_cellular_status(interface: str) -> FirmwareRecord`

Read FirmwareRecord; see the model reference for fields and limits.

#### `get_cellular_data_config(interface: str) -> List[Configuration]`

Read List[Configuration]; see the model reference for fields and limits.

#### `get_cellular_statistics(interface: str) -> FirmwareRecord`

Read FirmwareRecord; see the model reference for fields and limits.

#### `get_adshield_providers() -> ProviderCatalog`

Read ProviderCatalog; see the model reference for fields and limits.

#### `get_adshield_config() -> Configuration`

Read Configuration; see the model reference for fields and limits.

#### `get_adshield_status(provider: str) -> FirmwareRecord`

Read FirmwareRecord; see the model reference for fields and limits.

#### `get_adshield_stats(provider: str) -> FirmwareRecord`

Read FirmwareRecord; see the model reference for fields and limits.

#### `get_firmware_update_info() -> Optional[FirmwareRecord]`

Read Optional[FirmwareRecord]; see the model reference for fields and limits.

#### `get_firmware_check_status(device_id: str) -> Optional[str]`

Read an existing firmware-check state once for a known target ID.

#### `get_apply_status() -> Optional[str]`

Read configuration-application state once; never apply or poll changes.

### Configuration writes

#### `set_wifi_config(config: Dict[str, Any]) -> Any`

Submit a firmware-specific Wi-Fi configuration object; never replay.

#### `set_client_name(mac: str, name: str, *, device_type: str='other', brand: str='undefined') -> Any`

Change client name and metadata. Defaults reset type/brand to app defaults.

#### `set_client_internet_blocked(mac: str, blocked: bool, *, name: str='') -> Any`

Block/unblock a client's Internet access (a configuration write).

#### `set_client_rate_limit(mac: str, *, download_mbps: Any, upload_mbps: Any) -> Any`

Write both Mbps limits, with up to three decimal places; never replay.

#### `clear_client_rate_limit(mac: str) -> Any`

Remove the client's rate-limit configuration; never automatically replay.

#### `reboot() -> bool`

Reboot the router.

## Return models and fields

The fields below are declared Python attributes. `Optional` means the field is
`None` when the router omits it. Every model also exposes `.raw`, a copy of its
source object. Values and extra keys inside `.raw` vary by firmware. See
[response models](models.md) for snapshot and dynamic-field behavior.

### `SystemStatus`

Returned by `get_system_info()` and `get_system_status()`.

| Field | Type | Meaning |
| --- | --- | --- |
| `model`, `firmware`, `board_name` | `Optional[str]` | Router-reported identity and firmware text. |
| `uptime_seconds` | `Optional[int]` | Reported uptime. |
| `memory`, `swap`, `root`, `tmp` | `Optional[ResourceUsage]` | Reported resource counters; each has its own `.raw`. |
| `cpu_usage` | `Optional[float]` | Router-reported nonnegative CPU value; fractional values are retained. |
| `load` | `Optional[tuple[int, ...]]` | Native load values, without unit conversion. |
| `processor`, `revision`, `rom`, `country`, `device_type` | `Optional[str]` | Additional reported system fields. |
| `serial_number`, `mac_address`, `lan_ip` | `Optional[str]` | Router identifiers and LAN address; excluded from repr. |
| `timestamp`, `localtime` | `Optional[int]` | Router-reported time values. |
| `raw` | `dict` | Copy of the complete `system.info` result. |

`ResourceUsage` has `total`, `used`, `free`, `available`, `shared`, `cached`,
and `buffered` (`int | None`), plus `.raw`. The resource counters retain native
firmware units; missing counters are not calculated from others.

### `InterfaceStatus`

Returned by `get_network_status()` and `get_interface_status()`.

| Field | Type | Meaning |
| --- | --- | --- |
| `is_up` | `Optional[bool]` | Reported runtime link state. |
| `protocol`, `interface` | `Optional[str]` | Protocol and interface name. |
| `ip_address`, `gateway` | `Optional[str]` | Reported runtime addresses. |
| `uptime_seconds`, `rx_bytes`, `tx_bytes` | `Optional[int]` | Native runtime counters. |
| `raw` | `dict` | Copy of the complete interface response. |

### `Device`

Returned by `get_devices()`, its filters and lookups, and `get_client_info()`.

| Field | Type | Meaning |
| --- | --- | --- |
| `mac_address`, `ip_address` | `str` | Reported client addresses; an absent address becomes `"unknown"`. |
| `hostname`, `device_name` | `Optional[str]` | Reported client names. |
| `connection_type` | `Optional[str]` | Parsed `"wifi"` or `"ethernet"` when identifiable. |
| `interface`, `raw_iface` | `Optional[str]` | Reported interface names. |
| `signal_strength` | `Optional[int]` | Wi-Fi signal in dBm when available. |
| `bandwidth_up`, `bandwidth_down` | `Optional[int]` | Reported byte rates per second. |
| `bytes_received`, `bytes_sent` | `Optional[int]` | Reported client counters; accounting viewpoint remains unverified. |
| `reported_upbytes`, `reported_downbytes` | `Optional[int]` | Additional native byte counters. |
| `inactive_time`, `reported_online_seconds` | `Optional[int]` | Router-reported activity and elapsed time. |
| `is_online` | `Optional[bool]` | `inactive_time < 30` heuristic, not a reachability test. |
| `connected_since` | `Optional[datetime]` | Local estimate derived from reported elapsed seconds. |
| `has_internet`, `is_vpn` | `bool` | Parsed client flags. |
| `raw` | `dict` | Copy of the client record. |

Computed properties include `recently_active`, `reported_inbytes`,
`reported_outbytes`, `connection_time`, `formatted_bandwidth_up`,
`formatted_bandwidth_down`, `formatted_bytes_received`, and
`formatted_bytes_sent`.

### Other typed snapshots

| Model | Declared fields |
| --- | --- |
| `EthernetPort` | `port: Optional[int]`, `label: Optional[str]`, `link_up: Optional[bool]`, `speed_mbps: Optional[int]`, `full_duplex: Optional[bool]`, `auto_negotiation: Optional[bool]`, `tx_bytes: Optional[int]`, `rx_bytes: Optional[int]`, `raw: dict`. |
| `LanConfig` | `protocol`, `ip_address`, `netmask`, `gateway`, `interface` (`Optional[str]`), `raw: dict`. These are configured LAN values, not runtime status. |
| `WirelessInterface` | `section: str`; `ssid`, `encryption`, `device`, `mode` (`Optional[str]`); `disabled`, `hidden` (`Optional[bool]`); `raw: dict`. The raw section may include credentials. |
| `RateLimit` | `download_mbps`, `upload_mbps` (`Optional[Decimal]`), `raw: dict`. |

### Firmware records and pages

`FirmwareRecord` is a read-only mapping for a router-defined object. It has
`.raw`, supports `record["wire_key"]`, and allows attribute access for keys
that do not collide with Python attributes. It has no fixed field list.
`Configuration` and `ConfigurationSections` retain that dynamic schema;
`ConfigurationSections.section(name)` returns a `Configuration` or `None`.

The record subclasses below add these validated fields. All other router keys
remain available through mapping access and `.raw`.

| Model | Declared fields |
| --- | --- |
| `ClientName` | `mac_address: Optional[str]`, `name: Optional[str]`. |
| `WorkMode` | `mode: Optional[str]`, `name: Optional[str]`. |
| `ClientTraffic` | `mac_address: Optional[str]`; `upload_bytes_per_second`, `download_bytes_per_second`, `reported_inbytes`, `reported_outbytes`, `reported_upbytes`, `reported_downbytes` (`Optional[int]`). Counter direction and reset periods are unverified. |
| `AccessPoint` | `ssid: Optional[str]`. |
| `WdsStatus` | `is_up: Optional[bool]`. |
| `ParentalGroup` | `name: Optional[str]`. |
| `ProviderCatalog` | `providers: Optional[tuple[str, ...]]`. |

`ResponsePage[T]` exposes `entries: tuple[T, ...]`,
`total_count: int | None`, and `.raw`. A page is one explicit router read;
accessing its entries does not fetch subsequent pages.

`ResponseValue` is used where firmware may return an object, array, scalar or
null. Objects become `FirmwareRecord`, arrays become tuples, and scalar values
remain scalars. These methods have no fixed top-level field schema.

## Errors

`CudyAPIError` covers transport, RPC and response-shape failures. Its `.code`
contains a numeric RPC code when supplied by the router. `CudyAuthError`,
`CudyDiscoveryError` and `CudyUnsupportedError` are subclasses. Invalid local
arguments may raise `ValueError` or `TypeError`. See the [protocol contract](protocol.md)
and [read contracts](feature-reads.md) for argument and response variants.
