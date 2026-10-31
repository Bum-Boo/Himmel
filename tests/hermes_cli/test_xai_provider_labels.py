"""Regression tests for xAI provider label disambiguation."""

import pytest

from hermes_cli.models import provider_label
from hermes_cli.providers import get_label


@pytest.fixture(autouse=True)
def _offline_models_dev(monkeypatch):
    """Serve the xAI display name from a synthetic catalog.

    get_label("xai") takes the name from models.dev; unpatched it fetched
    models.dev live, and offline it fell back to the raw id "xai".
    """
    import agent.models_dev as models_dev

    catalog = {
        "xai": {
            "id": "xai",
            "name": "xAI",
            "env": ["XAI_API_KEY"],
            "api": "https://api.x.ai/v1",
            "models": {},
        }
    }
    monkeypatch.setattr(models_dev, "fetch_models_dev", lambda *a, **k: catalog)


def test_xai_oauth_provider_label_is_not_collapsed_to_api_key_label():
    """The model picker must distinguish xAI API-key and OAuth providers."""
    assert get_label("xai") == "xAI"
    assert get_label("xai-oauth") == "xAI Grok OAuth (SuperGrok / Premium+)"
    assert get_label("grok-oauth") == "xAI Grok OAuth (SuperGrok / Premium+)"


