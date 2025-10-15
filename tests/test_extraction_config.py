"""Tests for configuration helpers used by the Gemini extractor."""

import importlib
import os
from types import SimpleNamespace

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


def test_normalises_model_names(reset_env):
    module = importlib.import_module("genephenextract.extraction")
    importlib.reload(module)
    assert module._normalise_model_name("models/gemini-pro") == "gemini-pro"


def test_selects_preferred_model(reset_env):
    module = importlib.import_module("genephenextract.extraction")
    importlib.reload(module)
    options = ["gemini-1.0-pro", "gemini-pro"]
    assert module._select_preferred_model(options) == "gemini-1.0-pro"


def _fake_genai(available_models):
    def list_models():
        return [
            SimpleNamespace(
                name=f"models/{model}", supported_generation_methods=["generateContent"]
            )
            for model in available_models
        ]

    def configure(api_key):
        return None

    def generative_model(name):
        return SimpleNamespace(name=name)

    return SimpleNamespace(
        list_models=list_models,
        configure=configure,
        GenerativeModel=lambda name: generative_model(name),
    )


def test_gemini_extractor_falls_back_to_available_model(monkeypatch, reset_env):
    module = importlib.import_module("genephenextract.extraction")
    importlib.reload(module)
    monkeypatch.setattr(module, "genai", _fake_genai(["gemini-1.0-pro"]), raising=False)

    extractor = module.GeminiExtractor(api_key="test-key")

    assert extractor.model_name == "gemini-1.0-pro"


def test_gemini_extractor_errors_for_unavailable_requested_model(monkeypatch, reset_env):
    module = importlib.import_module("genephenextract.extraction")
    importlib.reload(module)
    monkeypatch.setattr(module, "genai", _fake_genai(["gemini-1.0-pro"]), raising=False)

    with pytest.raises(module.ExtractorError) as excinfo:
        module.GeminiExtractor(api_key="test-key", model="gemini-not-real")

    assert "Available models" in str(excinfo.value)
    assert "gemini-1.0-pro" in str(excinfo.value)
