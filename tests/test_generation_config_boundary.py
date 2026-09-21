"""Regression tests for generation config boundary — integration-level."""
import json, os, sys, pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from thai_factory.extract.ai_extractor import (
    _get_ai_config, _load_env, _call_ai, _REQUIRED_GEN_CONFIG,
    _OPENROUTER_ALLOWED_MODEL, _OPENROUTER_ALLOWED_PROVIDERS,
)

def _mock_result():
    r = MagicMock(); r.returncode = 0
    r.stdout = '{"choices":[{"message":{"content":"{\\"ok\\":true}"}}]}'
    r.stderr = ""; return r

def _payload(m):
    cmd = m.call_args[0][0]
    for i, a in enumerate(cmd):
        if a == "-d" and i+1 < len(cmd) and cmd[i+1].startswith("@"):
            try:
                with open(cmd[i+1][1:]) as f: return json.load(f)
            except: pass
    return None

def _run_with_mock(fn, use_openrouter=False, env=None, config=None):
    """Helper: run _call_ai with mocked subprocess + os.unlink."""
    if env is None: env = {}
    if config is None: config = {"base_url":"https://opencode.ai/zen/go/v1","api_key":"k","model":"m","provider":"p"}
    with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
        with patch("thai_factory.extract.ai_extractor._get_ai_config", return_value=config):
            with patch("thai_factory.extract.ai_extractor.subprocess.run") as m:
                with patch("thai_factory.extract.ai_extractor.os.unlink"):
                    m.return_value = _mock_result()
                    _call_ai("t", use_openrouter=use_openrouter)
                    return m

class TestGenerationConfigBoundary:
    def test_never_uses_embedding_credentials(self):
        env = {"AI_BASE_URL":"https://opencode.ai/zen/go/v1","AI_API_KEY":"gen","AI_MODEL":"m","EMBEDDING_API_KEY":"emb"}
        with patch("thai_factory.extract.ai_extractor._load_env", return_value=env):
            c = _get_ai_config()
            assert c["api_key"] == "gen" and c["api_key"] != "emb"

    def test_model_comes_only_from_ai_model(self):
        with patch("thai_factory.extract.ai_extractor._load_env", return_value={"AI_BASE_URL":"x","AI_API_KEY":"k","AI_MODEL":"my-m"}):
            assert _get_ai_config()["model"] == "my-m"

    def test_no_hardcoded_model(self):
        import inspect; from thai_factory.extract import ai_extractor
        for p in ["gpt-4o","gpt-3.5","claude","llama","mistral","openai/gpt","anthropic/"]:
            assert p not in inspect.getsource(ai_extractor)

    def test_missing_config_fails_closed(self):
        with patch("thai_factory.extract.ai_extractor._load_env", return_value={"AI_BASE_URL":"","AI_API_KEY":"","AI_MODEL":""}):
            with pytest.raises(ValueError, match="GENERATION CONFIG MISSING"): _get_ai_config()

    def test_missing_single_config(self):
        for k in _REQUIRED_GEN_CONFIG:
            e = {"AI_BASE_URL":"x","AI_API_KEY":"k","AI_MODEL":"m"}; e[k] = ""
            with patch("thai_factory.extract.ai_extractor._load_env", return_value=e):
                with pytest.raises(ValueError): _get_ai_config()

    def test_embedding_cannot_activate_fallback(self):
        with patch("thai_factory.extract.ai_extractor._load_env", return_value={"AI_BASE_URL":"","AI_API_KEY":"","AI_MODEL":"","EMBEDDING_API_KEY":"x"}):
            with pytest.raises(ValueError): _get_ai_config()

    def test_no_fallback_logic(self):
        import inspect; from thai_factory.extract import ai_extractor
        src = inspect.getsource(ai_extractor)
        lines = [l for l in src.split("\n") if not l.strip().startswith("#") and not l.strip().startswith('"')]
        code = "\n".join(lines)
        for p in ["try_next","alternative_provider","prefer_openrouter","prefer_openai"]:
            assert p.lower() not in code.lower()

    def test_same_key_with_openrouter_raises(self):
        with patch("thai_factory.extract.ai_extractor._load_env", return_value={"AI_BASE_URL":"https://openrouter.ai/api/v1","AI_API_KEY":"s","AI_MODEL":"t","EMBEDDING_API_KEY":"s"}):
            with pytest.raises(ValueError, match="CONFIG VIOLATION"): _get_ai_config()

    def test_config_fields(self):
        with patch("thai_factory.extract.ai_extractor._load_env", return_value={"AI_BASE_URL":"x","AI_API_KEY":"k","AI_MODEL":"m","EMBEDDING_API_KEY":"y"}):
            assert set(_get_ai_config().keys()) == {"base_url","api_key","model","provider"}

