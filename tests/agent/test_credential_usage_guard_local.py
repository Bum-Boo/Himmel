"""Tests for multi-credential runtime pooling and rotation."""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone

import pytest


def _write_auth_store(tmp_path, payload: dict) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    (hermes_home / "auth.json").write_text(json.dumps(payload, indent=2))


def _jwt_with_claims(claims: dict) -> str:
    def _part(payload: dict) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    return f"{_part({'alg': 'none', 'typ': 'JWT'})}.{_part(claims)}.sig"

def test_codex_usage_guard_switches_at_70_percent_used_30_percent_remaining(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    _write_auth_store(
        tmp_path,
        {
            "version": 1,
            "credential_pool": {
                "openai-codex": [
                    {
                        "id": "teacher",
                        "label": "teacher-codex",
                        "auth_type": "oauth",
                        "priority": 0,
                        "source": "manual:device_code",
                        "access_token": "teacher-token",
                    },
                    {
                        "id": "owner",
                        "label": "owner-codex",
                        "auth_type": "oauth",
                        "priority": 1,
                        "source": "manual:device_code",
                        "access_token": "owner-token",
                    },
                ]
            },
        },
    )
    config_path = tmp_path / "hermes" / "config.yaml"
    config_path.write_text(
        "credential_pool_usage_guards:\n"
        "  openai-codex:\n"
        "    - label: teacher-codex\n"
        "      primary_used_percent: 70\n"
        "      window_minutes: 300\n"
    )

    import agent.credential_pool as credential_pool

    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_primary_usage",
        lambda entry, cache_seconds=60.0: (70.0, 300.0, None),
        raising=False,
    )

    pool = credential_pool.load_pool("openai-codex")
    entry = pool.select()

    assert entry is not None
    assert entry.id == "owner"


def test_codex_usage_guard_switches_when_weekly_remaining_reaches_30_percent(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
    _write_auth_store(
        tmp_path,
        {
            "version": 1,
            "credential_pool": {
                "openai-codex": [
                    {
                        "id": "teacher",
                        "label": "teacher-codex",
                        "auth_type": "oauth",
                        "priority": 0,
                        "source": "manual:device_code",
                        "access_token": "teacher-token",
                    },
                    {
                        "id": "owner",
                        "label": "owner-codex",
                        "auth_type": "oauth",
                        "priority": 1,
                        "source": "manual:device_code",
                        "access_token": "owner-token",
                    },
                ]
            },
        },
    )
    config_path = tmp_path / "hermes" / "config.yaml"
    config_path.write_text(
        "credential_pool_usage_guards:\n"
        "  openai-codex:\n"
        "    - label: teacher-codex\n"
        "      primary_used_percent: 70\n"
        "      primary_window_minutes: 300\n"
        "      secondary_used_percent: 70\n"
        "      secondary_window_minutes: 10080\n"
    )

    import agent.credential_pool as credential_pool

    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_primary_usage",
        lambda entry, cache_seconds=60.0: (20.0, 300.0, None),
    )
    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_secondary_usage",
        lambda entry, cache_seconds=60.0: (70.0, 10080.0, None),
        raising=False,
    )

    pool = credential_pool.load_pool("openai-codex")
    entry = pool.select()

    assert entry is not None
    assert entry.id == "owner"


def test_codex_usage_guard_negative_caches_lookup_failures(monkeypatch):
    import agent.credential_pool as credential_pool

    entry = credential_pool.PooledCredential(
        provider="openai-codex",
        id="teacher",
        label="teacher-codex",
        auth_type="oauth",
        priority=0,
        source="manual:device_code",
        access_token="teacher-token",
    )
    calls = {"count": 0}

    class FailingClient:
        def __init__(self, *args, **kwargs):
            calls["count"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            raise RuntimeError("usage endpoint unavailable")

    credential_pool._CODEX_USAGE_CACHE.clear()
    monkeypatch.setattr("httpx.Client", FailingClient)

    with pytest.raises(RuntimeError, match="usage endpoint unavailable"):
        credential_pool._fetch_codex_primary_usage(entry, cache_seconds=60)
    assert credential_pool._fetch_codex_primary_usage(entry, cache_seconds=60) is None
    assert calls["count"] == 1


def _subscription_codex_entry():
    import agent.credential_pool as credential_pool

    return credential_pool.PooledCredential(
        provider="openai-codex",
        id="owner",
        label="owner-codex",
        auth_type="oauth",
        priority=0,
        source="manual:device_code",
        access_token=_jwt_with_claims({"chatgpt_account_id": "acct-owner"}),
        base_url="https://chatgpt.com/backend-api/codex",
    )


def test_codex_included_plan_guard_blocks_primary_at_100_percent(monkeypatch):
    import agent.credential_pool as credential_pool

    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_usage_windows",
        lambda entry, cache_seconds=60.0: {
            "primary": (100.0, 300.0, None),
            "secondary": (25.0, 10080.0, None),
        },
    )

    pool = credential_pool.CredentialPool(
        "openai-codex", [_subscription_codex_entry()]
    )
    with pytest.raises(credential_pool.CodexUsageLimitReached):
        pool.select()


