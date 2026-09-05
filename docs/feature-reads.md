# Additional status and configuration reads

These methods use the same configurable `CudyRouter` connection and never
submit configuration changes. They may raise `CudyUnsupportedError` when the
firmware returns -32601; other RPC failures remain `CudyAPIError` with `code`.
Do not confuse absent configuration with unavailable functionality.

| Python method | RPC and parameters | Result |
| --- | --- | --- |
| `get_work_modes()` | `conf.get_workmodes`, `[]` | List of mode/name dictionaries; available modes, not the active mode |
| `get_wifi_schedule()` | `wifi.get_schedule`, `[]` | Schedule dictionaries; null becomes an empty list |
| `get_wds_status(interface=None)` | `wifi.get_wds_status`, `[]` or `[interface]` | Raw dictionary or `None` |
| `get_wps_status()` | `wifi.get_wps_status`, `[]` | Firmware status string or `None`; never starts WPS |
| `get_vpn_status()` | `vpn.get_status`, `[]` | Raw firmware result |
| `get_client_info(mac)` | `devices.get_devinfo`, `[mac]` | `Device` or `None`; a direct read, not a full-list search |
| `get_client_rate_limit(mac)` | `conf.get_rate_limit`, `[mac]` | `RateLimit` or `None` for no configuration |
| `get_client_internet_schedule(mac)` | `conf.get_internet_schedule`, `[mac]` | List of schedule dictionaries; null becomes empty |
| `get_ethernet_ports()` | `eth.getstatus`, `[]` | List of `EthernetPort` |
| `get_lan_config()` | `conf.get_all`, `["network", "lan"]` | `LanConfig`: configured values, not runtime status |
| `get_dhcp_config()` | `conf.get_all`, `["dhcp"]` | Raw section dictionary |
| `get_wireless_config()` | `conf.get_all`, `["wireless"]` | Raw section dictionary; no scan or WPS activation |
| `get_vpn_config()` | `conf.get_all`, `["vpn", "config"]` | Raw configuration; not tunnel connectivity |
| `get_mesh_device_page(node_id, page=1)` | `mesh.get_devices`, `[node_id, start, end]` | Raw object retaining `devlist` and optional `devcnt`; inclusive pages of 100 |
| `get_system_status()` | `system.info`, `[]` | `SystemStatus`; original raw reader remains available |
| `get_interface_status(interface="wan")` | `net.iface_status`, `[interface]` | `InterfaceStatus`; original raw reader remains available |

Client methods accept colon, hyphen or unseparated MAC addresses and normalize
them to lowercase colon notation. Invalid identifiers fail before any request.
The existing raw `get_ethernet_status()` remains available.

`LanConfig` exposes `protocol`, `ip_address`, `netmask`, `gateway` and
`interface`, retaining all original fields in `raw` (excluded from its repr).
Missing fields remain `None`; a configured address is not proof of the active
address when DHCP is in use. Use `get_network_status("lan")` for runtime status
where supported. Null/non-object configuration results raise `CudyAPIError`.

DHCP and wireless dictionaries preserve unknown section names, including
firmware-generated sections. They can contain private identifiers and Wi-Fi
passwords: do not log, print or save their raw contents. These reads do not
perform configuration writes. No hardcoded radio names or IP addresses are
used to select sections.

`SystemStatus` exposes optional `model`, `firmware`, `board_name`, and
`uptime_seconds`. A missing model is not guessed from firmware or an IP address.
`InterfaceStatus` exposes optional `is_up`, `protocol`, `interface`,
`ip_address`, `gateway`, `uptime_seconds`, `rx_bytes`, and `tx_bytes`. `is_up`
is a firmware interface observation, not proof of Internet reachability.
Both retain all fields in `raw`, excluded from repr. Unknown addresses and
counters stay unknown rather than becoming zero or empty strings.

Mesh page callers must provide a known node identifier, not a guessed MAC or
address. The response retains total-count metadata for caller-managed pagination;
one page is not advertised as the full client list. This helper is source-backed
and offline-tested; node-specific hardware compatibility remains unverified.

`EthernetPort` exposes `port`, `label`, `link_up`, `speed_mbps`, `full_duplex`,
`auto_negotiation`, `tx_bytes` and `rx_bytes`. Missing values remain `None`;
`auto` and `autoneg` map to the same field. Counter direction is relative to the
router port. Its `raw` dictionary preserves unknown firmware fields.

`RateLimit.download_mbps` and `upload_mbps` are `Decimal` values, avoiding loss
of fractional limits. Missing fields remain `None`; an explicit zero remains
zero. A null RPC result produces no `RateLimit` instance. The app uses Mbps
labels and sends decimal strings directly; this differs from client traffic
rates in bytes/s. Invalid, negative and non-finite limits are rejected.

## Compatibility and verification

### Additional configuration reads

All of these methods send an empty positional argument list (`[]`). They are
source-backed and offline-tested, not yet hardware-verified.

| Helper | RPC | Result |
| --- | --- | --- |
| `get_system_config()` | `conf.get_system` | Raw system settings object, distinct from runtime status |
| `get_ipv6_config()` | `conf.get_ipv6` | Raw IPv6 settings object |
| `get_default_config()` | `conf.get_defaults` | Raw firmware defaults object; does not restore defaults |
| `get_ddns_config()` | `conf.get_ddns` | Raw DDNS object, potentially including account credentials |
| `get_connectivity_check_config()` | `conf.get_pingcheck` | Raw check settings object; does not initiate a check |
| `get_auto_reboot_config()` | `conf.get_autoreboot` | Raw scheduling object; does not schedule or trigger reboot |
| `get_qos_config()` | `conf.get_qos` | Firmware-defined JSON, including possible null |

Object readers preserve empty objects and all nested/unknown fields; null and
non-object responses raise `CudyAPIError`. QoS is intentionally unconstrained:
the app consumes a generic JSON value, not a confirmed fixed model. No helper
coerces string flags, times, addresses or rates into guessed types or units.
Do not log these results; DDNS and defaults can contain secrets. Unsupported
methods raise `CudyUnsupportedError`, never a fabricated empty configuration.

See the [coverage checklist](read-coverage.md) for implemented and missing RPCs.

These request structures were derived from the Cudy app's status and
configuration workflows. Availability varies by firmware; see
[compatibility](compatibility.md). Unsupported methods remain distinct from
empty or absent configuration.

The contributor tool `python -m tools.verify_read_only` performs named status
reads. Use `--include-config` for configuration reads and `--client-mac` or
`--mesh-node` for known targets. It reports shapes rather than private values.
See [contributor instructions](../CONTRIBUTING.md).
