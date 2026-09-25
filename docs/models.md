# Response models

Ordinary `router.get_*()` calls return response models. This reference describes
their types, fields, snapshot behavior and access to firmware-specific data.

Both the synchronous and async clients return these models. A model contains
the values from one router response. Call the getter again to read newer values.

```python
import os
from cudypy import CudyRouter

with CudyRouter(
    os.environ["CUDY_ROUTER_URL"],
    auth_token=os.environ["CUDY_ROUTER_TOKEN"],
) as router:
    status = router.get_system_info()
    print(status.model, status.uptime_seconds)

    for mode in router.get_work_modes():
        print(mode.mode, mode.name)

    page = router.get_client_traffic_page(page=1)
    print(page.total_count)
    for client in page.entries:
        print(client.download_bytes_per_second)
```

These are separate reads; optional methods can be unsupported on a firmware.
See [compatibility](compatibility.md), [read coverage](read-coverage.md) and
[read contracts](feature-reads.md).

## Models and coverage

Each named getter exists on both clients; async calls require `await`.

- `SystemStatus`: `get_system_info()`, `get_system_status()`. Resource fields
  contain `ResourceUsage` snapshots.
- `InterfaceStatus`: `get_network_status()`, `get_interface_status()`.
- `list[Device]`: `get_devices()`, `get_online_devices()`, `get_wifi_devices()`,
  `get_ethernet_devices()`.
- `Device | None`: `get_client_info()`, `get_device_by_mac()`,
  `get_device_by_ip()`, `get_device_by_hostname()`.
- `list[EthernetPort]`: `get_ethernet_status()`, `get_ethernet_ports()`.
- `LanConfig`: `get_lan_config()`. `RateLimit | None`: `get_client_rate_limit()`.
- `WirelessInterface | None`: `get_wireless_interface()`,
  `get_multi_ssid_config()`.
- `list[ClientName]` and `list[WorkMode]`: `get_client_names()` and
  `get_work_modes()`, respectively.
- `list[AccessPoint] | None`: `get_wifi_scan_results()`.
  `WdsStatus | None`: `get_wds_status()`.
- `list[ParentalGroup]`: `get_parental_control_config()`.
  `ProviderCatalog`: `get_adshield_providers()`.
- `ResponsePage[ClientTraffic]`: `get_client_traffic_page()`.
- `ResponsePage[FirmwareRecord]`: `get_mesh_device_page()` and
  `get_vpn_connection_page()`.
- `ConfigurationSections`: `get_dhcp_config()`, `get_wireless_config()`.
- `Configuration`: `get_system_config()`, `get_ipv6_config()`,
  `get_default_config()`, `get_ddns_config()`, `get_connectivity_check_config()`.
- `Configuration`: `get_iptv_config()`, `get_easymesh_config()`,
  `get_vpn_config()`, `get_vpn_profiles()`, `get_vpn_client_config()`,
  `get_adshield_config()`.
- `Configuration | None`: `get_auto_reboot_config()`.
- `list[Configuration]`: `get_wifi_schedule()`,
  `get_client_internet_schedule()`, `get_cellular_data_config()`.
- `FirmwareRecord`: `get_wifi_frequencies()`, `get_cellular_status()`,
  `get_cellular_statistics()`, `get_adshield_status()`, `get_adshield_stats()`.
- `FirmwareRecord | None`: `get_firmware_update_info()`.
- `ResponseValue`: `get_supported_features()`, `get_mesh_clients()`,
  `get_traffic_stats()`, `get_vpn_status()`, `get_qos_config()`.
- `str | None`: `get_wps_status()`, `get_firmware_check_status()`,
  `get_apply_status()`.
- `list[str]`: `get_online_interfaces()`, `get_multi_ssid_interfaces()`.

Scalar results stay scalars: wrapping an interface name or an unknown state
string in a class adds no useful parsing. Null and empty results retain the
existing getter's contract.

## Known fields versus firmware extensions

Typed domain models provide declared properties with type
annotations. `ClientName` exposes `name` and `mac_address`; `WorkMode` exposes
`mode` and `name`; `AccessPoint` exposes `ssid`; `WdsStatus` exposes `is_up`;
`ParentalGroup` exposes `name`; `ProviderCatalog` exposes optional `providers`.
Other fields remain recursively accessible, without inferred meanings.

`ClientTraffic` exposes optional `mac_address`, `upload_bytes_per_second`,
`download_bytes_per_second`, and `reported_inbytes`, `reported_outbytes`,
`reported_upbytes`, `reported_downbytes`. Counters do not establish accounting
direction or reset periods. Known numeric properties accept nonnegative integers
or integer strings, not booleans/fractions. Known missing properties are `None`.
Malformed declared fields raise `CudyAPIError` before an object getter returns.
Direct property access on manually constructed records can raise `ValueError`.

Unverified configuration, provider, cellular and other nested schemas use
`FirmwareRecord` or its configuration subclasses. These are flexible structured
records with firmware-defined keys. For example:

```python
from cudypy import FirmwareRecord

record = FirmwareRecord({"provider": {"enabled": "0"}})
assert record.provider.enabled == "0"
```

The value stays a string; generic mapping does not infer a boolean.

Dynamic attributes raise `AttributeError` when absent. Use `.get("field")` for
optional unknown keys or `"field" in record` to distinguish absence from null.
Indexing always accesses wire keys, including names that collide with methods
or properties: `record["items"]`, `record["raw"]`, `record["future-field"]`.
Nested arrays become tuples; object-list getters return lists of models.

Section names are firmware-defined. Use `sections.section(selected_name)` for a
`Configuration` or `None` if absent. This is a local lookup, not another request.
The wireless section collection includes radio sections as well as interfaces;
use `get_wireless_interface(section)` when the selected interface schema is wanted.

## Snapshots, privacy and lifecycle

Records are read-only views of detached response copies. Attribute access,
iteration, section lookup and page-entry access never perform network requests.
Explicitly call a getter again to refresh. Pages expose `entries` and
`total_count`; they never auto-fetch remaining pages or represent usage history.
The raw page wrapper, including unrecognized metadata, remains available via `.raw`.

Record `.raw` exports a fresh deep copy in the original wire structure. It can
contain passwords, keys and device inventories. Record reprs redact all
payload values, including nested values, but explicit field access, iteration
and raw serialization are not privacy filters. Existing models keep their
documented serialization behavior. Do not feed a read model's raw data into a
setter: read and write schemas are not interchangeable.

Unsupported/authentication errors propagate unchanged. No extra login, fallback,
scan, retry, provider call or mutation is introduced by model conversion. Existing
provider reads can still contact external services and retain their no-replay
rules. Closing the router prevents further reads.
Do not share the owning client across concurrent threads.

## Accessing original response data

With an existing synchronous `router`, access documented fields through
attributes and original response keys through `.raw`:

```python
status = router.get_system_info()
model = status.model
wire_model = status.raw["model"]
client_records = [item.raw for item in router.get_devices()]
```

Scalars and null retain their documented behavior.

For an entirely unparsed response use the low-level escape hatch:

```python
raw = router.call_api("system.info")["result"]
```

`call_api()` returns the RPC envelope and can invoke mutations. Do not use
it to probe unknown operations. Private `_read_*` methods are implementation
details, not a supported alternative API.

`get_system_status()`, `get_interface_status()` and `get_ethernet_ports()` are
aliases for the same models as `get_system_info()`, `get_network_status()` and
`get_ethernet_status()`. Attribute access never triggers another request.
