# Async client

`AsyncCudyRouter` uses `aiohttp` for nonblocking local HTTP requests. Install
the optional dependency with `python -m pip install -e ".[async]"` from this
repository. The existing `CudyRouter` remains synchronous.

```python
import asyncio
import os
from cudypy import AsyncCudyRouter

async def main():
    async with AsyncCudyRouter(
        os.environ["CUDY_ROUTER_URL"],
        auth_token=os.environ["CUDY_ROUTER_TOKEN"],
    ) as router:
        system, wan, devices = await asyncio.gather(
            router.get_system_status(),
            router.get_interface_status("wan"),
            router.get_devices(),
        )
        print(system.model, wan.is_up, len(devices))

asyncio.run(main())
```

These are three concurrent requests on one HTTP session. The router may
serialize work internally; concurrent client requests do not guarantee a faster
response. Reuse one `AsyncCudyRouter` within one event loop, and call `close()`
or use `async with` to release connections.

## Supported interface

The async client has coroutine versions of every public `CudyRouter` operation,
including configuration reads and writes. Each method is awaited. The
[API reference](api-reference.md) lists their arguments and return values;
`await router.call_api(method, params)` remains available for other RPCs.

Constructor arguments match `CudyRouter`. Token sessions bypass password
login and mDNS. Password sessions use
the same challenge/digest exchange. If no salt is given, discovery uses
Zeroconf's asyncio API. Explicit authentication failures return `False` from
`authenticate()`; reads raise `CudyAuthError` when login fails.

Known reads can retry once after an authentication rejection when a password
is available. Concurrent calls share a login lock, so they do not each start a
new login. Transport failures and writes are not replayed. Cancellation ends
the waiting coroutine and closes its in-flight HTTP response, but it does not
prove a router write did not happen. Do not automatically repeat a write after
cancellation or timeout.

The async and synchronous clients use the same [response models](models.md),
including `Device`, `SystemStatus`, `FirmwareRecord` and `ResponsePage`, and
the same library exceptions. See the [API reference](api-reference.md) for
method signatures and the
[protocol contract](protocol.md) for RPC behavior.

The installed async wheel was checked on a WR3000 V2.0: password login with
mDNS discovery, concurrent system/WAN/device reads, a broader set of passive
reads and an existing-token session succeeded. Firmware-specific unsupported
responses matched the synchronous compatibility results. Writes, session
expiry and selected argument forms remain untested on hardware; see
[compatibility](compatibility.md).
