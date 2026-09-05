"""Full getter inventory and object-mapping contracts, using synthetic data."""

import inspect
from unittest.mock import patch

import pytest

from cudypy import (
    AccessPoint,
    ClientName,
    ClientTraffic,
    Configuration,
    ConfigurationSections,
    CudyAPIError,
    CudyAuthError,
    CudyRouter,
    CudyUnsupportedError,
    FirmwareRecord,
    ParentalGroup,
    ProviderCatalog,
    ResponsePage,
    WdsStatus,
    WorkMode,
)

RECORDS = {
    "get_system_config": ((), Configuration),
    "get_ipv6_config": ((), Configuration),
    "get_default_config": ((), Configuration),
    "get_ddns_config": ((), Configuration),
    "get_connectivity_check_config": ((), Configuration),
    "get_auto_reboot_config": ((), Configuration),
    "get_iptv_config": ((), Configuration),
    "get_easymesh_config": ((), Configuration),
    "get_vpn_config": ((), Configuration),
    "get_vpn_profiles": (("clients",), Configuration),
    "get_vpn_client_config": (("synthetic-id",), Configuration),
    "get_dhcp_config": ((), ConfigurationSections),
    "get_wireless_config": ((), ConfigurationSections),
    "get_cellular_status": (("modem",), FirmwareRecord),
    "get_cellular_statistics": (("modem",), FirmwareRecord),
    "get_adshield_providers": ((), ProviderCatalog),
    "get_adshield_config": ((), Configuration),
    "get_adshield_status": (("provider",), FirmwareRecord),
    "get_adshield_stats": (("provider",), FirmwareRecord),
    "get_wifi_frequencies": ((), FirmwareRecord),
    "get_wds_status": (("radio",), WdsStatus),
    "get_firmware_update_info": ((), FirmwareRecord),
}
LISTS = {
    "get_client_names": ((), ClientName),
    "get_legacy_devices": ((), FirmwareRecord),
    "get_work_modes": ((), WorkMode),
    "get_wifi_schedule": ((), Configuration),
    "get_client_internet_schedule": (("020000000001",), Configuration),
    "get_wifi_scan_results": (("radio",), AccessPoint),
    "get_parental_control_config": (("group",), ParentalGroup),
    "get_cellular_data_config": (("modem",), Configuration),
}
PASSTHROUGH = {
    "get_system_status": ((), "get_system_status"),
    "get_system_info": ((), "get_system_status"),
    "get_interface_status": (("lan",), "get_interface_status"),
    "get_network_status": (("lan",), "get_interface_status"),
    "get_devices": ((), "get_devices"),
    "get_online_devices": ((), "get_online_devices"),
    "get_wifi_devices": ((), "get_wifi_devices"),
    "get_ethernet_devices": ((), "get_ethernet_devices"),
    "get_device_by_mac": (("020000000001",), "get_device_by_mac"),
    "get_device_by_ip": (("192.0.2.1",), "get_device_by_ip"),
    "get_device_by_hostname": (("synthetic", True), "get_device_by_hostname"),
    "get_client_info": (("020000000001",), "get_client_info"),
    "get_client_rate_limit": (("020000000001",), "get_client_rate_limit"),
    "get_ethernet_ports": ((), "get_ethernet_ports"),
    "get_ethernet_status": ((), "get_ethernet_ports"),
    "get_lan_config": ((), "get_lan_config"),
    "get_wireless_interface": (("section",), "get_wireless_interface"),
    "get_wps_status": ((), "get_wps_status"),
    "get_firmware_check_status": (("target",), "get_firmware_check_status"),
    "get_apply_status": ((), "get_apply_status"),
    "get_online_interfaces": ((), "get_online_interfaces"),
    "get_multi_ssid_interfaces": ((), "get_multi_ssid_interfaces"),
}
DYNAMIC = {
    "get_supported_features",
    "get_mesh_clients",
    "get_traffic_stats",
    "get_vpn_status",
    "get_qos_config",
}
PAGES = {
    "get_client_traffic_page": ((2,), "devlist", "devcnt", ClientTraffic),
    "get_mesh_device_page": (("node", 2), "devlist", "devcnt", FirmwareRecord),
    "get_vpn_connection_page": (("vpn", 2), "connection_list", "total_cnt", FirmwareRecord),
}


@pytest.fixture
def router():
    with CudyRouter("http://192.0.2.1", auth_token="synthetic-token") as value:
        yield value


def test_every_public_getter_is_covered_and_preserves_parameters():
    readers = {name for name in vars(CudyRouter) if name.startswith("get_")}
    assert readers == set(RECORDS) | set(LISTS) | set(PASSTHROUGH) | DYNAMIC | set(PAGES) | {
        "get_multi_ssid_config"
    }
    for name in readers:
        private = "_read_" + name[4:]
        if hasattr(CudyRouter, private):
            original = inspect.signature(getattr(CudyRouter, private)).parameters
            public = inspect.signature(getattr(CudyRouter, name)).parameters
            assert list(original) == list(public)
            for key in original:
                assert original[key].default == public[key].default
                assert original[key].kind == public[key].kind