def test_codex_included_plan_guard_blocks_weekly_at_100_percent(monkeypatch):
    import agent.credential_pool as credential_pool

    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_usage_windows",
        lambda entry, cache_seconds=60.0: {
            "primary": (25.0, 300.0, None),
            "secondary": (100.0, 10080.0, None),
        },
    )

    pool = credential_pool.CredentialPool(
        "openai-codex", [_subscription_codex_entry()]
    )
    with pytest.raises(credential_pool.CodexUsageLimitReached):
        pool.select()


def test_codex_included_plan_guard_allows_both_windows_below_100(monkeypatch):
    import agent.credential_pool as credential_pool

    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_usage_windows",
        lambda entry, cache_seconds=60.0: {
            "primary": (99.0, 300.0, None),
            "secondary": (99.0, 10080.0, None),
        },
    )

    pool = credential_pool.CredentialPool(
        "openai-codex", [_subscription_codex_entry()]
    )
    selected = pool.select()
    assert selected is not None
    assert selected.id == "owner"


def test_codex_included_plan_guard_fails_closed_when_usage_unavailable(monkeypatch):
    import agent.credential_pool as credential_pool

    def fail(*args, **kwargs):
        raise RuntimeError("usage endpoint unavailable")

    monkeypatch.setattr(credential_pool, "_fetch_codex_usage_windows", fail)
    pool = credential_pool.CredentialPool(
        "openai-codex", [_subscription_codex_entry()]
    )

    with pytest.raises(credential_pool.CodexUsageCheckUnavailable):
        pool.select()


class _FakeUsageResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeUsageClient:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, *args, **kwargs):
        return _FakeUsageResponse(self._payload)


