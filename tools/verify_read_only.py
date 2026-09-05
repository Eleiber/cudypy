"""Contributor token-only compatibility probe. No writes, scans or login calls."""

import argparse
import json
from pathlib import Path

from cudypy import CudyAPIError, CudyAuthError, CudyRouter


def shape(value):
    """Report structural types without exposing router or client values."""
    if isinstance(value, dict):
        # Keys in nested maps may be client identifiers, so report only types.
        return {"type": "object", "value_types": sorted({type(v).__name__ for v in value.values()})}
    if isinstance(value, list):
        return {
            "type": "array",
            "length": len(value),
            "item_types": sorted({type(v).__name__ for v in value}),
        }
    return {"type": type(value).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument(
        "--include-config",
        action="store_true",
        help="Read configuration, including potentially sensitive fields; report shapes only",
    )
    parser.add_argument(
        "--client-mac", help="Optional known client for detail/limit/schedule reads"
    )
    parser.add_argument("--mesh-node", help="Optional known mesh node for its first client page")
    args = parser.parse_args()
    try:
        token = args.token_file.read_text(encoding="utf-8").strip()
        with CudyRouter(args.url, auth_token=token) as router:
            report = {}
            reads = {
                "system": router.get_system_info,
                "devices": router.get_devices,
                "features": router.get_supported_features,
                "ethernet": router.get_ethernet_status,
                "mesh": router.get_mesh_clients,
                "traffic": router.get_traffic_stats,
                "wan": router.get_network_status,
                "system_typed": router.get_system_status,
                "wan_typed": router.get_interface_status,
                "ports_typed": router.get_ethernet_ports,
                "work_modes": router.get_work_modes,
                "wifi_schedule": router.get_wifi_schedule,
                "wds": router.get_wds_status,
                "wps_status": router.get_wps_status,
                "vpn_status": router.get_vpn_status,
                "online_interfaces": router.get_online_interfaces,
                "client_names": router.get_client_names,
                "client_traffic_first_page": router.get_client_traffic_page,
                "wifi_frequencies": router.get_wifi_frequencies,
                "wifi_existing_scan_results": router.get_wifi_scan_results,
            }
            if args.include_config:
                reads.update(
                    lan_config=router.get_lan_config,
                    dhcp_config=router.get_dhcp_config,
                    wireless_config=router.get_wireless_config,
                    vpn_config=router.get_vpn_config,
                    vpn_profiles=router.get_vpn_profiles,
                    system_config=router.get_system_config,
                    ipv6_config=router.get_ipv6_config,
                    default_config=router.get_default_config,
                    ddns_config=router.get_ddns_config,
                    connectivity_check_config=router.get_connectivity_check_config,
                    auto_reboot_config=router.get_auto_reboot_config,
                    qos_config=router.get_qos_config,
                    iptv_config=router.get_iptv_config,
                    easymesh_config=router.get_easymesh_config,
                    multi_ssid_interfaces=router.get_multi_ssid_interfaces,
                    parental_control_config=router.get_parental_control_config,
                    adshield_providers=router.get_adshield_providers,
                    adshield_config=router.get_adshield_config,
                )
            if args.client_mac:
                reads.update(
                    client_info=lambda: router.get_client_info(args.client_mac),
                    client_limit=lambda: router.get_client_rate_limit(args.client_mac),
                    client_schedule=lambda: router.get_client_internet_schedule(args.client_mac),
                )
            if args.mesh_node:
                reads["mesh_page"] = lambda: router.get_mesh_device_page(args.mesh_node)
            for name, read in reads.items():
                try:
                    report[name] = {"ok": True, **shape(read())}
                except CudyAuthError:
                    print("Authentication rejected; supply a fresh token.")
                    return 1
                except CudyAPIError as error:
                    report[name] = {"ok": False, "error": str(error), "code": error.code}
            print(json.dumps(report, indent=2))
            return 0 if report["system"]["ok"] and report["devices"]["ok"] else 1
    except (OSError, ValueError):
        print("Cannot read token file or invalid connection arguments.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