class TestOpenRouterAllowlist:
    def test_model(self): assert _OPENROUTER_ALLOWED_MODEL == "inclusionai/ling-3.0-flash"
    def test_providers(self): assert _OPENROUTER_ALLOWED_PROVIDERS == ["novita"]
    def test_fallbacks_false(self):
        import inspect; from thai_factory.extract import ai_extractor
        src = inspect.getsource(ai_extractor)
        assert "allow_fallbacks" in src and "False" in src
    def test_requires_emb_key(self):
        with pytest.raises(ValueError, match="OpenRouter requires EMBEDDING_API_KEY"):
            _run_with_mock(None, use_openrouter=True, env={"EMBEDDING_API_KEY":""},
                          config={"base_url":"x","api_key":"g","model":"t","provider":"p"})
    def test_primary_route(self):
        import inspect; from thai_factory.extract import ai_extractor
        assert 'config["base_url"]' in inspect.getsource(ai_extractor)
    def test_no_auto_fallback(self):
        import inspect; from thai_factory.extract import ai_extractor
        src = inspect.getsource(ai_extractor)
        lines = [l for l in src.split("\n") if not l.strip().startswith("#") and not l.strip().startswith('"')]
        code = "\n".join(lines)
        assert "try_next" not in code.lower() and "fallback_to_openrouter" not in code.lower()
    def test_payload_constraint(self):
        p = {"model":_OPENROUTER_ALLOWED_MODEL,"provider":{"only":_OPENROUTER_ALLOWED_PROVIDERS,"allow_fallbacks":False}}
        assert p["model"]=="inclusionai/ling-3.0-flash" and p["provider"]["only"]==["novita"] and p["provider"]["allow_fallbacks"] is False

class TestOutgoingPayloadInspection:
    CFG = {"base_url":"https://opencode.ai/zen/go/v1","api_key":"gen-key","model":"glm-5.3-flash","provider":"openai-compatible"}

    def test_default_uses_ai_base_url(self):
        m = _run_with_mock(None, use_openrouter=False, config=self.CFG)
        cmd = m.call_args[0][0]
        assert "opencode.ai" in cmd[4]
        p = _payload(m)
        assert p["model"] == "glm-5.3-flash" and "provider" not in p

    def test_openrouter_uses_allowlisted(self):
        m = _run_with_mock(None, use_openrouter=True, env={"EMBEDDING_API_KEY":"sk-or-emb"}, config=self.CFG)
        cmd = m.call_args[0][0]
        assert "openrouter.ai" in cmd[4]
        p = _payload(m)
        assert p["model"] == "inclusionai/ling-3.0-flash"
        assert p["provider"]["only"] == ["novita"]
        assert p["provider"]["allow_fallbacks"] is False

    def test_default_never_touches_embedding_key(self):
        m = _run_with_mock(None, use_openrouter=False, env={"EMBEDDING_API_KEY":"emb-key"}, config=self.CFG)
        cmd = m.call_args[0][0]
        for i, a in enumerate(cmd):
            if a == "-H" and "Authorization" in cmd[i+1]:
                assert "gen-key" in cmd[i+1] and "emb-key" not in cmd[i+1]
                break

    def test_no_other_model_in_openrouter(self):
        m = _run_with_mock(None, use_openrouter=True, env={"EMBEDDING_API_KEY":"sk-or-x"}, config=self.CFG)
        p = _payload(m)
        s = json.dumps(p)
        assert "gpt" not in s and "claude" not in s and "llama" not in s
