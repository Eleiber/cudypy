# Compatibility

CudyPy is experimental. Firmware and configuration determine availability, not
model name alone. Authenticated passive reads were checked on:

| Model | Firmware evaluated |
| --- | --- |
| WR3000H V1.0 | 2.4.5-20250515-105059 |
| WR3000 V2.0 | 2.5.24-20260727-122111 |

## Expanded hardware checks

The expanded pass exercised 38 helpers on each model. After correcting two
empty-array response variants, 28 helpers returned successfully on WR3000H and
36 on WR3000. Remaining outcomes were explicit RPC errors, not hidden fallbacks.
Success verifies handling of the observed response, not every field, argument
form or populated configuration variant.

Both models returned supported responses for system/interface status, extended
and legacy clients, client-name records, features, Ethernet ports, mesh topology,
online interfaces, work modes, Wi-Fi schedules, WDS/WPS status, frequency lists,
existing AP results, general VPN settings, LAN/DHCP/wireless configuration,
system/IPv6/default/DDNS/connectivity-check settings, IPTV and parental groups.
Empty responses do not prove support for all nonempty configurations.

| Read / observed variant | WR3000H | WR3000 |
| --- | --- | --- |
| Client traffic page, network traffic | -32601 | Object |
| VPN status | -32601 | List |
| VPN profiles, `["clients"]` | -32601 | Object |
| QoS configuration | -32601 | Object |
| EasyMesh configuration | -32601 | -32601 |
| Multi-SSID interface listing | -32004 | -32004 |
| Ad-blocking providers and configuration | -32601 | Object |
| Configuration-apply status | -32601 | String |
| Automatic-reboot settings | Empty array → `None` | Empty array → `None` |
| Firmware metadata, no arguments | Empty array → `None` | Empty array → `None` |

`-32601` is method-not-found. The multi-SSID `-32004` rejection is preserved as
an RPC error; it is not classified as method-not-found or an empty interface list.
No setting was changed to force a different response.

`get_auto_reboot_config()` and `get_firmware_update_info()` now accept the
observed empty array as unavailable object data and return `None`. This does not
mean scheduling is disabled, firmware is current, or no upgrade exists. Objects
remain raw; other malformed response types are rejected.

Earlier hardware checks also covered individual client details and rate limits;
per-client Internet schedules returned -32601 on both models. Ethernet
auto-negotiation fields vary (`auto` versus `autoneg`); model and WDS fields may
be absent. Those observations are not universal firmware rules.

## Password authentication and concurrent sessions

Password authentication was checked on WR3000H V1.0 with firmware
2.4.5-20250515-105059. A successful challenge/login exchange was followed by an
authenticated system-status read. These checks exercised the library's
authentication logic with an explicitly supplied salt and an alternate HTTP
adapter; they do not verify automatic mDNS discovery or the default HTTP
transport for password login.

Two independent password logins returned distinct session tokens. The first
session remained valid after the second login, and both completed two rounds
of concurrent system-status reads without HTTP/RPC errors or automatic
reauthentication. Logins were sequential; reads were concurrent. This establishes
two coexisting API sessions on the tested firmware, not a maximum session count,
simultaneous-login behavior, session lifetime or browser-session compatibility.

One deliberately incorrect password was rejected with RPC error `-32003` over
HTTP 200. `authenticate()` returned `False`, left no session token and cleared
local cookies. No login retry or authenticated status request followed the
rejection. Lockout thresholds and repeated-failure behavior were not tested.

## Still unverified

- Selected VPN client profiles, non-default VPN categories and connection pages.
- Selected multi-SSID sections, filtered parental groups, node-specific mesh
  client pages and target-specific firmware-check state.
- Cellular helpers: no cellular-capable model has been verified.
- Ad-blocking provider status/statistics and other external-provider behavior.
- Nonempty automatic-reboot and firmware-metadata objects on hardware.
- Password login on WR3000 V2.0, automatic mDNS discovery, default-transport
  password login and automatic reauthentication after session expiry.
- Mutation behavior, counter units/reset boundaries and activity heuristics.
  No hardware writes, scans, exports or SMS reads were performed.
- Python versions other than 3.12 and full admin-page field parity.

Credentials and raw responses are not distributed as fixtures. Regression tests
use synthetic data. Unsupported methods raise `CudyUnsupportedError`; other
failures retain their RPC code. Successful reads do not prove related writes work.
