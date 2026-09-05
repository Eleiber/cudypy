# Additional status and configuration reads

Getters return models by default; see the
[model reference](models.md). Tables below list
the public Python return types; RPC shape and validation details follow each table. Original structures
remain available through model `.raw` exports or `call_api()`.

These methods use the same configurable `CudyRouter` connection and never
submit configuration changes. They may raise `CudyUnsupportedError` when the
firmware returns -32601; other RPC failures remain `CudyAPIError` with `code`.
Do not confuse absent configuration with unavailable functionality.

| Python method | RPC and parameters | Result |
| --- | --- | --- |
| `get_work_modes()` | `conf.get_workmodes`, `[]` | List of `WorkMode`; available modes, not the active mode |
| `get_wifi_schedule()` | `wifi.get_schedule`, `[]` | List of `Configuration`; null becomes an empty list |
| `get_wds_status(interface=None)` | `wifi.get_wds_status`, `[]` or `[interface]` | `WdsStatus` or `None` |
| `get_wps_status()` | `wifi.get_wps_status`, `[]` | Firmware state string or `None`; never starts WPS |
| `get_vpn_status()` | `vpn.get_status`, `[]` | `ResponseValue`; firmware-dependent structured result |
| `get_client_info(mac)` | `devices.get_devinfo`, `[mac]` | `Device` or `None`; a direct read, not a full-list search |
| `get_client_rate_limit(mac)` | `conf.get_rate_limit`, `[mac]` | `RateLimit` or `None` for no configuration |
| `get_client_internet_schedule(mac)` | `conf.get_internet_schedule`, `[mac]` | List of `Configuration`; null becomes empty |
| `get_ethernet_ports()` | `eth.getstatus`, `[]` | List of `EthernetPort` |
| `get_lan_config()` | `conf.get_all`, `["network", "lan"]` | `LanConfig`: configured values, not runtime status |
| `get_dhcp_config()` | `conf.get_all`, `["dhcp"]` | `ConfigurationSections` |
| `get_wireless_config()` | `conf.get_all`, `["wireless"]` | `ConfigurationSections`; no scan or WPS activation |
| `get_vpn_config()` | `conf.get_all`, `["vpn", "config"]` | `Configuration`; not tunnel connectivity |
| `get_mesh_device_page(node_id, page=1)` | `mesh.get_devices`, `[node_id, start, end]` | `ResponsePage[FirmwareRecord]`; inclusive pages of 100 |
| `get_system_status()` | `system.info`, `[]` | `SystemStatus`; alias of `get_system_info()` |
| `get_interface_status(interface="wan")` | `net.iface_status`, `[interface]` | `InterfaceStatus`; alias of `get_network_status()` |

Client methods accept colon, hyphen or unseparated MAC addresses and normalize
them to lowercase colon notation. Invalid identifiers fail before any request.
`get_ethernet_status()` returns the same port models as `get_ethernet_ports()`.

`LanConfig` exposes `protocol`, `ip_address`, `netmask`, `gateway` and
`interface`, retaining all original fields in `raw` (excluded from its repr).
Missing fields remain `None`; a configured address is not proof of the active
address when DHCP is in use. Use `get_network_status("lan")` for runtime status
where supported. Null/non-object configuration results raise `CudyAPIError`.

DHCP and wireless section models preserve unknown section names, including
firmware-generated sections. They can contain private identifiers and Wi-Fi
passwords: do not log, print or save their raw contents. These reads do not
perform configuration writes. No hardcoded radio names or IP addresses are
used to select sections.

