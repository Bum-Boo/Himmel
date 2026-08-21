from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from hermes_cli import restart_broker as rb


def _write_gateway_state(
    root: Path,
    profile: str,
    *,
    active_agents: int,
    pid: int = 123,
    updated_at: str | None = None,
) -> Path:
    home = root if profile == "default" else root / "profiles" / profile
    home.mkdir(parents=True, exist_ok=True)
    path = home / "gateway_state.json"
    path.write_text(json.dumps({
        "pid": pid,
        "gateway_state": "running",
        "active_agents": active_agents,
        "updated_at": updated_at or datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    return path


def _update_broker_config(root: Path, **changes) -> None:
    path = root / rb.DEFAULT_CONFIG_NAME
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_create_request_writes_valid_pending_json(tmp_path):
    path = rb.create_request(
        "friren",
        requested_by="profilemanager",
        reason="reload patch",
        root=tmp_path,
    )

    assert path.parent == tmp_path / "restart-requests" / "pending"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["profile"] == "friren"
    assert data["requested_by"] == "profilemanager"
    assert data["reason"] == "reload patch"
    assert data["nonce"]


@pytest.mark.parametrize("bad", ["../friren", "friren service", "", "x" * 65])
def test_create_request_rejects_unsafe_profile_names(tmp_path, bad):
    with pytest.raises(rb.RestartRequestRejected):
        rb.create_request(bad, requested_by="profilemanager", root=tmp_path)


def test_run_once_refuses_inside_gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("_HERMES_GATEWAY", "1")
    with pytest.raises(rb.RestartBrokerError, match="inside a gateway"):
        rb.run_once(root=tmp_path)


def test_run_once_dry_run_moves_allowed_request_to_done(tmp_path):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    request = rb.create_request("friren", requested_by="profilemanager", root=tmp_path)

    result = rb.run_once(root=tmp_path, dry_run=True, allow_in_gateway=True)

    assert len(result) == 1
    assert result[0]["status"] == "done"
    assert result[0]["action"]["unit"] == "hermes-gateway-friren.service"
    assert not request.exists()
    assert list((tmp_path / "restart-requests" / "done").glob("*.json"))
    status = json.loads((tmp_path / "restart-requests" / "status" / "friren.json").read_text())
    assert status["status"] == "done"


def test_run_once_rejects_not_allowlisted_request(tmp_path):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    rb.create_request("serie", requested_by="profilemanager", root=tmp_path)

    result = rb.run_once(root=tmp_path, dry_run=True, allow_in_gateway=True)

    assert result[0]["status"] == "failed"
    assert "not in allowed_profiles" in result[0]["error"]
    assert list((tmp_path / "restart-requests" / "failed").glob("*.json"))


def test_run_once_executes_systemctl_for_allowed_request(tmp_path, monkeypatch):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    rb.create_request("friren", requested_by="profilemanager", root=tmp_path)
    _write_gateway_state(tmp_path, "friren", active_agents=0)
    _update_broker_config(tmp_path, minimum_idle_seconds=0)
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, args, stdout=""):
            self.args = args
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ""

    def fake_run(args, **kwargs):
        calls.append(list(args))
        if "show" in args:
            return Completed(args, "ActiveState=active\nSubState=running\nMainPID=123\n")
        return Completed(args, "")

    monkeypatch.setattr(rb.subprocess, "run", fake_run)

    result = rb.run_once(root=tmp_path, allow_in_gateway=True)

    assert result[0]["status"] == "done"
    assert calls[0] == ["systemctl", "--user", "restart", "hermes-gateway-friren.service"]
    assert calls[1][:4] == ["systemctl", "--user", "show", "hermes-gateway-friren.service"]


def test_busy_gateway_defers_request_without_systemctl(tmp_path, monkeypatch):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    request = rb.create_request("friren", requested_by="profilemanager", root=tmp_path)
    _write_gateway_state(tmp_path, "friren", active_agents=2)
    monkeypatch.setattr(
        rb,
        "_restart_unit",
        lambda *a, **k: pytest.fail("busy gateway must not restart"),
    )

    result = rb.run_once(root=tmp_path, allow_in_gateway=True)

    assert result[0]["status"] == "deferred"
    assert result[0]["activity"]["active_agents"] == 2
    assert request.exists()
    assert not list((tmp_path / "restart-requests" / "done").glob("*.json"))


def test_missing_gateway_state_defers_request_fail_closed(tmp_path, monkeypatch):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    request = rb.create_request("friren", requested_by="profilemanager", root=tmp_path)
    monkeypatch.setattr(
        rb,
        "_restart_unit",
        lambda *a, **k: pytest.fail("missing activity state must not restart"),
    )

    result = rb.run_once(root=tmp_path, allow_in_gateway=True)

    assert result[0]["status"] == "deferred"
    assert result[0]["activity"]["available"] is False
    assert request.exists()


def test_request_runs_only_after_four_continuous_idle_minutes(tmp_path, monkeypatch):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    _update_broker_config(tmp_path, cooldown_seconds=0, minimum_idle_seconds=240)
    request = rb.create_request("friren", requested_by="profilemanager", root=tmp_path)
    updated = datetime.fromtimestamp(1_000, timezone.utc).isoformat()
    _write_gateway_state(
        tmp_path, "friren", active_agents=0, pid=321, updated_at=updated
    )
    calls = []
    monkeypatch.setattr(rb.time, "time", lambda: 1_100)
    monkeypatch.setattr(
        rb,
        "_restart_unit",
        lambda profile, config, dry_run=False: calls.append(profile) or {
            "unit": f"hermes-gateway-{profile}.service",
            "ok": True,
        },
    )

    first = rb.run_once(root=tmp_path, allow_in_gateway=True)
    assert first[0]["status"] == "deferred"
    assert first[0]["activity"]["idle_seconds"] == 100
    assert request.exists()
    assert calls == []

    monkeypatch.setattr(rb.time, "time", lambda: 1_241)
    second = rb.run_once(root=tmp_path, allow_in_gateway=True)
    assert second[0]["status"] == "done"
    assert calls == ["friren"]
    assert not request.exists()


def test_busy_observation_resets_idle_window(tmp_path):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    paths = rb.broker_paths(tmp_path)
    config = rb.load_config(tmp_path)
    _write_gateway_state(
        tmp_path,
        "friren",
        active_agents=0,
        pid=7,
        updated_at=datetime.fromtimestamp(1_000, timezone.utc).isoformat(),
    )
    ready, _ = rb._check_sustained_idle(paths, "friren", config, now=1_100)
    assert ready is False

    _write_gateway_state(tmp_path, "friren", active_agents=1, pid=7)
    ready, _ = rb._check_sustained_idle(paths, "friren", config, now=1_200)
    assert ready is False

    _write_gateway_state(
        tmp_path,
        "friren",
        active_agents=0,
        pid=7,
        updated_at=datetime.fromtimestamp(1_200, timezone.utc).isoformat(),
    )
    ready, activity = rb._check_sustained_idle(paths, "friren", config, now=1_300)
    assert ready is False
    assert activity["idle_seconds"] == 100


def test_activity_change_on_immediate_recheck_keeps_request_pending(tmp_path, monkeypatch):
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    _update_broker_config(tmp_path, cooldown_seconds=0)
    request = rb.create_request("friren", requested_by="profilemanager", root=tmp_path)
    observations = iter([
        (True, {"active_agents": 0, "idle_seconds": 240}),
        (False, {"active_agents": 1, "idle_seconds": 0}),
    ])
    monkeypatch.setattr(rb, "_check_sustained_idle", lambda *a, **k: next(observations))
    monkeypatch.setattr(
        rb,
        "_restart_unit",
        lambda *a, **k: pytest.fail("resumed work must block restart"),
    )

    result = rb.run_once(root=tmp_path, allow_in_gateway=True)

    assert result[0]["status"] == "deferred"
    assert result[0]["reason"] == "gateway activity changed before restart"
    assert request.exists()


def test_install_systemd_units_writes_timer_without_enabling(tmp_path):
    out = rb.install_systemd_units(
        root=tmp_path / "hermes-root",
        python="/venv/bin/python",
        unit_dir=tmp_path / "units",
        interval_seconds=17,
        enable_now=False,
    )

    service = Path(out["service"])
    timer = Path(out["timer"])
    assert service.exists()
    assert timer.exists()
    assert "hermes_cli.restart_broker --root" in service.read_text(encoding="utf-8")
    assert f"--root {tmp_path / 'hermes-root'} run-once" in service.read_text(encoding="utf-8")
    assert "OnUnitActiveSec=17s" in timer.read_text(encoding="utf-8")
    assert out["enabled"] is False


def test_write_default_config_is_conservative_and_preserves_existing(tmp_path):
    first = rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["friren"],
        allowed_requesters=["profilemanager"],
    )
    rb.write_default_config(
        root=tmp_path,
        allowed_profiles=["serie"],
        allowed_requesters=["serie"],
        force=False,
    )

    data = yaml.safe_load(first.read_text(encoding="utf-8"))
    assert data["enabled"] is True
    assert data["allowed_profiles"] == ["friren"]
    assert data["allowed_requesters"] == ["profilemanager"]
    assert data["allow_self_restart"] is True
    assert data["require_sustained_idle"] is True
    assert data["minimum_idle_seconds"] == 240
