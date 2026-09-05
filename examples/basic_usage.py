"""Read system information and clients using environment credentials."""

import os
from cudypy import CudyAPIError, CudyRouter


def main():
    try:
        with CudyRouter(
            os.environ["CUDY_ROUTER_URL"],
            password=os.environ.get("CUDY_ROUTER_PASSWORD"),
            auth_token=os.environ.get("CUDY_ROUTER_TOKEN"),
            salt=os.environ.get("CUDY_ROUTER_SALT"),
        ) as router:
            print(router.get_system_info())
            for device in router.get_devices():
                print(device)
    except (KeyError, ValueError, CudyAPIError) as error:
        print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
