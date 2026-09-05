# Compatibility

CudyPy is experimental. A model name alone does not determine which RPCs are
available; firmware and configuration also matter.

| Model | Firmware evaluated |
| --- | --- |
| WR3000H V1.0 | 2.4.5-20250515-105059 |
| WR3000 V2.0 | 2.5.24-20260727-122111 |

Selected authenticated reads succeeded on these versions: system/interface
status, clients and client details, Ethernet ports, features, mesh topology,
work modes, Wi-Fi schedules and WDS/WPS status, LAN/DHCP/wireless configuration,
and VPN configuration. Empty/null responses are legitimate for some operations.

Observed differences:

- `net.traffic_stat` and `vpn.get_status` were unavailable (-32601) on the
  evaluated WR3000H firmware; the evaluated WR3000 firmware supported them.
- Per-client Internet schedules were unavailable on both evaluated versions.
- Ethernet auto-negotiation fields vary (`auto` versus `autoneg`).
- System model names and WDS fields may be absent.

## Verification limits

- Cellular status, data-plan settings and statistics are source-backed and
  offline-tested only. No cellular-capable model has been verified for these
  helpers; the listed router models do not establish modem support.

- Ad-blocking provider/configuration/status/statistics helpers are source-backed
  and offline-tested only. Provider-service behavior and hardware support remain
  unverified; status/statistics are not automatically replayed or probed.

- Online interface names, VPN profile reads and VPN connection pages are
  source-backed/offline-tested only; hardware availability remains unverified.

- IPTV, EasyMesh, multi-SSID and parental-control configuration helpers are
  source-backed and offline-tested; hardware availability remains unverified.

- Client-name records, paged client traffic, Wi-Fi frequencies and existing AP
  result reads are source-backed/offline-tested only, not hardware-verified.

- The additional system, IPv6, defaults, DDNS, connectivity-check, automatic-reboot
  and QoS configuration helpers are offline-tested only; their availability on
  the listed models has not yet been checked.

- Hardware checks used existing session tokens. Password login is covered by
  offline tests but was not hardware-verified in these checks.
- Mutations are derived from app request structures and tested offline only.
  No claim of live write compatibility is made.
- Node-specific mesh pages require a known node identifier and remain
  offline-tested; mesh topology reads do not prove page support.
- The suite has been run on Python 3.12. Other declared Python versions have
  not been independently runtime-verified.
- Inactivity is a heuristic, not reachability. Client-counter direction and
  reset behavior remain uncertain; see [device semantics](device-semantics.md).

Unsupported methods raise `CudyUnsupportedError`; other failures retain their
numeric RPC code where supplied. Do not treat an unsupported response as empty
configuration or assume a read being available proves the related write works.