def test_codex_usage_guard_retries_negative_cache_quickly(monkeypatch):
    import agent.credential_pool as credential_pool

    entry = credential_pool.PooledCredential(
        provider="openai-codex",
        id="teacher",
        label="teacher-codex",
        auth_type="oauth",
        priority=0,
        source="manual:device_code",
        access_token="teacher-token",
    )
    calls = {"count": 0}
    now = {"value": 1_000.0}

    class RecoveringClient:
        def __init__(self, *args, **kwargs):
            calls["count"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            if calls["count"] == 1:
                raise RuntimeError("usage endpoint unavailable")
            return _FakeUsageResponse({
                "rate_limit": {
                    "primary_window": {
                        "used_percent": 0,
                        "limit_window_seconds": 604800,
                        "reset_at": 2_000,
                    }
                }
            })

    credential_pool._CODEX_USAGE_CACHE.clear()
    monkeypatch.setattr(credential_pool.time, "time", lambda: now["value"])
    monkeypatch.setattr("httpx.Client", RecoveringClient)

    with pytest.raises(RuntimeError, match="usage endpoint unavailable"):
        credential_pool._fetch_codex_usage_windows(entry, cache_seconds=60)
    assert credential_pool._fetch_codex_usage_windows(entry, cache_seconds=60) is None
    assert calls["count"] == 1

    now["value"] += credential_pool.CODEX_USAGE_ERROR_CACHE_SECONDS + 0.1
    windows = credential_pool._fetch_codex_usage_windows(entry, cache_seconds=60)

    assert windows == {"secondary": (0.0, 10080.0, 2_000.0)}
    assert calls["count"] == 2


def test_codex_usage_cache_expires_at_provider_reset_boundary(monkeypatch):
    import agent.credential_pool as credential_pool

    entry = _subscription_codex_entry()
    payloads = [
        {
            "rate_limit": {
                "primary_window": {
                    "used_percent": 100,
                    "limit_window_seconds": 18000,
                    "reset_at": 1_000,
                }
            }
        },
        {
            "rate_limit": {
                "primary_window": {
                    "used_percent": 0,
                    "limit_window_seconds": 18000,
                    "reset_at": 19_000,
                }
            }
        },
    ]
    calls = {"count": 0}
    now = {"value": 990.0}

    class ResetAwareClient:
        def __init__(self, *args, **kwargs):
            self.payload = payloads[calls["count"]]
            calls["count"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            return _FakeUsageResponse(self.payload)

    credential_pool._CODEX_USAGE_CACHE.clear()
    monkeypatch.setattr(credential_pool.time, "time", lambda: now["value"])
    monkeypatch.setattr("httpx.Client", ResetAwareClient)

    before_reset = credential_pool._fetch_codex_usage_windows(entry, cache_seconds=60)
    assert before_reset == {"primary": (100.0, 300.0, 1_000.0)}
    assert calls["count"] == 1

    now["value"] = 1_001.0
    after_reset = credential_pool._fetch_codex_usage_windows(entry, cache_seconds=60)

    assert after_reset == {"primary": (0.0, 300.0, 19_000.0)}
    assert calls["count"] == 2


def test_codex_usage_window_classified_by_duration_not_json_slot(monkeypatch):
    """Regression for #61200: the usage endpoint doesn't keep a fixed
    primary=5h/secondary=weekly meaning — some accounts report only a
    weekly window, and it can arrive in the ``primary_window`` slot with
    ``secondary_window`` left null. That must not be treated as an
    unrecognized/unavailable shape (it used to raise
    CodexUsageCheckUnavailable and hard-block every call regardless of
    actual usage)."""
    import agent.credential_pool as credential_pool

    credential_pool._CODEX_USAGE_CACHE.clear()
    weekly_in_primary_slot = {
        "rate_limit": {
            "primary_window": {"used_percent": 3, "limit_window_seconds": 604800},
            "secondary_window": None,
        }
    }
    monkeypatch.setattr(
        "httpx.Client", lambda *a, **kw: _FakeUsageClient(weekly_in_primary_slot)
    )

    pool = credential_pool.CredentialPool(
        "openai-codex", [_subscription_codex_entry()]
    )
    selected = pool.select()

    assert selected is not None
    assert selected.id == "owner"


def test_codex_usage_window_weekly_in_primary_slot_blocks_at_100(monkeypatch):
    import agent.credential_pool as credential_pool

    credential_pool._CODEX_USAGE_CACHE.clear()
    weekly_in_primary_slot = {
        "rate_limit": {
            "primary_window": {"used_percent": 100, "limit_window_seconds": 604800},
            "secondary_window": None,
        }
    }
    monkeypatch.setattr(
        "httpx.Client", lambda *a, **kw: _FakeUsageClient(weekly_in_primary_slot)
    )

    pool = credential_pool.CredentialPool(
        "openai-codex", [_subscription_codex_entry()]
    )
    with pytest.raises(credential_pool.CodexUsageLimitReached):
        pool.select()


def test_codex_guard_skips_unrefreshable_entry_and_uses_healthy_alternative(
    monkeypatch,
):
    import agent.credential_pool as credential_pool

    stale = _subscription_codex_entry()
    healthy = credential_pool.PooledCredential(
        provider="openai-codex",
        id="healthy",
        label="owner-codex-healthy",
        auth_type="oauth",
        priority=1,
        source="manual:device_code",
        access_token=_jwt_with_claims({"chatgpt_account_id": "acct-owner"}),
        base_url="https://chatgpt.com/backend-api/codex",
    )
    monkeypatch.setattr(
        credential_pool,
        "_fetch_codex_usage_windows",
        lambda entry, cache_seconds=60.0: {
            "primary": (40.0, 300.0, None),
            "secondary": (20.0, 10080.0, None),
        },
    )
    pool = credential_pool.CredentialPool("openai-codex", [stale, healthy])
    monkeypatch.setattr(
        pool, "_entry_needs_refresh", lambda entry: entry.id == "owner"
    )
    monkeypatch.setattr(pool, "_refresh_entry", lambda entry, force: None)

    selected = pool.select()

    assert selected is not None
    assert selected.id == "healthy"
