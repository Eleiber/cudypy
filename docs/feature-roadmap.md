# Feature coverage and limits

The [model reference](models.md) covers every current getter with domain
models, new record/page models and flexible firmware-specific structures. Full
typed field coverage remains distinct from object-returning getter coverage.

The library has grown beyond the initial transport refactor, but does not claim
complete or majority coverage of every APK/panel operation.
Read and write structures are derived from the app and web interface. Support
is established per operation, not inferred from its name alone.

The [read-method checklist](read-coverage.md) tracks dedicated helpers, missing
RPC candidates and the remaining browser inventory separately.

| Area | Present | Work remaining |
| --- | --- | --- |
| Transport/auth | Token sessions, bounded read retries, numeric/unsupported errors | Preserve behavior as coverage expands |
| System/network | System/interface models, Ethernet ports, work modes, LAN configuration and DHCP section models | Hardware/model variation retained through optional fields and `.raw` exports |
| Clients | Full list, filters, direct details, rate-limit and schedule reads; offline-tested controls; explicit unknown activity, elapsed seconds and native counters | Counter viewpoint/reset semantics and hardware write behavior remain explicitly unverified |
| Wi-Fi | WDS/WPS status, schedule/configuration records, typed selected interface, advanced source-backed configuration writes | Hardware write compatibility intentionally unverified; firmware-specific setting constraints remain caller-managed |
| Mesh/VPN | Structured topology/status/configuration and explicit client/connection page models with distinct capability handling | Detailed field schemas and node-specific mesh hardware compatibility remain unverified; no guessed node IDs or topology mutations |
| Diagnostics/maintenance | Traffic read, inherited reboot method | Preserve the no-live-mutations rule; no scans/upgrades/reset probes |
| Packaging/docs | Offline suite, installable package, expanded examples, protocol/live evidence and compatibility guide | See explicit compatibility limits in the compatibility guide |

## What is not full panel parity

The additions cover client controls, useful configuration/status reads and an
advanced Wi-Fi writer. They do not provide a complete firewall/NAT editor, all
VPN-profile management, every WAN/LAN/DHCP write, firmware maintenance workflow,
mesh enrollment/roaming, or every browser form. The dashboard remains read-only
even where the Python library has a mutation method.

Mutation envelopes, positional arguments and known primitive fields follow
the inspected APK callers and are tested offline. Typed models cover selected
read fields, while raw mappings preserve firmware-specific structures. In
particular, the advanced Wi-Fi writer does not validate every possible setting
or guarantee identical behavior across firmware versions. See the operation
guides for exact contracts, side effects and validation boundaries.

## Dashboard and async

The [dashboard](../dashboard/README.md) adds session-local rate graphs, per-client
selection, search/sort and controlled polling. It has no persistent history or
full router-configuration UI. [Async support](async.md) is feasible but not yet
implemented natively; the Python client remains synchronous.
