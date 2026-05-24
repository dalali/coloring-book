"""Tests for AI generation provider selection + graceful degradation (FR10/FR11).

No network calls: provider construction is verified by key presence, and the
factory's None behaviour is verified directly.
"""
from __future__ import annotations

import dataclasses

from app.config import Settings
from app.generation.base import get_provider


def _settings(**over) -> Settings:
    base = Settings()
    return dataclasses.replace(base, **over)


def test_no_keys_disables_text_flow():
    s = _settings(openai_api_key=None, stability_api_key=None)
    assert get_provider(s) is None
    assert s.text_flow_enabled is False


def test_openai_selected_when_key_present():
    s = _settings(openai_api_key="sk-test")
    provider = get_provider(s)
    assert provider is not None
    assert provider.name == "openai"
    assert s.text_flow_enabled is True


def test_stability_selected_when_only_stability_key():
    s = _settings(openai_api_key=None, stability_api_key="st-test")
    provider = get_provider(s)
    assert provider is not None
    assert provider.name == "stability"


def test_openai_preferred_over_stability():
    s = _settings(openai_api_key="sk-test", stability_api_key="st-test")
    assert get_provider(s).name == "openai"
