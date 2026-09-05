# Changelog

## Unreleased

- Verify 38 passive-read helpers on WR3000H and WR3000 firmware. Handle observed
  empty-array automatic-reboot and firmware-metadata responses as unavailable
  objects (`None`); preserve firmware-specific RPC errors and document limits.

- Add legacy raw clients and one-shot firmware metadata/check/apply status reads.
  Classify timezone assignment as a setter, not a missing read operation.

- Add cellular status, data-plan settings and native statistics reads with
  explicit interface selection and opt-in, shape-only compatibility checks.

- Add ad-blocking provider/configuration reads and explicit-provider status and
  statistics reads. Preserve provider wrappers/error codes; disable automatic
  auth replay for potentially external provider requests.

- Add online-interface names, VPN category/selected-client configuration and
  paged VPN connections. Preserve raw response wrappers and sensitive fields;
  keep profile reads opt-in in the compatibility checker.

- Add IPTV, EasyMesh, multi-SSID section discovery/configuration and parental
  group configuration readers with explicit shape checks and raw-field retention.

- Add raw client-name records, paged client traffic, Wi-Fi frequency information
  and existing AP-result reads, preserving unavailable scan results separately
  from empty lists. No scan initiation or automatic polling is performed.

- Add system, IPv6, defaults, DDNS, connectivity-check, automatic-reboot and QoS
  configuration readers with lossless results, offline contract tests and opt-in
  compatibility checks. Document missing read candidates and verification limits.

- Add offline-capable dashboard traffic history, client drill-down, search/sort,
  and bounded polling with pause/resume and explicit missing-data gaps.
- Refresh older guides, correct unknown-activity documentation, use model-only
  compatibility descriptions and document synchronous/async integration options.

- Add typed system/interface status, VPN configuration and mesh client-page
  reads; expand the token-only, shape-reporting compatibility verifier.

- Preserve unknown device activity as `None` (intentional compatibility change),
  label the legacy online cutoff as a heuristic, and expose native duration,
  counters and raw fields without claiming verified counter direction.

- Add typed wireless-section reads and an advanced source-backed Wi-Fi
  configuration writer, with offline-only tests and no automatic replay.

- Add typed LAN configuration plus DHCP and wireless section reads, preserving
  firmware-specific fields and documenting sensitive configuration handling.

- Add source-backed client naming, Internet blocking, and rate-limit set/clear
  controls with strict input validation and offline-only mutation tests.

- Add work-mode, Wi-Fi schedule, WDS/WPS, VPN and per-client configuration reads.
- Add typed Ethernet port and decimal rate-limit models, preserving raw fields.
- Distinguish unsupported firmware methods with `CudyUnsupportedError`.

- Support existing session tokens and explicit salts; local API requests no
  longer depend on mDNS device IDs.
- Consolidate RPC transport, validate response envelopes, and report
  authentication rejection consistently.
- Retry only source-confirmed reads after authentication expiry; never replay
  custom methods, reboot, or transport failures.
- Reject redirects and invalid origins, omit token-bearing network error text,
  and ignore environment proxy settings.
- Correct interface status payloads and preserve native device fields.
- Correct APK RSSI conversion and display traffic rates as bytes/s rather than
  treating raw byte rates as kilobytes/s.
- Add firmware feature, Ethernet, mesh client, and traffic read methods.
- Add offline regression tests and block accidental HTTP calls in unit tests.
- Reject malformed empty RPC errors and clear local cookies after failed login.
- Verify read methods on WR3000H V1.0 and WR3000 V2.0 firmware using
  browser session tokens; inspect both admin HTML and JavaScript.
- Correct the single-client `[1, 1]` request and follow inclusive client ranges
  when needed. Detect inconsistent pagination rather than return partial data.
- Expose numeric RPC error codes, including unsupported methods on older firmware.
- Require explicit dashboard router configuration instead of a fallback IP.
- Correct installation and compatibility documentation.

Behavior changes: malformed device lists now raise errors; missing MAC/IP
values remain unknown rather than becoming the string "None";
`get_network_status()` defaults to the WAN interface; arbitrary RPC calls no
longer retry automatically after auth failure.
Python 3.10 or later is now required.

## 0.1.0 prototype

Password authentication, mDNS discovery, device listing/filtering, basic status
reads, context management, and an experimental Flask dashboard. Historical
prototype documentation was not a verified compatibility or test report.

