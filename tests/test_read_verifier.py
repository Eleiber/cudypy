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
        for word in ["synthetic-private", "synthetic-secret", "private-section", "synthetic-token"]
    )
    methods = [call[0] for call in verifier.method_calls]
    assert all(name.startswith("get_") for name in methods)
    assert "get_mesh_device_page" not in methods
    assert "get_client_info" not in methods


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
