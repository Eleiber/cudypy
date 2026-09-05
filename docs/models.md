# Response models

Ordinary `router.get_*()` calls return response models. This reference describes
their types, fields, snapshot behavior and access to firmware-specific data.

This layer performs **response deserialization and model mapping**: JSON objects
become Python response models. It is not an ORM, a database persistence layer,
or a new asynchronous transport.

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
[read contracts](feature-reads.md). This API does not add new firmware endpoints
or hardware verification.

## Models and coverage

Every public `CudyRouter.get_*` is covered by the model API inventory. Tests
check getter coverage and parameter/default compatibility. Mutation methods
remain explicitly separate; model reads never invoke them.

| Getter(s), with `get_` prefix | Returned model |
| --- | --- |
| `system_info`, `system_status` | `SystemStatus`, including `ResourceUsage` children |
| `network_status`, `interface_status` | `InterfaceStatus` |
| `devices`, `online_devices`, `wifi_devices`, `ethernet_devices` | List of existing `Device` models |
| `device_by_mac`, `device_by_ip`, `device_by_hostname`, `client_info` | Optional `Device` |
| `ethernet_status`, `ethernet_ports` | List of `EthernetPort` |
| `lan_config`, `client_rate_limit`, `wireless_interface` | Existing `LanConfig`, optional `RateLimit`, optional `WirelessInterface` |
| `multi_ssid_config` | Optional `WirelessInterface` for the selected section |
| `client_names`, `work_modes` | Lists of `ClientName`, `WorkMode` |
| `wifi_scan_results`, `wds_status` | Optional list of `AccessPoint`, optional `WdsStatus` |
| `parental_control_config`, `adshield_providers` | List of `ParentalGroup`, `ProviderCatalog` |
| `client_traffic_page` | `ResponsePage[ClientTraffic]` |
| `mesh_device_page`, `vpn_connection_page` | `ResponsePage[FirmwareRecord]` |
| `dhcp_config`, `wireless_config` | `ConfigurationSections` |
| `system_config`, `ipv6_config`, `default_config`, `ddns_config`, `connectivity_check_config`, `iptv_config`, `easymesh_config`, `vpn_config`, `vpn_profiles`, `vpn_client_config`, `adshield_config` | `Configuration` |
| `auto_reboot_config` | Optional `Configuration` |
| `wifi_schedule`, `client_internet_schedule`, `cellular_data_config` | Lists of `Configuration` |
| `wifi_frequencies`, `cellular_status`, `cellular_statistics`, `adshield_status`, `adshield_stats` | `FirmwareRecord` |
| `legacy_devices`, `firmware_update_info` | List of `FirmwareRecord`, optional `FirmwareRecord` |
| `supported_features`, `mesh_clients`, `traffic_stats`, `vpn_status`, `qos_config` | `ResponseValue`: recursively mapped record/tuple/scalar/null, preserving firmware-specific top-level shapes |
| `wps_status`, `firmware_check_status`, `apply_status` | Optional string; no guessed enum or success interpretation |
| `online_interfaces`, `multi_ssid_interfaces` | Lists of strings |

Scalar results stay scalars: wrapping an interface name or an unknown state
string in a class adds no useful parsing. Null and empty results retain the
existing getter's contract.

## Known fields versus firmware extensions

This is full **getter coverage**, not full **field-schema coverage**.
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
records, **not fully schema-validated domain models**. For example, a synthetic
response `{"provider": {"enabled": "0"}}` allows `record.provider.enabled`, but
the value stays the string `"0"`; generic mapping never guesses boolean semantics.
Further field-specific models can be added as contracts are verified.

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

Access documented fields through attributes, such as
`router.get_system_info().model`. For original response keys use
`router.get_system_info().raw["model"]`. Lists of models can be exported with
`[item.raw for item in result]`. Scalars and null retain their documented behavior.

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
