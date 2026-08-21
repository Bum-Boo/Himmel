"""Out-of-process gateway restart broker.

The terminal and cron guards intentionally block raw gateway lifecycle commands
from inside a running gateway process.  A gateway that runs
``systemctl --user restart hermes-gateway-<profile>.service`` kills its own
subprocess before the command can complete, which can create SIGTERM-respawn
loops.

This module provides a safer two-step contract:

1. A gateway/profile writes a validated restart request JSON file.
2. An external broker process (systemd timer/service, not a gateway child)
   consumes the request and performs the restart.

The request writer is safe to run from inside a gateway.  The broker refuses to
run from inside a gateway unless explicitly bypassed for tests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from hermes_constants import get_default_hermes_root

_PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
REQUEST_SCHEMA_VERSION = 1
DEFAULT_CONFIG_NAME = "restart-broker.yaml"


class RestartBrokerError(RuntimeError):
    """Base error for restart broker failures."""


class RestartRequestRejected(RestartBrokerError):
    """Raised when a request is invalid or not allowed by policy."""


@dataclass(frozen=True)
class BrokerPaths:
    root: Path
    request_root: Path
    pending: Path
    done: Path
    failed: Path
    status: Path
    idle: Path
    config: Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _validate_profile_name(name: str, *, field: str = "profile") -> str:
    value = str(name or "").strip()
    if not _PROFILE_RE.fullmatch(value):
        raise RestartRequestRejected(
            f"Invalid {field}: {value!r}. Allowed: letters, numbers, '_', '.', '-' up to 64 chars."
        )
    return value


def resolve_root(root: str | Path | None = None) -> Path:
    """Return the Hermes root used for shared profile-level broker state."""
    if root:
        return Path(root).expanduser().resolve()
    return get_default_hermes_root().expanduser().resolve()


def broker_paths(root: str | Path | None = None) -> BrokerPaths:
    base = resolve_root(root)
    request_root = base / "restart-requests"
    return BrokerPaths(
        root=base,
        request_root=request_root,
        pending=request_root / "pending",
        done=request_root / "done",
        failed=request_root / "failed",
        status=request_root / "status",
        idle=request_root / "idle",
        config=base / DEFAULT_CONFIG_NAME,
    )


def ensure_dirs(paths: BrokerPaths) -> None:
    for directory in (
        paths.request_root,
        paths.pending,
        paths.done,
        paths.failed,
        paths.status,
        paths.idle,
    ):
        directory.mkdir(parents=True, exist_ok=True)
        try:
            directory.chmod(0o700)
        except OSError:
            pass


def load_config(root: str | Path | None = None) -> dict[str, Any]:
    paths = broker_paths(root)
    if not paths.config.exists():
        return {
            "enabled": False,
            "allowed_profiles": [],
            "allowed_requesters": [],
            "allow_self_restart": False,
            "cooldown_seconds": 30,
            "max_request_age_seconds": 3600,
            "require_sustained_idle": True,
            "minimum_idle_seconds": 240,
            "systemctl_scope": "user",
        }
    data = yaml.safe_load(paths.config.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RestartBrokerError(f"Invalid broker config: {paths.config}")
    return data


def _list_config(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def write_default_config(
    *,
    root: str | Path | None = None,
    allowed_profiles: Iterable[str],
    allowed_requesters: Iterable[str] | None = None,
    force: bool = False,
) -> Path:
    """Create a conservative broker config file.

    Existing configs are left untouched unless ``force`` is true.
    """
    paths = broker_paths(root)
    ensure_dirs(paths)
    if paths.config.exists() and not force:
        return paths.config
    profiles = [_validate_profile_name(p) for p in allowed_profiles]
    requesters = [
        _validate_profile_name(r, field="requester")
        for r in (allowed_requesters if allowed_requesters is not None else profiles)
    ]
    cfg = {
        "enabled": True,
        "allowed_profiles": profiles,
        "allowed_requesters": requesters,
        "allow_self_restart": True,
        "cooldown_seconds": 30,
        "max_request_age_seconds": 3600,
        "require_sustained_idle": True,
        "minimum_idle_seconds": 240,
        "systemctl_scope": "user",
    }
    tmp = paths.config.with_suffix(paths.config.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(paths.config)
    try:
        paths.config.chmod(0o600)
    except OSError:
        pass
    return paths.config


def create_request(
    profile: str,
    *,
    requested_by: str,
    reason: str = "",
    root: str | Path | None = None,
) -> Path:
    """Write a restart request and return its path."""
    target = _validate_profile_name(profile)
    requester = _validate_profile_name(requested_by, field="requested_by")
    paths = broker_paths(root)
    ensure_dirs(paths)
    nonce = secrets.token_hex(8)
    payload = {
        "schema_version": REQUEST_SCHEMA_VERSION,
        "profile": target,
        "requested_by": requester,
        "reason": str(reason or "")[:500],
        "created_at": _utc_now(),
        "nonce": nonce,
    }
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{requester}-to-{target}-{nonce}.json"
    final = paths.pending / filename
    tmp = paths.pending / f".{filename}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(final)
    try:
        final.chmod(0o600)
    except OSError:
        pass
    return final


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _status_file(paths: BrokerPaths, profile: str) -> Path:
    return paths.status / f"{profile}.json"


def _idle_file(paths: BrokerPaths, profile: str) -> Path:
    return paths.idle / f"{profile}.json"


def _profile_gateway_state_file(paths: BrokerPaths, profile: str) -> Path:
    if profile == "default":
        return paths.root / "gateway_state.json"
    return paths.root / "profiles" / profile / "gateway_state.json"


def _read_gateway_activity(paths: BrokerPaths, profile: str) -> dict[str, Any]:
    """Read the profile's public gateway activity snapshot, failing closed."""
    state_path = _profile_gateway_state_file(paths, profile)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise TypeError("gateway state is not an object")
        active_agents = int(state.get("active_agents"))
        pid = int(state.get("pid") or 0)
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "active_agents": None,
            "pid": 0,
            "gateway_state": None,
            "state_file": str(state_path),
            "reason": f"gateway activity unavailable: {type(exc).__name__}",
        }
    return {
        "available": True,
        "active_agents": active_agents,
        "pid": pid,
        "gateway_state": state.get("gateway_state"),
        "state_file": str(state_path),
        "updated_at": state.get("updated_at"),
    }