def test_models_are_default_and_no_facade_is_exposed(router):
    import cudypy

    assert not hasattr(router, "objects")
    assert not hasattr(cudypy, "RouterObjects")
    with patch.object(router, "call_api", return_value={"result": {"model": "Synthetic"}}):
        assert isinstance(router.get_system_info(), cudypy.SystemStatus)
        assert router.get_system_info().model == "Synthetic"
        assert router.call_api("system.info")["result"] == {"model": "Synthetic"}


@pytest.mark.parametrize(
    "primary,alias,rpc,payload",
    [
        ("get_system_info", "get_system_status", "system.info", {"uptime": "10"}),
        ("get_network_status", "get_interface_status", "net.iface_status", {"is_up": "1"}),
        ("get_ethernet_status", "get_ethernet_ports", "eth.getstatus", [{"port": 1}]),
    ],
)
def test_model_aliases_do_not_duplicate_requests(router, primary, alias, rpc, payload):
    with patch.object(router, "call_api", return_value={"result": payload}) as call:
        first = getattr(router, primary)()
        call.assert_called_once()
        assert call.call_args.args[0] == rpc
        call.reset_mock()
        second = getattr(router, alias)()
        call.assert_called_once()
        assert type(first) is type(second) and first == second


@pytest.mark.parametrize("name", RECORDS)
def test_object_readers_preserve_and_deserialize(router, name):
    args, model = RECORDS[name]
    source = {"future": {"records": [{"value": False}], "nullable": None}}
    with patch.object(router, "_read_" + name[4:], return_value=source) as read:
        result = getattr(router, name)(*args)
        assert isinstance(result, model)
        assert result.future.records[0].value is False
        assert result.future.nullable is None
        assert result.raw == source
        result.raw["future"]["records"].clear()
        assert len(result.future.records) == 1
        read.assert_called_once_with(*args)


@pytest.mark.parametrize("name", LISTS)
def test_record_lists(router, name):
    args, model = LISTS[name]
    with patch.object(router, "_read_" + name[4:], return_value=[{"future": [0]}]) as read:
        result = getattr(router, name)(*args)
        assert len(result) == 1 and isinstance(result[0], model)
        assert result[0].future == (0,)
        read.assert_called_once_with(*args)


@pytest.mark.parametrize("name", DYNAMIC)
@pytest.mark.parametrize("value", [None, False, 0, "future-state", [], {}, [{"enabled": "0"}]])
def test_unknown_result_shapes_remain_distinct(router, name, value):
    with patch.object(router, "_read_" + name[4:], return_value=value) as read:
        result = getattr(router, name)()
        if isinstance(value, dict):
            assert isinstance(result, FirmwareRecord) and result.raw == value
        elif isinstance(value, list):
            assert isinstance(result, tuple) and len(result) == len(value)
            if value:
                assert isinstance(result[0], FirmwareRecord)
                assert result[0].enabled == "0"  # Never generic boolean guessing.
        else:
            assert type(result) is type(value) and result == value
        read.assert_called_once_with()


@pytest.mark.parametrize("name", PAGES)
def test_pages_keep_metadata_and_do_not_fetch_more(router, name):
    args, entries_key, count_key, model = PAGES[name]
    source = {entries_key: [{"future": True}], count_key: 101, "extra": {"x": 0}}
    with patch.object(router, "_read_" + name[4:], return_value=source) as read:
        page = getattr(router, name)(*args)
        assert isinstance(page, ResponsePage)
        assert page.total_count == 101
        assert len(page.entries) == 1 and isinstance(page.entries[0], model)
        assert page.extra.x == 0 and page.raw == source
        read.assert_called_once_with(*args)


@pytest.mark.parametrize(
    "name,args",
    [
        ("get_wds_status", (None,)),
        ("get_wifi_scan_results", (None,)),
        ("get_firmware_update_info", ()),
        ("get_auto_reboot_config", ()),
        ("get_multi_ssid_config", ("section",)),
    ],
)
def test_optional_reads_preserve_none(router, name, args):
    with patch.object(router, "_read_" + name[4:], return_value=None):
        assert getattr(router, name)(*args) is None


def test_multi_ssid_uses_existing_wireless_model(router):
    with patch.object(
        router, "_read_multi_ssid_config", return_value={"ssid": "Synthetic", "disabled": "0"}
    ) as read:
        result = router.get_multi_ssid_config("selected")
        assert result.section == "selected" and result.ssid == "Synthetic"
        assert result.disabled is False
        read.assert_called_once_with("selected")


def test_known_fields_are_normalized_and_unknown_fields_preserved(router):
    with patch.object(
        router,
        "_read_client_traffic_page",
        return_value={
            "devlist": [{"upspeed": "0", "downspeed": "42", "inbytes": 2**60}],
            "devcnt": 1,
        },
    ):
        entry = router.get_client_traffic_page().entries[0]
        assert entry.upload_bytes_per_second == 0
        assert entry.download_bytes_per_second == 42
        assert entry.reported_inbytes == 2**60 and entry.reported_outbytes is None
    assert WorkMode({"mode": "ap"}).mode == "ap"
    assert WorkMode({}).name is None
    assert ClientName({"macaddr": "020000000001"}).mac_address == "020000000001"
    assert WdsStatus({"up": "0"}).is_up is False
    assert ProviderCatalog({"providers": ["future"]}).providers == ("future",)


