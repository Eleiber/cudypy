# Router web-interface coverage

The router web interface and app RPC expose overlapping, but not identical,
data. Implementing the app's read-method catalog does not establish full web
panel parity. This guide describes browser-delivered source inspected on
WR3000H V1.0 and WR3000 V2.0 with the firmware versions in
[compatibility](compatibility.md).

## Transport and safety boundaries

The reviewed pages load HTML fragments through `cbi_xhr_load`. The default
polling interval is six seconds, with refreshes skipped for hidden fragments.
Other data loaders use GET requests with explicitly selected intervals. Browser
forms submit multipart POST requests, including form-control and CSRF fields;
these are not the JSON payloads used by the app RPC client.

GET does not automatically mean passive: the shared JavaScript also invokes
logout and dismissal actions with GET. Auto-upgrade source contains a separate
update-check POST and a follow-up display URL with an action-related parameter.
Those actions were inspected as source, not invoked. No JavaScript was executed,
forms submitted, diagnostics launched, uploads performed or configuration saved.

## Confirmed gaps and partial coverage

Paths below are relative to `/cgi-bin/luci/admin/`. Form field names establish
the displayed concepts, not a guarantee that an identically named RPC or UCI
section can be fetched. Derived controls can differ from stored configuration.

| Panel source / displayed data | Current library coverage | Remaining work |
| --- | --- | --- |
| `network/wan/config/detail`: protocol, credentials, DNS, MTU, MAC override, secondary addressing, access concentrator/service | Runtime WAN status exists; no dedicated WAN configuration reader | Verify the corresponding configuration read and derived-field mapping |
| `network/firewall`: SPI, DoS protection, ping response; `network/ttl`: override settings | No dedicated readers for these settings | Verify configuration sections and result schemas |
| `network/forwards`: protocol, source port, destination address/port, rule name | No dedicated forwarding-rule reader | Read rules without creating/editing them; preserve extra fields |
| `network/upnp`: enable state and a separate polling fragment | No dedicated UPnP configuration/mapping reader | Inspect the polling payload and distinguish configuration from active mappings |
| `system/administration`: HTTPS-only, local-manager rules; remote-manager restrictions on the inspected WR3000H page | No dedicated administration-access reader | Map access rules without changing them |
| `network/igmp`: snooping on both; proxy/version on the inspected WR3000H page | IPTV configuration is present, but no dedicated IGMP reader | Verify the separate multicast settings |
| `services/coovachilli`: portal, RADIUS, allowed domains/addresses, lease and DNS settings on the inspected WR3000H page | No dedicated captive-portal reader | Verify configuration access; credentials require careful handling |
| `network/dns`: rebinding protection, forced DNS, resolver/TLS/provider-derived controls | Raw DHCP configuration is already retained | Check field-by-field derivation before claiming data is missing or adding a duplicate reader |
| `network/wireless/config/uncombine`: SSID, encryption, channel/width, power, station limit, hidden/isolation settings | Raw wireless configuration and a limited typed interface model exist | Map radio/section fields and derived channel controls; raw coverage is not typed coverage |
| `system/autoupgrade`: auto-update/time controls and firmware metadata | System settings and firmware metadata readers exist | Verify field derivation and nonempty metadata; no update initiation is needed |
| `status/bandwidth`: timestamped per-interface counter samples | No web-bandwidth sample reader; existing traffic RPCs are different endpoints | Add an explicitly scoped web transport/read contract after resolving collection prerequisites |
| `status/statistic`, referenced by WR3000 topology source | JSON object response observed, but no dedicated reader | Inspect its complete schema and determine overlap with existing RPCs |

These are gaps in dedicated coverage, not proof that the firmware lacks a
usable generic RPC. `call_api()` is an escape hatch, not a tested mapping for
these web forms. In particular, do not derive a new `conf.get_all` selector
solely from a rendered form's name and advertise it as verified.

## The stock panel already has graphs

Both inspected firmwares render per-interface bandwidth graphs with SVG.
They also load ECharts, although loading that library alone does not establish
which widgets use it. The bandwidth fragment polls `status/bandwidth` every
three seconds, passing a runtime interface identifier resolved by the server.
Logical wireless-section names and runtime interface identifiers differ; they
must not be hardcoded as interchangeable.

The graph source interprets each sample as:

`[timestamp, rx_bytes, rx_packets, tx_bytes, tx_packets]`

It derives byte rates from counter differences and elapsed time, using a
microsecond time scale. It ignores overlapping timestamps, handles counter
decreases, and retains a width-dependent browser series. Display direction
can be swapped by the rendered interface view; this is not evidence for the
meaning of similarly named per-client RPC counters.

Single passive reads of the bandwidth endpoint returned empty arrays on both
models. A populated response, retention duration and history availability when
the panel is closed remain unverified. The newer fragment also invokes
`status/checkbandwidth`; that helper was not called because its collection
side effects are unknown. The source supports a potential short-term sample
source, not a claim of durable per-device usage history.

The companion dashboard offers tab-local client-rate exploration, search/sort,
selection and polling controls. Graphs alone are not an advantage unique to it.
Persistent background collection, multi-router timelines and period-based
usage rankings remain the more substantial prospective improvements.

## Scope and remaining audit

Inspected on both models: home/setup/tools/panel navigation, relevant shared
request-loader JavaScript, bandwidth and topology source, LAN/wireless/system
status fragments, wireless configuration loaders and separate-band settings,
auto-upgrade display forms, IGMP and administration forms.

Additionally inspected on WR3000H: WAN configuration, captive portal, firewall,
forwarding, routes, UPnP, DNS, ARP binding, TTL and scheduled-WOL display pages.
Empty routes/ARP/WOL tables do not establish populated-row schemas. Menu
visibility differs between the two rendered panels and does not prove backend
availability or model capability.

Only linked/inventoried, not fully audited here: other filters, DMZ, ALG,
port-trigger rules, detailed QoS and DDNS forms, CWMP, time/LED controls, guest/WDS
forms, mesh management, detailed client pages and diagnostic/log tools. Earlier
client/RPC checks do not replace a field-by-field audit of those pages. The
newer tools page also links packet capture; no capture was started.

This is a bounded source and response audit, not exhaustive browser parity or
access to server-side Lua/backend implementation. Generic third-party scripts
were inventoried but not audited in full. Source/response values, credentials
and private network inventories are not distributed as fixtures.

Recommended order: verify WAN/firewall/administration/IGMP configuration reads;
then establish the web bandwidth/statistics contracts; then complete the
remaining display-page inventory before redesigning the companion dashboard.
