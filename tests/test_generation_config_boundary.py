"""
Regression tests for generation config boundary.

CRITICAL: Generation uses ONLY AI_BASE_URL, AI_API_KEY, AI_MODEL.
EMBEDDING_* must NEVER be used for generation.
No provider fallback. No hardcoded models. Fail-closed.
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from thai_factory.extract.ai_extractor import _get_ai_config, _load_env, _REQUIRED_GEN_CONFIG


class TestGenerationConfigBoundary:
    """Generation config must use ONLY AI_BASE_URL, AI_API_KEY, AI_MODEL."""

    def test_generation_never_uses_embedding_credentials(self):
        """EMBEDDING_API_KEY must never be used for generation."""
        env = {
            "AI_BASE_URL": "https://opencode.ai/zen/go/v1",
            "AI_API_KEY": "gen-key-123",
            "AI_MODEL": "glm-5.3-flash",
            "EMBEDDING_BASE_URL": "https://openrouter.ai/api/v1",
            "EMBEDDING_API_KEY": "emb-key-456",
        }
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            config = _get_ai_config()
            assert config["base_url"] == "https://opencode.ai/zen/go/v1"
            assert config["api_key"] == "gen-key-123"
            assert config["model"] == "glm-5.3-flash"
            assert config["api_key"] != env.get("EMBEDDING_API_KEY")

    def test_generation_model_comes_only_from_ai_model(self):
        """Model must come from AI_MODEL only."""
        env = {
            "AI_BASE_URL": "https://opencode.ai/zen/go/v1",
            "AI_API_KEY": "test-key",
            "AI_MODEL": "my-actual-model",
        }
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            config = _get_ai_config()
            assert config["model"] == "my-actual-model"

    def test_no_hardcoded_generation_model(self):
        """Source code must not contain hardcoded generation model names."""
        import inspect
        from thai_factory.extract import ai_extractor
        source = inspect.getsource(ai_extractor)
        hardcoded = [
            "gpt-4o", "gpt-3.5", "claude", "llama", "mistral",
            "openai/gpt", "anthropic/",
        ]
        for pattern in hardcoded:
            assert pattern not in source, f"Hardcoded model found: {pattern}"

    def test_missing_generation_config_fails_closed(self):
        """Missing all config must raise ValueError."""
        env = {"AI_BASE_URL": "", "AI_API_KEY": "", "AI_MODEL": ""}
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            with pytest.raises(ValueError, match="GENERATION CONFIG MISSING"):
                _get_ai_config()

    def test_missing_single_config_fails_closed(self):
        """Missing any single required config must raise ValueError."""
        for key in _REQUIRED_GEN_CONFIG:
            env = {
                "AI_BASE_URL": "https://opencode.ai/zen/go/v1",
                "AI_API_KEY": "test-key",
                "AI_MODEL": "test-model",
            }
            env[key] = ""
            with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
                with pytest.raises(ValueError, match="GENERATION CONFIG MISSING"):
                    _get_ai_config()

    def test_embedding_config_cannot_activate_generation_fallback(self):
        """Having EMBEDDING_API_KEY must not activate generation fallback."""
        env = {
            "AI_BASE_URL": "",
            "AI_API_KEY": "",
            "AI_MODEL": "",
            "EMBEDDING_BASE_URL": "https://openrouter.ai/api/v1",
            "EMBEDDING_API_KEY": "sk-or-embedding-key",
        }
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            with pytest.raises(ValueError, match="GENERATION CONFIG MISSING"):
                _get_ai_config()

    def test_provider_fallback_is_disabled(self):
        """No automatic provider fallback logic must exist in source."""
        import inspect
        from thai_factory.extract import ai_extractor
        source = inspect.getsource(ai_extractor)
        # Check for fallback LOGIC (not comments about the policy)
        # Remove comments and docstrings for checking
        lines = source.split("\n")
        code_lines = [l for l in lines if not l.strip().startswith("#") and not l.strip().startswith('"')]
        code_source = "\n".join(code_lines)
        fallback_logic = [
            "try_next", "alternative_provider",
            "prefer_openrouter", "prefer_openai",
        ]
        for pattern in fallback_logic:
            assert pattern.lower() not in code_source.lower(), \
                f"Provider fallback logic found: {pattern}"

    def test_outgoing_request_uses_ai_base_url(self):
        """Outgoing requests must use AI_BASE_URL."""
        import inspect
        from thai_factory.extract import ai_extractor
        source = inspect.getsource(ai_extractor)
        assert "AI_BASE_URL" in source

    def test_embedding_key_same_as_gen_key_with_openrouter_raises(self):
        """If AI_API_KEY == EMBEDDING_API_KEY with OpenRouter URL, must raise."""
        env = {
            "AI_BASE_URL": "https://openrouter.ai/api/v1",
            "AI_API_KEY": "same-key-both",
            "AI_MODEL": "test-model",
            "EMBEDDING_API_KEY": "same-key-both",
        }
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            with pytest.raises(ValueError, match="CONFIG VIOLATION"):
                _get_ai_config()

    def test_config_returns_only_generation_fields(self):
        """Config dict must contain only base_url, api_key, model, provider."""
        env = {
            "AI_BASE_URL": "https://opencode.ai/zen/go/v1",
            "AI_API_KEY": "test-key",
            "AI_MODEL": "test-model",
            "EMBEDDING_BASE_URL": "https://openrouter.ai/api/v1",
            "EMBEDDING_API_KEY": "emb-key",
        }
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            config = _get_ai_config()
            assert set(config.keys()) == {"base_url", "api_key", "model", "provider"}