def _write_idle_state(paths: BrokerPaths, profile: str, state: dict[str, Any]) -> None:
    ensure_dirs(paths)
    target = _idle_file(paths, profile)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(target)


def _load_idle_state(paths: BrokerPaths, profile: str) -> dict[str, Any]:
    try:
        state = json.loads(_idle_file(paths, profile).read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def _clear_idle_state(paths: BrokerPaths, profile: str) -> None:
    try:
        _idle_file(paths, profile).unlink()
    except FileNotFoundError:
        pass


def _check_sustained_idle(
    paths: BrokerPaths,
    profile: str,
    config: dict[str, Any],
    *,
    now: float | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Require active_agents=0 for a continuous configured interval.

    Missing or malformed activity state fails closed. A busy observation,
    gateway PID change, or non-running gateway resets the idle window.
    """
    observed_at = time.time() if now is None else float(now)
    minimum = max(0, int(config.get("minimum_idle_seconds", 240) or 0))
    activity = _read_gateway_activity(paths, profile)
    previous = _load_idle_state(paths, profile)
    same_pid = int(previous.get("pid") or 0) == int(activity.get("pid") or 0)
    running = activity.get("gateway_state") == "running"
    idle_now = bool(
        activity.get("available")
        and running
        and activity.get("active_agents") == 0
    )

    if not idle_now:
        state = {
            "profile": profile,
            "pid": int(activity.get("pid") or 0),
            "idle_since": None,
            "last_observed_at": observed_at,
            "active_agents": activity.get("active_agents"),
            "reason": activity.get("reason") or (
                "gateway is not running" if not running else "gateway has active agents"
            ),
        }
        _write_idle_state(paths, profile, state)
        return False, {
            **activity,
            "minimum_idle_seconds": minimum,
            "idle_seconds": 0,
        }

    idle_since = previous.get("idle_since") if same_pid else None
    if not isinstance(idle_since, (int, float)):
        updated = _parse_time(str(activity.get("updated_at") or ""))
        if updated is not None:
            idle_since = min(observed_at, updated.timestamp())
        else:
            idle_since = observed_at
    idle_seconds = max(0.0, observed_at - float(idle_since))
    state = {
        "profile": profile,
        "pid": int(activity.get("pid") or 0),
        "idle_since": float(idle_since),
        "last_observed_at": observed_at,
        "active_agents": 0,
    }
    _write_idle_state(paths, profile, state)
    return idle_seconds >= minimum, {
        **activity,
        "minimum_idle_seconds": minimum,
        "idle_seconds": round(idle_seconds, 3),
        "idle_since": float(idle_since),
    }


def _write_status(paths: BrokerPaths, profile: str, status: dict[str, Any]) -> None:
    ensure_dirs(paths)
    tmp = _status_file(paths, profile).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(_status_file(paths, profile))


def _move_request(path: Path, dest_dir: Path, payload: dict[str, Any], result: dict[str, Any]) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    archived = dict(payload)
    archived["broker_result"] = result
    dest = dest_dir / path.name
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(archived, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(dest)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return dest


def _check_allowed(payload: dict[str, Any], config: dict[str, Any]) -> tuple[str, str]:
    if not bool(config.get("enabled", False)):
        raise RestartRequestRejected("Restart broker is disabled in restart-broker.yaml")
    profile = _validate_profile_name(payload.get("profile", ""))
    requester = _validate_profile_name(payload.get("requested_by", ""), field="requested_by")
    allowed_profiles = set(_list_config(config.get("allowed_profiles")))
    allowed_requesters = set(_list_config(config.get("allowed_requesters")))
    if profile not in allowed_profiles:
        raise RestartRequestRejected(f"Profile {profile!r} is not in allowed_profiles")
    if requester not in allowed_requesters:
        raise RestartRequestRejected(f"Requester {requester!r} is not in allowed_requesters")
    if profile == requester and not bool(config.get("allow_self_restart", False)):
        raise RestartRequestRejected("Self restart requests are disabled")
    created_at = _parse_time(str(payload.get("created_at", "")))
    max_age = int(config.get("max_request_age_seconds", 3600) or 3600)
    if created_at is None:
        raise RestartRequestRejected("Request is missing a valid created_at timestamp")
    age = (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).total_seconds()
    if age > max_age:
        raise RestartRequestRejected(f"Request is stale ({age:.0f}s > {max_age}s)")
    return profile, requester


def _systemctl_base(config: dict[str, Any]) -> list[str]:
    scope = str(config.get("systemctl_scope") or "user").strip().lower()
    if scope == "system":
        return ["systemctl"]
    return ["systemctl", "--user"]


def _restart_unit(profile: str, config: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    unit = f"hermes-gateway-{profile}.service"
    base = _systemctl_base(config)
    if dry_run:
        return {
            "dry_run": True,
            "unit": unit,
            "restart_command": base + ["restart", unit],
            "show_command": base + [
                "show",
                unit,
                "--property=ActiveState,SubState,MainPID,ExecMainStartTimestamp",
                "--no-pager",
            ],
        }
    restart = subprocess.run(
        base + ["restart", unit],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    show = subprocess.run(
        base + [
            "show",
            unit,
            "--property=ActiveState,SubState,MainPID,ExecMainStartTimestamp",
            "--no-pager",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return {
        "dry_run": False,
        "unit": unit,
        "restart_returncode": restart.returncode,
        "restart_stdout": restart.stdout.strip(),
        "restart_stderr": restart.stderr.strip(),
        "show_returncode": show.returncode,
        "show_stdout": show.stdout.strip(),
        "show_stderr": show.stderr.strip(),
        "ok": restart.returncode == 0 and "ActiveState=active" in show.stdout,
    }


def run_once(
    *,
    root: str | Path | None = None,
    dry_run: bool = False,
    allow_in_gateway: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Process pending restart requests.

    Refuses to run from inside a gateway unless ``allow_in_gateway`` is true.
    The request-writing path remains safe inside gateways; only this executor is
    required to be out-of-process.
    """
    if os.environ.get("_HERMES_GATEWAY") == "1" and not allow_in_gateway:
        raise RestartBrokerError(
            "Refusing to run restart broker inside a gateway process. "
            "Run it from a systemd timer/service or a shell outside the gateway."
        )
    paths = broker_paths(root)
    ensure_dirs(paths)
    config = load_config(paths.root)
    results: list[dict[str, Any]] = []
    pending = sorted(paths.pending.glob("*.json"), key=lambda p: (p.stat().st_mtime, p.name))[:limit]
    for request_path in pending:
        try:
            payload = json.loads(request_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise RestartRequestRejected("Request JSON must be an object")
            profile, requester = _check_allowed(payload, config)
            idle_required = bool(config.get("require_sustained_idle", True)) and not dry_run
            if idle_required:
                idle_ready, activity = _check_sustained_idle(paths, profile, config)
                if not idle_ready:
                    result = {
                        "request": str(request_path),
                        "profile": profile,
                        "requested_by": requester,
                        "status": "deferred",
                        "observed_at": _utc_now(),
                        "reason": "waiting for sustained gateway idleness",
                        "activity": activity,
                    }
                    _write_status(paths, profile, result)
                    results.append(result)
                    continue
            cooldown = int(config.get("cooldown_seconds", 30) or 0)
            status_path = _status_file(paths, profile)
            if cooldown > 0 and status_path.exists():
                try:
                    previous = json.loads(status_path.read_text(encoding="utf-8"))
                    last_at = _parse_time(previous.get("finished_at", ""))
                    if last_at is not None:
                        elapsed = (datetime.now(timezone.utc) - last_at.astimezone(timezone.utc)).total_seconds()
                        if elapsed < cooldown:
                            raise RestartRequestRejected(
                                f"Cooldown active for {profile!r}: {elapsed:.0f}s < {cooldown}s"
                            )
                except RestartRequestRejected:
                    raise
                except Exception:
                    pass
            if idle_required:
                # Close the race between the first observation and restart.
                # Any resumed work or PID change resets the idle window and
                # leaves the request pending for a later broker tick.
                idle_ready, activity = _check_sustained_idle(paths, profile, config)
                if not idle_ready:
                    result = {
                        "request": str(request_path),
                        "profile": profile,
                        "requested_by": requester,
                        "status": "deferred",
                        "observed_at": _utc_now(),
                        "reason": "gateway activity changed before restart",
                        "activity": activity,
                    }
                    _write_status(paths, profile, result)
                    results.append(result)
                    continue
            action = _restart_unit(profile, config, dry_run=dry_run)
            _clear_idle_state(paths, profile)
            ok = bool(action.get("ok", False) or dry_run)
            result = {
                "request": str(request_path),
                "profile": profile,
                "requested_by": requester,
                "status": "done" if ok else "failed",
                "finished_at": _utc_now(),
                "action": action,
            }
            _write_status(paths, profile, result)
            _move_request(request_path, paths.done if ok else paths.failed, payload, result)
            results.append(result)
        except Exception as exc:
            profile = str(locals().get("payload", {}).get("profile", "unknown")) if isinstance(locals().get("payload"), dict) else "unknown"
            result = {
                "request": str(request_path),
                "profile": profile,
                "status": "failed",
                "finished_at": _utc_now(),
                "error": str(exc),
            }
            if _PROFILE_RE.fullmatch(profile):
                _write_status(paths, profile, result)
            try:
                payload_for_archive = payload if isinstance(payload, dict) else {"raw_error": "invalid payload"}
            except UnboundLocalError:
                payload_for_archive = {"raw_error": "unreadable payload"}
            _move_request(request_path, paths.failed, payload_for_archive, result)
            results.append(result)
    return results


def install_systemd_units(
    *,
    root: str | Path | None = None,
    python: str | None = None,
    unit_dir: str | Path | None = None,
    interval_seconds: int = 15,
    enable_now: bool = False,
) -> dict[str, Any]:
    """Install a user systemd service+timer for the restart broker."""
    root_path = resolve_root(root)
    py = python or sys.executable
    target_dir = Path(unit_dir).expanduser() if unit_dir else Path.home() / ".config" / "systemd" / "user"
    target_dir.mkdir(parents=True, exist_ok=True)
    service = target_dir / "hermes-restart-broker.service"
    timer = target_dir / "hermes-restart-broker.timer"
    service.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Hermes Gateway Restart Broker",
                "Documentation=https://hermes-agent.nousresearch.com/docs",
                "",
                "[Service]",
                "Type=oneshot",
                f"ExecStart={shutil.which(py) or py} -m hermes_cli.restart_broker --root {root_path} run-once",
                "",
            ]
        ),
        encoding="utf-8",
    )
    timer.write_text(
        "\n".join(
            [
                "[Unit]",
                "Description=Run Hermes Gateway Restart Broker periodically",
                "",
                "[Timer]",
                "OnBootSec=30s",
                f"OnUnitActiveSec={int(interval_seconds)}s",
                "AccuracySec=2s",
                "Unit=hermes-restart-broker.service",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        ),
        encoding="utf-8",
    )
    result: dict[str, Any] = {
        "service": str(service),
        "timer": str(timer),
        "enabled": False,
    }
    if enable_now:
        daemon = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        enable = subprocess.run(
            ["systemctl", "--user", "enable", "--now", "hermes-restart-broker.timer"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        result.update(
            {
                "daemon_reload_returncode": daemon.returncode,
                "daemon_reload_stderr": daemon.stderr.strip(),
                "enable_returncode": enable.returncode,
                "enable_stdout": enable.stdout.strip(),
                "enable_stderr": enable.stderr.strip(),
                "enabled": daemon.returncode == 0 and enable.returncode == 0,
            }
        )
    return result


def _json_print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes gateway restart broker")
    parser.add_argument("--root", help="Hermes root directory (default: inferred)")
    sub = parser.add_subparsers(dest="command", required=True)

    req = sub.add_parser("request", help="Create a restart request")
    req.add_argument("--profile", required=True)
    req.add_argument("--requested-by", required=True)
    req.add_argument("--reason", default="")

    run = sub.add_parser("run-once", help="Process pending restart requests")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--allow-in-gateway", action="store_true", help=argparse.SUPPRESS)
    run.add_argument("--limit", type=int, default=20)

    cfg = sub.add_parser("write-config", help="Write broker config")
    cfg.add_argument("--allowed-profile", action="append", required=True)
    cfg.add_argument("--allowed-requester", action="append")
    cfg.add_argument("--force", action="store_true")

    inst = sub.add_parser("install-systemd", help="Install user systemd broker timer")
    inst.add_argument("--interval-seconds", type=int, default=15)
    inst.add_argument("--enable-now", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "request":
            path = create_request(
                args.profile,
                requested_by=args.requested_by,
                reason=args.reason,
                root=args.root,
            )
            _json_print({"ok": True, "request": str(path)})
            return 0
        if args.command == "run-once":
            _json_print(
                run_once(
                    root=args.root,
                    dry_run=args.dry_run,
                    allow_in_gateway=args.allow_in_gateway,
                    limit=args.limit,
                )
            )
            return 0
        if args.command == "write-config":
            path = write_default_config(
                root=args.root,
                allowed_profiles=args.allowed_profile,
                allowed_requesters=args.allowed_requester,
                force=args.force,
            )
            _json_print({"ok": True, "config": str(path)})
            return 0
        if args.command == "install-systemd":
            _json_print(
                install_systemd_units(
                    root=args.root,
                    interval_seconds=args.interval_seconds,
                    enable_now=args.enable_now,
                )
            )
            return 0
    except Exception as exc:
        _json_print({"ok": False, "error": str(exc)})
        return 1
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
