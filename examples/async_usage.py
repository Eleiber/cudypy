"""Read one concurrent router snapshot with the async client."""

import asyncio
import os

from cudypy import AsyncCudyRouter, CudyAPIError


async def main() -> int:
    try:
        async with AsyncCudyRouter(
            os.environ["CUDY_ROUTER_URL"],
            password=os.environ.get("CUDY_ROUTER_PASSWORD"),
            auth_token=os.environ.get("CUDY_ROUTER_TOKEN"),
            salt=os.environ.get("CUDY_ROUTER_SALT"),
        ) as router:
            system, wan, devices = await asyncio.gather(
                router.get_system_status(),
                router.get_interface_status("wan"),
                router.get_devices(),
            )
            print("Model:", system.model)
            print("WAN up:", wan.is_up)
            print("Devices:", len(devices))
    except (KeyError, ValueError, CudyAPIError) as error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
