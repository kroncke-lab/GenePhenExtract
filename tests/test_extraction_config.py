"""Tests for configuration helpers used by the Gemini extractor."""

import importlib
import os

import pytest


@pytest.fixture
def reset_env():
    """Ensure the configuration module reads a clean environment."""
    original = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original)


def test_resolve_model_uses_defaults(reset_env):
    module = importlib.import_module("genephenextract.extraction")
    importlib.reload(module)
    assert module._resolve_model_name(None) == module.DEFAULT_GEMINI_MODEL


def test_resolve_model_prefers_argument(reset_env):
    module = importlib.import_module("genephenextract.extraction")
    importlib.reload(module)
    assert module._resolve_model_name("custom-model") == "custom-model"


def test_resolve_model_prefers_env_var(reset_env):
    module = importlib.import_module("genephenextract.extraction")
    os.environ[module.GEMINI_MODEL_ENV_VAR] = "env-model"
    importlib.reload(module)
    assert module._resolve_model_name(None) == "env-model"
