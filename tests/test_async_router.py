"""Offline contracts for the aiohttp client and concurrent reads."""

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest

from cudypy import AsyncCudyRouter, CudyAPIError, CudyAuthError, CudyRouter, CudyUnsupportedError
from zeroconf import ServiceStateChange


def run(coro):
    return asyncio.run(coro)


def test_public_router_methods_have_async_parity():
    sync_methods = {
        name: method
        for name, method in inspect.getmembers(CudyRouter, inspect.isfunction)
        if name.startswith(("get_", "set_", "clear_")) or name == "reboot"
    }
    for name, method in sync_methods.items():
        counterpart = getattr(AsyncCudyRouter, name)
        assert inspect.iscoroutinefunction(counterpart), name
        assert inspect.signature(counterpart) == inspect.signature(method), name


@pytest.mark.parametrize(
    "name,args,kwargs,result,expected_rpc",
    [
        ("get_client_names", (), {}, None, ("devices.get_name", None, True)),
        ("get_system_config", (), {}, {"hostname": "x"}, ("conf.get_system", None, True)),
        ("get_vpn_config", (), {}, {"vpn": {}}, ("conf.get_all", ["vpn", "config"], True)),
        ("get_wifi_scan_results", (), {}, None, ("wifi.get_aplist", [], True)),
        ("get_auto_reboot_config", (), {}, [], ("conf.get_autoreboot", None, True)),
        (
            "get_parental_control_config",
            ("family",),
            {},
            [],
            ("parental_control.get_conf", ["family"], True),
        ),
        ("get_cellular_status", ("wwan",), {}, {}, ("cellular.getstatus", ["wwan"], True)),
        (
            "get_client_rate_limit",
            ("AA-BB-CC-DD-EE-FF",),
            {},
            None,
            ("conf.get_rate_limit", ["aa:bb:cc:dd:ee:ff"], True),
        ),
        (
            "get_adshield_status",
            ("provider",),
            {},
            {},
            ("adshield.get_status", ["provider"], False),
        ),
        (
            "set_client_name",
            ("AA-BB-CC-DD-EE-FF", "desk"),
            {},
            None,
            ("devices.set_name", ["aa:bb:cc:dd:ee:ff", "desk", "other", "undefined"], False),
        ),
        (
            "set_client_rate_limit",
            ("AA-BB-CC-DD-EE-FF",),
            {"download_mbps": "1.25", "upload_mbps": "2"},
            True,
            ("devices.rate_limit", ["aa:bb:cc:dd:ee:ff", {"ddrate": "1.25", "uurate": "2"}], False),
        ),
        (
            "set_wifi_config",
            ({"iface": {"wifi0": {"disabled": False}}},),
            {},
            True,
            ("wifi.set_conf", [{"iface": {"wifi0": {"disabled": False}}}], False),
        ),
    ],
)
def test_async_method_matches_sync_rpc_contract(name, args, kwargs, result, expected_rpc):
    calls = []

    def sync_rpc(method, params=None, retry_auth=True):
        calls.append((method, params, retry_auth))
        return {"result": result}

    async def async_rpc(method, params=None, retry_auth=True):
        calls.append((method, params, retry_auth))
        return {"result": result}

    with CudyRouter("http://192.0.2.1", auth_token="synthetic") as sync_router:
        with patch.object(sync_router, "call_api", side_effect=sync_rpc):
            sync_result = getattr(sync_router, name)(*args, **kwargs)

    async def scenario():
        async with AsyncCudyRouter("http://192.0.2.1", auth_token="synthetic") as router:
            with patch.object(router, "call_api", side_effect=async_rpc):
                return await getattr(router, name)(*args, **kwargs)

    async_result = run(scenario())
    assert sync_result == async_result
    assert calls == [expected_rpc, expected_rpc]


def test_three_reads_overlap_and_share_one_session():
    async def scenario():
        async with AsyncCudyRouter("http://192.0.2.1", auth_token="token") as router:
            session = router._session
            arrived = 0
            all_arrived = asyncio.Event()

            async def rpc(path, method, params=None, *, authenticated=False):
                nonlocal arrived
                arrived += 1
                if arrived == 3:
                    all_arrived.set()
                await asyncio.wait_for(all_arrived.wait(), 1)
                if method == "system.info":
                    return {"result": {"model": "WR3000"}}
                if method == "net.iface_status":
                    return {"result": {"is_up": 1}}
                return {"result": {"devcnt": 0, "devlist": []}}

            with patch.object(router, "_rpc_request", side_effect=rpc):
                system, wan, devices = await asyncio.gather(
                    router.get_system_status(),
                    router.get_interface_status(),
                    router.get_devices(),
                )
            assert (system.model, wan.is_up, devices) == ("WR3000", True, [])
            assert router._session is session

    run(scenario())


def test_password_login_is_shared_by_concurrent_reads():
    async def scenario():
        async with AsyncCudyRouter("http://192.0.2.1", password="secret", salt="known") as router:
            calls = []

            async def rpc(path, method, params=None, *, authenticated=False):
                calls.append(method)
                if method == "token":
                    await asyncio.sleep(0)
                    return {"result": "challenge"}
                if method == "login":
                    return {"result": "session-token"}
                return {"result": {"model": "WR3000"}}

            with patch.object(router, "_rpc_request", side_effect=rpc):
                results = await asyncio.gather(
                    router.get_system_info(), router.get_system_info(), router.get_system_info()
                )
            assert len(results) == 3
            assert calls.count("token") == calls.count("login") == 1
            assert calls.count("system.info") == 3

    run(scenario())


