# CudyPy

CudyPy is an unofficial, experimental synchronous Python wrapper for Cudy's local
LuCI app RPC API. Read methods have been checked on WR3000H V1.0 and WR3000 V2.0.
See [tested firmware and results](docs/compatibility.md); model names
alone do not guarantee firmware capabilities.

The package is named `cudypy`.
Install from this source tree, not an assumed PyPI release.

For monitoring graphs, client drill-down and search/sorting, see the
[local dashboard](dashboard/README.md). For asyncio integration and native
async tradeoffs, see [async feasibility](docs/async.md).

## Install

From the repository root, with Python 3.10 or later:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

See [INSTALL.md](INSTALL.md) for development and build instructions.

## Read with an existing session token

Set `CUDY_ROUTER_URL` and `CUDY_ROUTER_TOKEN` in your local environment.
Use the token value from the router's `auth` query parameter or `sysauth`
cookie, not an entire Cookie header. Each router needs its own token.

```python
import os
from cudypy import CudyRouter, CudyAPIError

try:
    with CudyRouter(
        os.environ["CUDY_ROUTER_URL"],
        auth_token=os.environ["CUDY_ROUTER_TOKEN"],
        timeout=10,
    ) as router:
        print(router.get_system_info())
        for device in router.get_devices():
            print(device, device.connection_type)
except CudyAPIError as error:
    print(error)
```

Token sessions do not need mDNS, a device ID, or your password. Expired tokens
raise `CudyAuthError`; obtain a fresh token and create a new client.
Closing a client only closes local resources; it does not log out the browser
or change router configuration.

## Password authentication

```python
import os
from cudypy import CudyRouter

with CudyRouter(
    os.environ["CUDY_ROUTER_URL"],
    password=os.environ["CUDY_ROUTER_PASSWORD"],
    # salt="known-router-salt",  # optional: bypass mDNS when already known
) as router:
    if not router.authenticate():
        raise RuntimeError("Router authentication failed")
    print(router.get_system_info())
```

Without an explicit salt, the client discovers the router's salt over mDNS.
Use a literal router IP for mDNS matching. The legacy `devid` parameter is
accepted but is not sent by the local transport, matching the APK's transient
device ID field.

`authenticate()` retains the prototype's boolean result for password login
failures. API reads authenticate on demand and raise `CudyAuthError` when
login fails. Forced login without a password raises `CudyAuthError`.
Only source-confirmed reads retry once after an authentication rejection when
a password is available. Transport errors and arbitrary RPC methods are never
replayed.

## API

| Method | Result |
| --- | --- |
| `get_system_info()` | Raw system information dictionary |
| `get_devices()` | List of `Device` instances |
| `get_network_status(interface="wan")` | Raw status dictionary for that interface |
| `get_supported_features()` | Raw firmware feature declarations |
| `get_ethernet_status()` | Raw Ethernet port status |
| `get_mesh_clients()` | Raw mesh client data |
| `get_traffic_stats()` | Raw network traffic statistics |
| `get_online_devices()` | Devices passing the legacy inactivity heuristic |
| `get_wifi_devices()`, `get_ethernet_devices()` | Devices filtered by interface |
| `get_device_by_mac(mac)`, `get_device_by_ip(ip)` | First matching device or `None` |
| `get_device_by_hostname(name, case_sensitive=False)` | First matching hostname or fallback device name |
| `call_api(method, params=None, retry_auth=True)` | Full RPC envelope, including `result` |
| `reboot()` | Sends a reboot request; disruptive, tested only with mocks |

Each filtering/search method fetches a new device list. Fetch once and filter
locally when taking a consistent snapshot. Use one client per router and do not
share a client across threads.

Raw results preserve firmware-specific keys. Do not assume `firmware_version`
or any other undocumented key exists. Unsupported methods raise `CudyAPIError`
with a numeric RPC `code` when supplied by the router. For example, the tested
WR3000H firmware rejects `net.traffic_stat` with `code == -32601`. Other builds
or modes may lack WAN or mesh features. See
[the RPC contract](docs/protocol.md).

`call_api` is an advanced escape hatch: it can invoke mutations. Inspect the
firmware or APK payload before using it. The unit suite mocks mutation calls;
it never sends them to hardware.

## Device data

Additional reads for Wi-Fi schedules, WDS/WPS status, VPN, work modes and
per-client details/limits are described in [feature reads](docs/feature-reads.md).
Source-backed client naming, Internet blocking and rate-limit writes are
described in [client controls](docs/client-controls.md). These controls are
offline-tested only; read the side effects and no-replay guarantees before use.
Typed wireless-section reads and the advanced nested Wi-Fi write API are
described in [wireless configuration](docs/wireless.md), including credential
handling and firmware compatibility limitations.
See [device semantics](docs/device-semantics.md) for optional activity state,
elapsed duration, and unresolved counter direction/reset behavior.
Typed Ethernet-port status is available through `get_ethernet_ports()`.

The parser accepts native `macaddr`/`ipaddr` and legacy `mac`/`ip` fields,
`signal` (dBm) or `rssi` (converted to dBm by subtracting 100), and string/integer
boolean values. Unknown fields are preserved in `Device.raw` (excluded from repr).
Malformed device-list envelopes raise errors instead of appearing as an empty
network. `get_devices()` follows inclusive ranges if the first response reports
more clients than it returns. Counts changing during pagination or duplicate
clients raise an error so the caller can retry a fresh read.

`is_online` currently uses the prototype's `inactive < 30` heuristic. Missing
or invalid inactivity stays `None` (unknown); this is not definitive evidence
of reachability. `online` is interpreted as elapsed seconds for
`connected_since`. Firmware-reported `upspeed`/`downspeed` values are retained;
formatting uses bytes/s with explicit binary prefixes (KiB/s, MiB/s), matching
the APK's interpretation of the raw values.
`inbytes`/`outbytes` retain the prototype's receive/send mapping, whose viewpoint
also needs hardware verification.

## Errors and transport

All library errors derive from `CudyAPIError`; authentication and discovery have
`CudyAuthError` and `CudyDiscoveryError` subclasses. Explicitly missing methods
raise `CudyUnsupportedError` (RPC code -32601). HTTP failures, invalid JSON,
malformed RPC envelopes, and invalid result shapes raise errors. Request error
messages omit URLs and tokens. Requests do not follow redirects or use
environment proxies. HTTPS certificate verification remains enabled.

If requests time out, check that this machine can reach the configured router
origin and that local routing, VPN or firewall rules allow the connection.

The client does not configure global logging. Avoid enabling third-party HTTP
wire/debug logging when handling tokens.

## Dashboard and development

The Flask dashboard is an optional local example, outside the installed library.
See [dashboard/README.md](dashboard/README.md). It is not a deployment-ready
multi-user administration service.

Run offline tests from this directory:

```sh
python -m pip install -e ".[dev]"
python -m pytest
```

The suite blocks unmocked HTTP access. Live compatibility checks are separate
and require explicit per-router credentials. No factory resets, firmware
upgrades, configuration writes, scans, WPS, or reboots are part of verification.

Licensed under [MIT](LICENSE). Not affiliated with Cudy.
