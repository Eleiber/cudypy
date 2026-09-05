# Compatibility

CudyPy is experimental. Results apply to the firmware and request forms listed
below, not every configuration or firmware available for a model.

## Tested hardware

| Model | Firmware | Passive-read checks |
| --- | --- | --- |
| WR3000H V1.0 | 2.4.5-20250515-105059 | 38 helpers: 28 successful responses, 10 RPC errors |
| WR3000 V2.0 | 2.5.24-20260727-122111 | 38 helpers: 36 successful responses, 2 RPC errors |

**Legend:** ✓ verified for the stated check; △ limited or unavailable response;
✗ request failed or was rejected; — not verified.

## Password authentication and concurrent sessions

| Connection mode | WR3000H V1.0 | WR3000 V2.0 |
| --- | --- | --- |
| Existing session token and authenticated read | ✓ | ✓ |
| Password login over HTTP, automatic salt discovery and default transport | ✓ | ✓ |
| Two coexisting API sessions with concurrent reads | ✓ | — |

Both login modes include an authenticated status read. The two-session check
used distinct tokens, sequential logins and two rounds of concurrent status reads
without reauthentication. Maximum session count, session lifetime, simultaneous
logins, browser/API coexistence and refresh after expiry remain unverified.

## Read verification

Cells describe the observed RPC response, before conversion into Python models.
A ✓ confirms handling of that response, not every field or populated variant.
The table includes additional selected-client checks beyond the 38-helper pass.

| Read / request form | WR3000H V1.0 | WR3000 V2.0 |
| --- | --- | --- |
| System and interface status | ✓ | ✓ |
| Extended and legacy client lists; client-name records | ✓ | ✓ |
| Individual client details and rate limits | ✓ | ✓ |
| Per-client Internet schedules | ✗ `-32601` | ✗ `-32601` |
| Feature declarations and Ethernet port status | ✓ | ✓ |
| Mesh topology | ✓ | ✓ |
| Online interfaces and available work modes | ✓ | ✓ |
| Wi-Fi schedules and WDS/WPS status | ✓ | ✓ |
| Wi-Fi frequency lists and existing AP results | ✓ | ✓ |
| General VPN settings | ✓ | ✓ |
| LAN, DHCP and wireless configuration | ✓ | ✓ |
| System, IPv6 and default settings | ✓ | ✓ |
| DDNS and connectivity-check settings | ✓ | ✓ |
| IPTV and unfiltered parental groups | ✓ | ✓ |
| Client traffic page and network traffic | ✗ `-32601` | ✓ Object |
| VPN status | ✗ `-32601` | ✓ List |
| VPN profiles, `["clients"]` | ✗ `-32601` | ✓ Object |
| QoS configuration | ✗ `-32601` | ✓ Object |
| EasyMesh configuration | ✗ `-32601` | ✗ `-32601` |
| Multi-SSID interface listing | ✗ `-32004` | ✗ `-32004` |
| Ad-blocking providers and configuration | ✗ `-32601` | ✓ Object |
| Configuration-apply status | ✗ `-32601` | ✓ String |
| Automatic-reboot settings | △ Empty array → `None` | △ Empty array → `None` |
| Firmware metadata, no arguments | △ Empty array → `None` | △ Empty array → `None` |

`-32601` means method-not-found and raises `CudyUnsupportedError`. Other RPC
errors retain their codes; `-32004` is not treated as an empty interface list.
An empty-array response mapped to `None` does not mean reboot scheduling is
disabled, firmware is current or no upgrade exists. No settings were changed
to obtain different responses.

## Verification gaps

| Check | WR3000H V1.0 | WR3000 V2.0 |
| --- | --- | --- |
| Selected VPN profiles, non-default categories and connection pages | — | — |
| Selected multi-SSID configuration and filtered parental groups | — | — |
| Node-specific mesh client pages | — | — |
| Target-specific firmware-check state | — | — |
| Nonempty automatic-reboot settings and firmware metadata | — | — |
| Ad-blocking provider status/statistics and external-provider behavior | — | — |
| Cellular helpers on cellular-capable hardware | — | — |
| Hardware mutations, scans, exports and SMS operations | — | — |
| Counter units/direction/reset boundaries and activity heuristics | — | — |
| Full admin-page field parity | — | — |

## Python and model verification

| Scope | Status |
| --- | --- |
| Offline regression suite on Python 3.12 | ✓ Synthetic fixtures; unmocked HTTP blocked |
| Password login, discovery and system-info read on Python 3.13 | ✓ Both models over HTTP, default transport |
| Full regression suite on Python versions other than 3.12 | — |
| Response model conversion | ✓ Offline tests; not a separate hardware-validation pass |

Error-handling validation on WR3000H V1.0: one incorrect-password attempt returned
RPC `-32003` over HTTP 200. The library returned `False`, cleared its local token
and cookies, and did not retry. Lockout thresholds and repeated failures were not
tested; this check has not been repeated on WR3000 V2.0.

Firmware fields can be absent or vary, including Ethernet `auto`/`autoneg`,
model names and WDS fields. Empty responses do not establish all populated
schemas. Successful reads do not prove related writes work. Credentials and
raw hardware responses are not distributed as fixtures.

See [response models](models.md), [read contracts](feature-reads.md) and
[web-interface coverage](web-interface.md) for field semantics and scope.
