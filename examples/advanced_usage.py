"""Fetch one device snapshot and filter locally without repeated HTTP requests."""

import os
from cudypy import CudyAPIError, CudyRouter, CudyUnsupportedError


def main():
    try:
        with CudyRouter(
            os.environ["CUDY_ROUTER_URL"],
            password=os.environ.get("CUDY_ROUTER_PASSWORD"),
            auth_token=os.environ.get("CUDY_ROUTER_TOKEN"),
            salt=os.environ.get("CUDY_ROUTER_SALT"),
        ) as router:
            devices = router.get_devices()
            for device in devices:
                if device.connection_type == "wifi":
                    print(device, device.signal_strength, device.formatted_bandwidth_down)
            print("Recently active (heuristic):", sum(d.recently_active is True for d in devices))
            print("Activity unknown:", sum(d.recently_active is None for d in devices))
            status = router.get_system_status()
            print("Firmware:", status.firmware, "uptime seconds:", status.uptime_seconds)
            wan = router.get_interface_status()
            print("WAN reported up:", wan.is_up, "protocol:", wan.protocol)
            features = router.get_supported_features()
            print("Feature response type:", type(features).__name__)
            for port in router.get_ethernet_ports():
                print("Port:", port.label, "link:", port.link_up, "Mbps:", port.speed_mbps)
            for mode in router.get_work_modes():
                print("Available mode:", mode.mode, "name:", mode.name)
            print("Wi-Fi schedules:", len(router.get_wifi_schedule()))
            if devices:
                limit = router.get_client_rate_limit(devices[0].mac_address)
                print("First client's rate limits:", limit)
            try:
                vpn = router.get_vpn_status()
                print("VPN result type:", type(vpn).__name__)
            except CudyUnsupportedError:
                print("This firmware does not expose VPN status")
    except (KeyError, ValueError, CudyAPIError) as error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
