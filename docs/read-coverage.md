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
| `devices.get_name` | `get_client_names` |
| `devices.traffic_stat` | `get_client_traffic_page` |
| `wifi.get_freqlist` | `get_wifi_frequencies` |
| `wifi.get_aplist` | `get_wifi_scan_results` (existing results only) |
| `iptv.get_conf` | `get_iptv_config` |
| `easymesh.get_conf` | `get_easymesh_config` |
| `multi_ssid.get_all_multi_ssid_iface` | `get_multi_ssid_interfaces` |
| `multi_ssid.get_conf` | `get_multi_ssid_config` (one selected section) |
| `parental_control.get_conf` | `get_parental_control_config` |
| `net.online_interfaces` | `get_online_interfaces` |
| `vpn.get_conf` | `get_vpn_profiles`, `get_vpn_client_config` (selected argument forms) |
| `vpn.get_connection` | `get_vpn_connection_page` |
| `adshield.get_providers` | `get_adshield_providers` |
| `adshield.get_conf` | `get_adshield_config` |
| `adshield.get_status` | `get_adshield_status` (explicit provider, no auth replay) |
| `adshield.get_stats` | `get_adshield_stats` (explicit provider, no auth replay) |
| `cellular.getstatus` | `get_cellular_status` |
| `cellular.get_data` | `get_cellular_data_config` |
| `cellular.get_statistics` | `get_cellular_statistics` |
| `devices.get_devlist` | `get_legacy_devices` (raw array, no extended pagination) |
| `system.upgrade_fwinfo` | `get_firmware_update_info` (no-argument form) |
| `system.upgrade_checkstatus` | `get_firmware_check_status` (explicit target) |
| `apply_status` | `get_apply_status` |

The additional configuration, client/Wi-Fi, IPTV, EasyMesh, multi-SSID and
parental-control, VPN/network, ad-blocking, cellular and maintenance helpers have source-confirmed argument lists and
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
| Client identity | `devices.mdns_browse` | Whether browsing performs active discovery; identity certainty remains unproven |
| Network | `net.get_inetip`, `net.online_check` | Passive status versus active external checks |
| Mesh | `mesh.uplinks_scan_result`, `mesh.smt_devices` | Read-only behavior and prerequisites; no scans or enrollment |
| VPN | `vpn.export_conf` | Sensitive profile/key material; export side effects |
| Messages | `cellular.list_sms`, `cellular.read_sms` | Pagination and read-state side effects; message privacy |
| Ad blocking | `adshield.get_dashboard`, `adshield.get_servers`, `adshield.get_device` | Dashboard access URL/session behavior and provider-account calls; external effects remain unverified |
| System discovery | `sysinfo` | Observed in a cloud/token workflow; local authentication context and contract remain unverified |
| Provider integration | `vpn.surfshark_server` | External requests and arguments; not assumed passive |

`get_vpn_profiles()` uses `vpn.get_conf`, distinct from `get_vpn_config()`,
which reads general settings through `conf.get_all`. Only category selection
and the `clients` plus identifier form are wrapped; other argument forms need
separate verification.

`combo.call` needs separate treatment: a batch can contain mutations, so it must
not be added wholesale to the read-retry allowlist. Login/token exchanges,
configuration setters, reboot/reset, upgrade/check/download initiation, scans,
ping tests, enrollment, WPS and OAuth initialization are outside this passive-read
batch even where they produce useful response data.

`system.zonename` was a review candidate, but the observed caller supplies a
timezone name to set. It is not a passive getter and is excluded from read
helpers/retries. Read configured timezone fields through `get_system_config()`.

## Browser coverage still to review

The reviewed browser home, system-status and client pages load HTML fragments;
they are not interchangeable with JSON app RPCs. Client details, rates and
system/interface status have library representations, but no field-by-field
parity claim is made for all rendered panels. Additional configuration/status
pages need a separate inventory of routes, rendered fields and backing calls.
Do not infer a missing RPC from a hidden UI panel, or invoke form actions merely
to discover their output.