`SystemStatus` provides typed system and nested resource snapshots, described
under [typed system status](#typed-system-status).
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

### Typed system status

`get_system_status()` fetches one `system.info` response and returns a
`SystemStatus`. Attribute access is local to that snapshot; call the method
again to refresh it. `get_system_info()` returns the same model; `.raw` exports
the original dictionary and `call_api()` remains available for unparsed reads.

```python
status = router.get_system_status()
print(status.model, status.firmware, status.uptime_seconds)
if status.memory is not None:
    print(status.memory.available)  # Native units, not an automatic byte conversion.
```

The optional `memory`, `swap`, `root` and `tmp` attributes are `ResourceUsage`
objects, exported from both `cudypy` and `cudypy.models`. Each exposes `total`,
`used`, `free`, `available`, `shared`, `cached` and `buffered`. `available` accepts
the native `available` or `avail` field (the former takes precedence when both
exist). Free and available remain distinct. Missing counters are `None`, not
calculated from other counters; an empty object differs from a missing/null
resource. Zero remains zero.

System fields include `model`, `firmware`, `board_name`, `uptime_seconds`,
`processor`, `revision`, `rom`, `country`, `device_type` (native `type`),
`serial_number` (`sn`), `mac_address` (`macaddr`) and `lan_ip`.
`processor` remains firmware text, not an inferred processor count.
`cpu_usage`, `timestamp` and `localtime` are native nonnegative integers;
`load` is a tuple of native nonnegative integers, without inferred scaling,
averaging intervals or fixed length. No percentage, timestamp timezone, byte
unit or cross-resource conversion is assumed for these new fields. In
particular, memory and filesystem counters need not use the same units.

Missing fields remain `None`; malformed known fields raise `CudyAPIError` through
the router reader (`ValueError` when constructing models from responses directly).
Numeric fields accept integers and integer strings, not booleans or fractional
values. A missing model is never inferred from firmware or an address.

System and resource `.raw` dictionaries retain all source fields as independent
deep copies. Raw data and serial/MAC/IP attributes are excluded from model repr,
but direct access and dataclass serialization can still expose private data.
Do not log entire raw responses or serialized snapshots indiscriminately.

Expanded parsing is covered by synthetic fixtures representing populated newer
responses and sparse older variants; this does not establish every firmware's
field meanings or a new live hardware-validation pass.

### Legacy clients and maintenance status

| Helper | RPC / positional arguments | Result |
| --- | --- | --- |
| `get_legacy_devices()` | `devices.get_devlist`, `[]` | List of `FirmwareRecord`; null becomes `[]` |
| `get_firmware_update_info()` | `system.upgrade_fwinfo`, `[]` | `FirmwareRecord` or `None` for an empty-array response |
| `get_firmware_check_status(device_id)` | `system.upgrade_checkstatus`, `[device_id]` | Raw state string or `None` |
| `get_apply_status()` | `apply_status`, `[]` | Raw state string or `None` |

These helpers are source-backed and offline-tested. See [compatibility](compatibility.md)
for the hardware-tested forms and remaining limits.
The legacy client reader does not paginate, produce typed `Device` objects or
act as an automatic fallback when `get_devices()` fails. It retains unknown
record fields but makes no completeness guarantee beyond the returned array.

Firmware metadata is not a fresh update check and may be stale; this wrapper
exposes only the no-argument form. The check-status helper requires a known,
nonempty target ID, sent unchanged. The app uses `000000000000` for its local
target, but no target is selected automatically and no firmware support for a
particular ID is assumed. Both status readers perform one read without polling
or waiting. Unknown state strings, empty strings and null remain distinct; no
state is guessed to mean success. Empty-array firmware metadata becomes `None`
(unavailable), not a claim that firmware is current. Null and other non-object
responses are rejected. Malformed shapes raise `CudyAPIError`; unsupported RPCs remain errors.

These methods never initiate an update check, download/install firmware, apply
configuration or change timezone. They are not automatically called by the
compatibility checker. `system.zonename` is a setter in the reviewed app
workflow; use system configuration reads to inspect timezone settings.

### Cellular status, data plans and statistics

| Helper | RPC / positional arguments | Result |
| --- | --- | --- |
| `get_cellular_status(interface)` | `cellular.getstatus`, `[interface]` | `FirmwareRecord` |
| `get_cellular_data_config(interface)` | `cellular.get_data`, `[interface]` | List of `Configuration`; null becomes `[]` |
| `get_cellular_statistics(interface)` | `cellular.get_statistics`, `[interface]` | `FirmwareRecord` |

These helpers are source-backed and offline-tested, not hardware-verified.
Provide a known cellular interface: the app uses `4g`, but the library supplies
no default or automatic discovery. Nonempty text is required and passed through
unchanged; firmware determines which identifiers it supports.

Status and statistics require objects; null is not interpreted as a disconnected
modem or zero usage. Plan settings require an array of objects (or null for no
entries). Empty objects/lists and unknown nested fields remain intact. Malformed
shapes raise `CudyAPIError`; unsupported methods remain `CudyUnsupportedError`.
Native values such as `cur_traffic`, `his_traffic`, `mon_traffic`, `monthly_data`
and `start_date` are not converted or treated as verified billing history.
Counter units, reset boundaries and carrier accounting need separate verification.

Status may expose IMEI, IMSI, ICCID and cell identifiers. Plan settings may expose
phone numbers and alert configuration. Do not log raw responses. These helpers
do not enable a modem, switch SIMs, change limits, clear statistics or read SMS.

The contributor checker only performs cellular status/statistics reads when
`--cellular-interface` is supplied. Data-plan settings additionally require
`--include-config`. It reports shapes, not identifiers or private values.

### Ad-blocking providers, settings and statistics

| Helper | RPC / positional arguments | Result |
| --- | --- | --- |
| `get_adshield_providers()` | `adshield.get_providers`, `[]` | `ProviderCatalog`; retains the outer object |
| `get_adshield_config()` | `adshield.get_conf`, `[]` | `Configuration` |
| `get_adshield_status(provider)` | `adshield.get_status`, `[provider]` | `FirmwareRecord`; retains the provider wrapper |
| `get_adshield_stats(provider)` | `adshield.get_stats`, `[provider]` | `FirmwareRecord`; retains the provider wrapper |

These contracts are source-backed and offline-tested. Providers/configuration
have hardware observations; status/statistics remain unverified. See [compatibility](compatibility.md).
The app uses provider identifiers `shiild` and `adguard`. A caller must supply
nonempty provider text for status/statistics; identifiers are passed unchanged
without a fixed capability allowlist. Those requests may contact an external
provider through the router. They are made once, without automatic replay after
authentication rejection, and are not included in the compatibility checker.
The checker reads only providers/configuration with `--include-config`.

All four RPC results must be objects: empty objects are preserved, while null and
non-object responses raise `CudyAPIError`. Nested fields are recursively represented, preserving
unknown fields, provider-specific wrappers and provider error codes. A successful
RPC response can still contain a provider failure (for example an `adguard.code`
value); callers must inspect that provider result rather than assume success.
RPC-level unsupported errors remain `CudyUnsupportedError`.

Configuration/status may contain account information or credentials, and
statistics can reveal DNS usage. Do not log raw results. No counters are reset,
no aggregation period or unit is inferred, and no OAuth flow, account binding,
provider selection or dashboard session is initiated by these helpers.
Dashboard URLs, server selection and provider-device operations remain outside
this batch pending verification of their external effects.

### VPN profiles and online interfaces

| Helper | RPC / positional arguments | Result |
| --- | --- | --- |
| `get_online_interfaces()` | `net.online_interfaces`, `[]` | Raw interface-name strings; null becomes `[]` |
| `get_vpn_profiles(category="clients")` | `vpn.get_conf`, `[category]` | `Configuration`; retains the outer object |
| `get_vpn_client_config(client_id)` | `vpn.get_conf`, `["clients", client_id]` | `Configuration`; not an unwrapped client |
| `get_vpn_connection_page(vpn_type, page=1)` | `vpn.get_connection`, `[vpn_type, start, end]` | `ResponsePage[FirmwareRecord]` with entries and optional total count |

These helpers are source-backed and offline-tested; see [compatibility](compatibility.md)
for hardware-tested argument forms. Firmware-reported online interfaces are observations, not a new
reachability test. VPN configuration categories observed in the app include
`clients`, `wireguards`, `ipsecs2s` and `zerotier`; support varies by firmware.
Selectors must be nonempty strings and are sent unchanged, without assuming a
fixed firmware capability list. The selected-client helper requires a known ID.

The existing `get_vpn_config()` reads general settings through `conf.get_all`;
it is not replaced by the profile readers. Profile objects may contain private
keys, passwords and certificates. Never log their raw contents. The verifier
only requests the default profile category when `--include-config` is supplied;
it does not guess client IDs or VPN types for further reads.

Connection pages contain at most 100 requested entries using inclusive bounds
(page 2 sends `[vpn_type, 101, 200]`). One page is not the complete connection
list or historical traffic. `connection_list` must be an array of objects;
non-null `total_cnt` must be a nonnegative integer. Missing counts remain
missing. Handshake values and unknown fields are preserved without semantic conversion; no timestamp units,
reachability or freshness are inferred. Pages may change between requests.
Profile results must be objects; null is not converted to empty configuration.
Wrong shapes raise `CudyAPIError`; unsupported methods remain explicit errors.

These helpers do not export profiles, generate keys, connect/disconnect tunnels
or run `net.online_check`. Public-IP lookup and active-check/export behavior
remain outside this passive-read batch pending further verification.

### IPTV, EasyMesh, multi-SSID and parental controls

| Helper | RPC / positional arguments | Result |
| --- | --- | --- |
| `get_iptv_config()` | `iptv.get_conf`, `[]` | `Configuration` |
| `get_easymesh_config()` | `easymesh.get_conf`, `[]` | `Configuration`; not topology |
| `get_multi_ssid_interfaces()` | `multi_ssid.get_all_multi_ssid_iface`, `[]` | List of section-name strings; null becomes `[]` |
| `get_multi_ssid_config(section)` | `multi_ssid.get_conf`, `["wireless", section]` | `WirelessInterface` for the selected section, or `None` |
| `get_parental_control_config(group=None)` | `parental_control.get_conf`, `[]` or `[group]` | List of `ParentalGroup`, also for one selected group; null becomes `[]` |

These helpers are source-backed and offline-tested; see [compatibility](compatibility.md)
for successful hardware reads, RPC rejections and untested forms. They
do not change VLANs, apply profiles, enroll mesh nodes, create SSIDs or change
parental policies. `section` and any supplied `group` must be nonempty strings;
invalid arguments fail before a request. Use an actual returned section name,
not a guessed radio identifier. Only the selected-section form of the multi-SSID
configuration RPC is wrapped.

IPTV and EasyMesh results must be objects; null is rejected rather than treated
as disabled. A null selected SSID remains absent/unknown; it does not prove the
radio is disabled. Wrong result types raise `CudyAPIError`, and unsupported RPCs
remain `CudyUnsupportedError`. Nested values, string flags, schedule fields and
unknown firmware fields remain unchanged; no default policy is invented.

SSID configuration may contain Wi-Fi keys and RADIUS credentials. Parental
groups may contain private device lists, website rules and schedules. Do not log
raw results. The contributor verifier includes unfiltered configuration reads
only with `--include-config`; it does not enumerate and fetch individual SSID
sections automatically.

### Client names, traffic and Wi-Fi information

| Helper | RPC / positional arguments | Result |
| --- | --- | --- |
| `get_client_names()` | `devices.get_name`, `[]` | List of `ClientName`; null becomes `[]`, not a MAC-keyed map |
| `get_client_traffic_page(page=1)` | `devices.traffic_stat`, `[start, end]` | `ResponsePage[ClientTraffic]` with entries and optional total count |
| `get_wifi_frequencies()` | `wifi.get_freqlist`, `[]` | `FirmwareRecord` keyed by firmware interface names |
| `get_wifi_scan_results(interface=None)` | `wifi.get_aplist`, `[]` or `[interface]` | List of `AccessPoint`, or `None` when unavailable |

These helpers are source-backed and offline-tested, with model-specific hardware
results recorded in [compatibility](compatibility.md). All preserve unknown fields. Name records do not establish
physical identity across randomized MAC addresses. The traffic helper fetches
exactly one page with inclusive bounds of 100 entries (page 2 is `[101, 200]`),
not every client or historical usage. It preserves rates/counters verbatim and
does not infer counter direction, accounting periods or reset behavior. Pages
can change between calls. Invalid page types (including booleans) fail locally.

Traffic results must contain an object array `devlist`; optional non-null
`devcnt` must be a nonnegative integer. Frequency results must be objects;
interface names and nested channel/frequency structures are not hardcoded.
Malformed top-level structures raise `CudyAPIError`.

The AP-result reader sends only `wifi.get_aplist`, never `wifi.trigger_scan`.
It does not poll, wait, join a network or initiate discovery. `None` means
unavailable/not ready, whereas `[]` is an empty result; returned results may be
stale. An explicitly supplied interface must be nonempty text. AP records can
include sensitive network details, so do not log their raw contents. An
unsupported method raises `CudyUnsupportedError`, without trying an active
scan or a different endpoint as fallback.

### Additional configuration reads

All of these methods send an empty positional argument list (`[]`). They are
source-backed and offline-tested, with hardware results in [compatibility](compatibility.md).

| Helper | RPC | Result |
| --- | --- | --- |
| `get_system_config()` | `conf.get_system` | `Configuration`; not runtime system status |
| `get_ipv6_config()` | `conf.get_ipv6` | `Configuration` |
| `get_default_config()` | `conf.get_defaults` | `Configuration`; does not restore defaults |
| `get_ddns_config()` | `conf.get_ddns` | `Configuration`; may contain credentials |
| `get_connectivity_check_config()` | `conf.get_pingcheck` | `Configuration`; does not initiate a check |
| `get_auto_reboot_config()` | `conf.get_autoreboot` | `Configuration` or `None` for an empty-array response; never triggers reboot |
| `get_qos_config()` | `conf.get_qos` | `ResponseValue`; structured firmware-defined result, including possible null |

Object readers preserve empty objects and all nested/unknown fields. Automatic-reboot
settings additionally accept the observed empty array as `None` (unavailable,
not necessarily disabled). Null and other non-object responses raise `CudyAPIError`. QoS is intentionally unconstrained:
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
