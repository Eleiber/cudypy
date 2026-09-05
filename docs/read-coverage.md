# Read-method coverage

This checklist separates implemented helpers from candidates requiring request,
response and side-effect verification. It covers the app's router RPC method
catalog and the previously reviewed browser status/client workflows. It is not
an exhaustive inventory of every browser page, firmware endpoint, cloud API or
managed-switch API. A generic `call_api()` escape hatch does not count as a
dedicated, tested helper.

## Implemented RPC reads

| RPC | Library helper(s) |
| --- | --- |
| `system.info` | `get_system_info`, `get_system_status` |
| `net.iface_status` | `get_network_status`, `get_interface_status` |
| `devices.get_devlist_ex` | `get_devices` and client filters/lookups |
| `devices.get_devinfo` | `get_client_info` |
| `conf.get_rate_limit` | `get_client_rate_limit` |
| `conf.get_internet_schedule` | `get_client_internet_schedule` |
| `feature.supported` | `get_supported_features` |
| `eth.getstatus` | `get_ethernet_status`, `get_ethernet_ports` |
| `mesh.get_clients` | `get_mesh_clients` |
| `mesh.get_devices` | `get_mesh_device_page` |
| `net.traffic_stat` | `get_traffic_stats` |
| `conf.get_workmodes` | `get_work_modes` |
| `wifi.get_schedule` | `get_wifi_schedule` |
| `wifi.get_wds_status` | `get_wds_status` |
| `wifi.get_wps_status` | `get_wps_status` |
| `vpn.get_status` | `get_vpn_status` |
| `conf.get_all` | Selected LAN, DHCP, wireless and VPN configuration helpers; not every section |
| `conf.get_system` | `get_system_config` |
| `conf.get_ipv6` | `get_ipv6_config` |
| `conf.get_defaults` | `get_default_config` |
| `conf.get_ddns` | `get_ddns_config` |
| `conf.get_pingcheck` | `get_connectivity_check_config` |
| `conf.get_autoreboot` | `get_auto_reboot_config` |
| `conf.get_qos` | `get_qos_config` |

The last seven configuration helpers have source-confirmed argument lists and
offline tests, but no hardware verification yet. See [read contracts](feature-reads.md)
for response types and sensitive-data handling. For older helpers, consult the
[compatibility guide](compatibility.md): unsupported RPCs remain explicit errors,
not empty configuration. Unsupported on one firmware does not mean universally
unsupported.

## Missing helpers / candidates to verify

Every method below lacks a dedicated helper. Listing one does **not** classify
it as safe to invoke or automatically retry. Verify callers and result consumers
before implementation, particularly operations that may trigger discovery,
contact external services, generate credentials or mark messages as read.

| Area | RPC candidates | Next verification |
| --- | --- | --- |
| Client identity | `devices.get_name`, `devices.mdns_browse` | Name-map structure; whether browsing performs active discovery |
| Client traffic / legacy list | `devices.traffic_stat`, `devices.get_devlist` | Pagination, result shape and native counter semantics |
| Network | `net.online_interfaces`, `net.get_inetip`, `net.online_check` | Passive status versus active external checks |
| Wi-Fi | `wifi.get_freqlist`, `wifi.get_aplist` | Radio arguments; cached results versus scan initiation |
| Mesh | `easymesh.get_conf`, `mesh.uplinks_scan_result`, `mesh.smt_devices` | Read-only behavior and prerequisites; no scans or enrollment |
| IPTV | `iptv.get_conf` | Object fields and null variants |
| VPN | `vpn.get_conf`, `vpn.get_connection`, `vpn.export_conf` | Protocol arguments and sensitive profile/key material; export side effects |
| Multi-SSID | `multi_ssid.get_all_multi_ssid_iface`, `multi_ssid.get_conf` | Interface identifiers and section shapes |
| Parental control | `parental_control.get_conf` | Group/device mappings and schedule structures |
| Cellular | `cellular.getstatus`, `cellular.get_data`, `cellular.get_statistics` | Modem/interface arguments and counter units |
| Messages | `cellular.list_sms`, `cellular.read_sms` | Pagination and read-state side effects; message privacy |
| Ad blocking | `adshield.get_providers`, `adshield.get_conf`, `adshield.get_status`, `adshield.get_stats`, `adshield.get_dashboard`, `adshield.get_servers`, `adshield.get_device` | Provider-specific arguments, result variants and external calls |
| Maintenance/status | `sysinfo`, `system.zonename`, `system.upgrade_fwinfo`, `system.upgrade_checkstatus`, `apply_status` | Authentication context, arguments and whether a call reads or changes state |
| Provider integration | `vpn.surfshark_server` | External requests and arguments; not assumed passive |

`vpn.get_conf` is a distinct RPC from the existing `get_vpn_config()` helper,
which reads selected sections through `conf.get_all`.

`combo.call` needs separate treatment: a batch can contain mutations, so it must
not be added wholesale to the read-retry allowlist. Login/token exchanges,
configuration setters, reboot/reset, upgrade/check/download initiation, scans,
ping tests, enrollment, WPS and OAuth initialization are outside this passive-read
batch even where they produce useful response data.

## Browser coverage still to review

The reviewed browser home, system-status and client pages load HTML fragments;
they are not interchangeable with JSON app RPCs. Client details, rates and
system/interface status have library representations, but no field-by-field
parity claim is made for all rendered panels. Additional configuration/status
pages need a separate inventory of routes, rendered fields and backing calls.
Do not infer a missing RPC from a hidden UI panel, or invoke form actions merely
to discover their output.