def test_device_pagination_matches_sync_client():
    async def scenario():
        async with AsyncCudyRouter("http://192.0.2.1", auth_token="token") as router:
            first = {"result": {"devcnt": 2, "devlist": [{"macaddr": "020000000001"}]}}
            second = {"result": {"devcnt": 2, "devlist": [{"macaddr": "020000000002"}]}}
            with patch.object(router, "call_api", new_callable=AsyncMock) as rpc:
                rpc.side_effect = [first, second]
                devices = await router.get_devices()
                assert len(devices) == 2
                assert rpc.call_args_list[1].args == ("devices.get_devlist_ex", [2, 2])

    run(scenario())


def test_write_is_not_replayed_after_auth_rejection():
    async def scenario():
        async with AsyncCudyRouter(
            "http://192.0.2.1", password="secret", auth_token="old", salt="known"
        ) as router:
            with patch.object(
                router, "_rpc_request", new_callable=AsyncMock, side_effect=CudyAuthError("expired")
            ) as rpc:
                with pytest.raises(CudyAuthError):
                    await router.reboot()
                assert rpc.await_count == 1

    run(scenario())


def test_known_read_refreshes_only_once():
    async def scenario():
        async with AsyncCudyRouter(
            "http://192.0.2.1", password="secret", auth_token="old", salt="known"
        ) as router:
            calls = []

            async def rpc(path, method, params=None, *, authenticated=False):
                calls.append((method, router.auth_token))
                if method == "system.info" and router.auth_token == "old":
                    raise CudyAuthError("expired", code=-32003)
                if method == "token":
                    return {"result": "challenge"}
                if method == "login":
                    return {"result": "new-session-token"}
                return {"result": {"model": "WR3000"}}

            with patch.object(router, "_rpc_request", side_effect=rpc):
                result = await asyncio.gather(router.get_system_info(), router.get_system_info())
            assert len(result) == 2
            assert [m for m, _ in calls].count("login") == 1
            assert 3 <= [m for m, _ in calls].count("system.info") <= 4

    run(scenario())


def test_response_errors_and_closed_session():
    async def scenario():
        router = AsyncCudyRouter("http://192.0.2.1", auth_token="token")
        with patch.object(router, "_rpc_request", new_callable=AsyncMock) as rpc:
            rpc.return_value = {"result": None}
            with pytest.raises(CudyAPIError):
                await router.get_system_info()
            rpc.side_effect = CudyUnsupportedError("missing", code=-32601)
            with pytest.raises(CudyUnsupportedError) as error:
                await router.get_system_info()
            assert error.value.code == -32601
        await router.close()
        with pytest.raises(CudyAPIError, match="closed"):
            await router.get_system_info()

    run(scenario())


def test_transport_payload_query_and_rpc_error_mapping():
    class Response:
        def __init__(self, body, status=200):
            self.body = body
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def json(self, **kwargs):
            return self.body

    class Session:
        def __init__(self):
            self.calls = []
            self.response = Response({"result": {"model": "WR3000"}})

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return self.response

        async def close(self):
            return None

    async def scenario():
        router = AsyncCudyRouter("http://192.0.2.1", auth_token="token")
        router._session = Session()
        assert (await router.get_system_info()).model == "WR3000"
        url, kwargs = router._session.calls[-1]
        assert url.endswith("/cgi-bin/luci/rpc/app")
        assert kwargs["json"] == {"method": "system.info", "params": []}
        assert kwargs["params"] == {"auth": "token"}
        assert kwargs["allow_redirects"] is False
        router._session.response = Response({"error": {"code": -32601}})
        with pytest.raises(CudyUnsupportedError) as error:
            await router.get_system_info()
        assert error.value.code == -32601
        router._session.response = Response({"result": {}}, status=302)
        with pytest.raises(CudyAPIError, match="redirect"):
            await router.get_system_info()
        await router.close()

    run(scenario())


def test_async_mdns_discovers_salt_and_closes_resources():
    class Info:
        properties = {b"salt": b"known-salt"}

        def parsed_addresses(self):
            return ["192.0.2.1"]

    class Zeroconf:
        zeroconf = object()
        closed = False

        async def async_get_service_info(self, type_, name, timeout):
            return Info()

        async def async_close(self):
            self.closed = True

    class Browser:
        cancelled = False

        def __init__(self, zeroconf, type_, handlers):
            handlers[0](
                zeroconf=zeroconf,
                service_type=type_,
                name="router.local.",
                state_change=ServiceStateChange.Added,
            )

        async def async_cancel(self):
            self.cancelled = True

    async def scenario():
        router = AsyncCudyRouter("http://192.0.2.1", password="secret")
        zc = Zeroconf()
        browser = Browser
        with patch("zeroconf.asyncio.AsyncZeroconf", return_value=zc):
            with patch("zeroconf.asyncio.AsyncServiceBrowser", browser):
                await router._discover_salt()
        assert router.salt == "known-salt"
        assert zc.closed
        await router.close()

    run(scenario())
