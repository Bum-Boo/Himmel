"""Generated service behavior for the opt-in systemd watchdog."""

from __future__ import annotations

from gateway.config import GatewayConfig
from hermes_cli import gateway as gateway_cli




def test_positive_watchdog_config_generates_notify_unit(monkeypatch):
    monkeypatch.setattr(
        gateway_cli,
        "load_gateway_config",
        lambda: GatewayConfig.from_dict({"systemd_watchdog_seconds": 120}),
        raising=False,
    )

    unit = gateway_cli.generate_systemd_unit(system=False)

    assert "Type=notify" in unit
    assert "NotifyAccess=main" in unit
    assert "WatchdogSec=120s" in unit






def test_system_unit_reads_watchdog_from_target_home(tmp_path, monkeypatch):
    caller_home = tmp_path / "caller"
    target_home = tmp_path / "target"
    caller_home.mkdir()
    target_home.mkdir()
    (caller_home / "config.yaml").write_text(
        "gateway:\n  systemd_watchdog_seconds: 0\n",
        encoding="utf-8",
    )
    (target_home / "config.yaml").write_text(
        "gateway:\n  systemd_watchdog_seconds: 75\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HERMES_HOME", str(caller_home))
    monkeypatch.setattr(
        gateway_cli,
        "_system_service_identity",
        lambda _user: ("service", "service", str(tmp_path / "account")),
    )
    monkeypatch.setattr(
        gateway_cli,
        "_hermes_home_for_target_user",
        lambda _home: str(target_home),
    )

    unit = gateway_cli.generate_systemd_unit(system=True, run_as_user="service")

    assert "Type=notify" in unit
    assert "WatchdogSec=75s" in unit


def _point_system_unit_at(monkeypatch, tmp_path, target_hermes):
    caller_home = tmp_path / "caller"
    caller_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(caller_home))
    monkeypatch.setattr(
        gateway_cli,
        "_system_service_identity",
        lambda _user: ("service", "service", str(target_hermes.parent)),
    )
    monkeypatch.setattr(
        gateway_cli,
        "_hermes_home_for_target_user",
        lambda _home: str(target_hermes),
    )


def test_system_unit_does_not_create_missing_target_home(tmp_path, monkeypatch):
    # System units are generated under sudo; creating the service user's
    # HERMES_HOME here leaves it root-owned 0700 and unusable by the service.
    target_hermes = tmp_path / "account" / ".hermes"
    _point_system_unit_at(monkeypatch, tmp_path, target_hermes)

    unit = gateway_cli.generate_systemd_unit(system=True, run_as_user="service")

    assert "Type=simple" in unit
    assert not target_hermes.exists()


def test_system_unit_watchdog_lookup_does_not_load_target_plugins(tmp_path, monkeypatch):
    target_hermes = tmp_path / "account" / ".hermes"
    plugin_dir = target_hermes / "plugins" / "canary"
    plugin_dir.mkdir(parents=True)
    imported = tmp_path / "canary-imported"
    (plugin_dir / "plugin.yaml").write_text("name: canary\nversion: 0.0.1\n", encoding="utf-8")
    (plugin_dir / "__init__.py").write_text(
        f"open({str(imported)!r}, 'w').write('x')\n\ndef register(ctx):\n    pass\n",
        encoding="utf-8",
    )
    (target_hermes / "config.yaml").write_text(
        "gateway:\n  systemd_watchdog_seconds: 45\nplugins:\n  enabled: [canary]\n",
        encoding="utf-8",
    )
    before = sorted(p.relative_to(target_hermes) for p in target_hermes.rglob("*"))
    _point_system_unit_at(monkeypatch, tmp_path, target_hermes)

    unit = gateway_cli.generate_systemd_unit(system=True, run_as_user="service")

    assert "WatchdogSec=45s" in unit
    assert not imported.exists(), "service user's plugin code ran in the installer process"
    assert sorted(p.relative_to(target_hermes) for p in target_hermes.rglob("*")) == before