@pytest.mark.parametrize(
    "name,value",
    [
        ("get_work_modes", [{"mode": 1}]),
        ("get_client_names", [{"name": False}]),
        ("get_adshield_providers", {"providers": [1]}),
        ("get_client_traffic_page", {"devlist": [{"upspeed": True}]}),
    ],
)
def test_known_fields_are_validated_before_return(router, name, value):
    with patch.object(router, "_read_" + name[4:], return_value=value):
        with pytest.raises(CudyAPIError, match="Malformed response model"):
            getattr(router, name)()


def test_records_are_detached_and_reserved_keys_remain_accessible():
    source = {"raw": "synthetic-secret", "items": [{"value": 1}], "future-field": 0}
    record = FirmwareRecord(source)
    source["items"][0]["value"] = 2
    assert record["items"][0].value == 1
    assert record["raw"] == "synthetic-secret"
    assert record["future-field"] == 0
    assert "synthetic-secret" not in repr(record)
    with pytest.raises(AttributeError):
        record.missing
    with pytest.raises(KeyError):
        record["missing"]
    with pytest.raises(AttributeError):
        record.new_value = 1


def test_dynamic_section_selection_is_local():
    sections = ConfigurationSections({"arbitrary-section": {"enabled": "0"}})
    assert sections.section("arbitrary-section").enabled == "0"
    assert sections.section("absent") is None
    with pytest.raises(ValueError):
        ConfigurationSections({"bad": []}).section("bad")


@pytest.mark.parametrize(
    "error", [CudyAuthError("expired"), CudyUnsupportedError("unsupported", code=-32601)]
)
def test_errors_propagate_without_fallback_or_retry(router, error):
    with patch.object(router, "_read_system_config", side_effect=error) as read:
        with pytest.raises(type(error)) as caught:
            router.get_system_config()
        assert caught.value is error
        read.assert_called_once_with()


def test_provider_reads_keep_no_reauthentication_rule():
    with CudyRouter("http://192.0.2.1", password="synthetic", auth_token="old") as router:
        with patch.object(router, "_rpc_request", side_effect=CudyAuthError("expired")) as rpc:
            with patch.object(router, "authenticate") as auth:
                with pytest.raises(CudyAuthError):
                    router.get_adshield_status("future")
                rpc.assert_called_once()
                auth.assert_not_called()


def test_closed_owner_cannot_be_bypassed(router):
    objects = router
    router.close()
    with pytest.raises(CudyAPIError):
        objects.get_system_config()


def test_invalid_arguments_still_fail_without_http(router):
    with patch.object(router.session, "post") as post:
        with pytest.raises(ValueError):
            router.get_cellular_status("")
        with pytest.raises(ValueError):
            router.get_client_traffic_page(0)
        post.assert_not_called()


@pytest.mark.parametrize(
    "reader,args,rpc,params,payload",
    [
        ("get_system_config", (), "conf.get_system", [], {"future": {"x": 1}}),
        ("get_client_names", (), "devices.get_name", [], [{"name": "Synthetic"}]),
        ("get_vpn_profiles", ("clients",), "vpn.get_conf", ["clients"], {"clients": []}),
        (
            "get_client_traffic_page",
            (2,),
            "devices.traffic_stat",
            [101, 200],
            {"devlist": [], "devcnt": 0},
        ),
        (
            "get_cellular_statistics",
            ("modem",),
            "cellular.get_statistics",
            ["modem"],
            {"cur_traffic": 0},
        ),
        (
            "get_adshield_status",
            ("provider",),
            "adshield.get_status",
            ["provider"],
            {"provider": {"code": 401}},
        ),
        ("get_wifi_scan_results", (None,), "wifi.get_aplist", [], None),
        ("get_auto_reboot_config", (), "conf.get_autoreboot", [], []),
    ],
)
def test_object_readers_use_original_wire_contract(router, reader, args, rpc, params, payload):
    with patch.object(router.session, "post") as post:
        post.return_value.json.return_value = {"result": payload}
        value = getattr(router, reader)(*args)
        post.assert_called_once()
        assert post.call_args.kwargs["json"] == {"method": rpc, "params": params}
        if reader in ("get_wifi_scan_results", "get_auto_reboot_config"):
            assert value is None
        if reader == "get_adshield_status":
            assert value.provider.code == 401  # Provider failures aren't flattened away.


@pytest.mark.parametrize("reader", DYNAMIC)
def test_non_json_custom_results_have_sanitized_error(router, reader):
    with patch.object(router, "_read_" + reader[4:], return_value=object()):
        with pytest.raises(CudyAPIError, match="Malformed response model"):
            getattr(router, reader)()
