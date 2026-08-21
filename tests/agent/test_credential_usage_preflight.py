from types import SimpleNamespace


def test_preflight_swaps_active_agent_to_usage_guard_selection():
    selected = SimpleNamespace(
        id="owner",
        runtime_api_key="owner-token",
        access_token="owner-token",
    )

    class FakePool:
        def usage_guard_enabled(self):
            return True

        def select(self):
            return selected

    swaps = []
    agent = SimpleNamespace(
        _credential_pool=FakePool(),
        api_key="teacher-token",
        _swap_credential=swaps.append,
    )

    import agent.chat_completion_helpers as helpers

    preflight = getattr(helpers, "_preflight_credential_usage_guard", lambda _agent: None)
    preflight(agent)

    assert swaps == [selected]


def test_preflight_fails_closed_instead_of_reusing_stale_codex_token():
    import pytest
    from agent.credential_pool import CodexUsageLimitReached

    class FakePool:
        def usage_guard_enabled(self):
            return True

        def select(self):
            return None

    agent = SimpleNamespace(
        _credential_pool=FakePool(),
        api_key="stale-token-that-must-not-run",
        _swap_credential=lambda selected: None,
    )

    import agent.chat_completion_helpers as helpers

    with pytest.raises(CodexUsageLimitReached):
        helpers._preflight_credential_usage_guard(agent)


def test_preflight_propagates_codex_usage_guard_errors():
    import pytest
    from agent.credential_pool import CodexUsageCheckUnavailable

    class FakePool:
        def usage_guard_enabled(self):
            return True

        def select(self):
            raise CodexUsageCheckUnavailable("usage lookup unavailable")

    agent = SimpleNamespace(
        _credential_pool=FakePool(),
        api_key="token-that-must-not-run",
        _swap_credential=lambda selected: None,
    )

    import agent.chat_completion_helpers as helpers

    with pytest.raises(CodexUsageCheckUnavailable):
        helpers._preflight_credential_usage_guard(agent)
