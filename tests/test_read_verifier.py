"""The compatibility CLI must report shapes, not private configuration."""

import json
from unittest.mock import MagicMock

import pytest

from cudypy import CudyAuthError, CudyUnsupportedError
from tools import verify_read_only


@pytest.fixture
def verifier(monkeypatch, tmp_path):
    token_file = tmp_path / "token"
    token_file.write_text("synthetic-token", encoding="utf-8")
    router = MagicMock()
    router.__enter__.return_value = router
    router.get_system_info.return_value = {"firmware": "synthetic-private"}
    router.get_devices.return_value = []
    router.get_wireless_config.return_value = {"private-section": {"key": "synthetic-secret"}}
    router.get_ddns_config.return_value = {"password": "synthetic-ddns-secret"}
    router.get_vpn_profiles.return_value = {"clients": [{"key": "synthetic-vpn-secret"}]}
    router.get_adshield_config.return_value = {"adguard": {"token": "synthetic-ad-secret"}}
    monkeypatch.setattr(verify_read_only, "CudyRouter", MagicMock(return_value=router))
    monkeypatch.setattr(
        "sys.argv",
        [
            "verify",
            "--url",
            "http://192.0.2.1",
            "--token-file",
            str(token_file),
            "--include-config",
        ],
    )
    return router


def test_verifier_reports_shapes_without_values(verifier, capsys):
    assert verify_read_only.main() == 0
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["wireless_config"]["type"] == "object"
    assert all(
        word not in output
        for word in [
            "synthetic-private",
            "synthetic-secret",
            "private-section",
            "synthetic-token",
            "synthetic-ddns-secret",
            "synthetic-vpn-secret",
            "synthetic-ad-secret",
        ]
    )
    methods = [call[0] for call in verifier.method_calls]
    assert all(name.startswith("get_") for name in methods)
    assert "get_mesh_device_page" not in methods
    assert "get_client_info" not in methods
    verifier.get_ddns_config.assert_called_once_with()
    verifier.get_auto_reboot_config.assert_called_once_with()
    verifier.get_client_traffic_page.assert_called_once_with()
    verifier.get_wifi_scan_results.assert_called_once_with()
    verifier.get_parental_control_config.assert_called_once_with()
    verifier.get_multi_ssid_interfaces.assert_called_once_with()
    verifier.get_multi_ssid_config.assert_not_called()
    verifier.get_vpn_profiles.assert_called_once_with()
    verifier.get_online_interfaces.assert_called_once_with()
    verifier.get_vpn_client_config.assert_not_called()
    verifier.get_vpn_connection_page.assert_not_called()
    verifier.get_adshield_config.assert_called_once_with()
    verifier.get_adshield_providers.assert_called_once_with()
    verifier.get_adshield_status.assert_not_called()
    verifier.get_adshield_stats.assert_not_called()


def test_configuration_reads_are_opt_in(verifier, monkeypatch, capsys):
    import sys

    monkeypatch.setattr(sys, "argv", [arg for arg in sys.argv if arg != "--include-config"])
    assert verify_read_only.main() == 0
    verifier.get_ddns_config.assert_not_called()
    verifier.get_default_config.assert_not_called()
    verifier.get_vpn_profiles.assert_not_called()
    verifier.get_adshield_config.assert_not_called()
    verifier.get_adshield_providers.assert_not_called()
    verifier.get_iptv_config.assert_not_called()
    verifier.get_easymesh_config.assert_not_called()
    verifier.get_parental_control_config.assert_not_called()
    verifier.get_multi_ssid_interfaces.assert_not_called()
    verifier.get_auto_reboot_config.assert_not_called()


def test_optional_unsupported_read_does_not_claim_success(verifier, capsys):
    verifier.get_vpn_status.side_effect = CudyUnsupportedError("Unsupported", code=-32601)
    assert verify_read_only.main() == 0
    assert json.loads(capsys.readouterr().out)["vpn_status"] == {
        "ok": False,
        "error": "Unsupported",
        "code": -32601,
    }


def test_expired_session_stops_without_login(verifier, capsys):
    verifier.get_system_info.side_effect = CudyAuthError("synthetic-private")
    assert verify_read_only.main() == 1
    assert "synthetic-private" not in capsys.readouterr().out
    verifier.authenticate.assert_not_called()
    verifier.get_devices.assert_not_called()
