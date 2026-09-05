# Async feasibility

`CudyRouter` is synchronous: HTTP requests, authentication and discovery block
the calling thread. Browser `fetch` does not make the Python library async.
There is no `AsyncCudyRouter` today.

For an occasional asyncio read, use a worker that owns its entire client:

```python
import asyncio
import os
from cudypy import CudyRouter

def read_snapshot():
    with CudyRouter(os.environ["CUDY_ROUTER_URL"],
                    auth_token=os.environ["CUDY_ROUTER_TOKEN"]) as router:
        return router.get_devices()

async def main():
    devices = await asyncio.to_thread(read_snapshot)
    print(len(devices))

asyncio.run(main())
```

This avoids blocking the event loop, but is not native async I/O or long-lived
session reuse. Do not start unbounded workers or concurrently share one
`CudyRouter`: its session, cookies and authentication state are mutable.
Cancelling an await does not undo a request already running; the worker owns
cleanup. Never blindly retry a mutation after cancellation or timeout.

A separate native async client is feasible while preserving the synchronous
API. Models, validation and response parsing can be shared. It would need an
async HTTP transport, async context management/close, coordinated authentication
refresh, bounded concurrency, async discovery or an isolated blocking discovery
path, and cancellation/no-replay tests. Token sessions are the simplest first
step; password/mDNS paths must preserve cleanup and retry guarantees.

Async keeps an application responsive during I/O, especially across multiple
routers. It does not speed up one router, fix network routing, or increase the
router's safe request capacity.

References: [Python to_thread](https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread)
and [HTTPX async lifecycle](https://www.python-httpx.org/async/). This is a design
assessment, not an implemented native async client.
