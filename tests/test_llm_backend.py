"""Universal LLM backend: dispatch + OpenAI-compatible path (mocked, no network)."""

import sys
import types

import pytest

from engine import llm


def _fake_requests(monkeypatch, *, status=200, payload=None, body="", raise_exc=None):
    """Install a fake `requests` module so engine.llm imports it locally."""
    class FakeResp:
        status_code = status
        text = body

        def json(self):
            if payload is None:
                raise ValueError("no json")
            return payload

    class Timeout(Exception):
        pass

    class RequestException(Exception):
        pass

    captured = {}

    def post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        if raise_exc == "timeout":
            raise Timeout()
        if raise_exc == "conn":
            raise RequestException("boom")
        return FakeResp()

    fake = types.ModuleType("requests")
    fake.post = post
    fake.Timeout = Timeout
    fake.RequestException = RequestException
    monkeypatch.setitem(sys.modules, "requests", fake)
    return captured


def _ok_payload(content):
    return {"choices": [{"message": {"content": content}}]}


def test_openai_compatible_happy_path(monkeypatch):
    cap = _fake_requests(monkeypatch, payload=_ok_payload('{"title": "x"}'))
    out = llm._call_openai_compatible(
        "prompt", base_url="https://host/v1", api_key="k", model="qwen"
    )
    assert out == '{"title": "x"}'
    assert cap["url"] == "https://host/v1/chat/completions"
    assert cap["json"]["model"] == "qwen"
    assert cap["headers"]["Authorization"] == "Bearer k"


def test_openai_compatible_strips_fences(monkeypatch):
    _fake_requests(monkeypatch, payload=_ok_payload("```json\n{\"a\":1}\n```"))
    out = llm._call_openai_compatible("p", base_url="http://h/v1", api_key="", model="m")
    assert out == '{"a":1}'


def test_openai_compatible_http_error_raises(monkeypatch):
    _fake_requests(monkeypatch, status=429, body="rate limited")
    with pytest.raises(llm.LLMError):
        llm._call_openai_compatible("p", base_url="http://h/v1", api_key="k", model="m")


def test_openai_compatible_empty_content_raises(monkeypatch):
    _fake_requests(monkeypatch, payload=_ok_payload("   "))
    with pytest.raises(llm.LLMError):
        llm._call_openai_compatible("p", base_url="http://h/v1", api_key="k", model="m")


def test_openai_compatible_timeout_raises(monkeypatch):
    _fake_requests(monkeypatch, raise_exc="timeout")
    with pytest.raises(llm.LLMError):
        llm._call_openai_compatible("p", base_url="http://h/v1", api_key="k", model="m")


def test_generate_dry_run_returns_stub():
    assert llm.generate("p", dry_run=True, stub='{"ok":1}') == '{"ok":1}'


def test_generate_openai_backend_dispatch(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.setenv("LLM_BASE_URL", "https://host/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen")
    monkeypatch.setenv("LLM_API_KEY", "k")
    _fake_requests(monkeypatch, payload=_ok_payload('{"done": true}'))
    assert llm.generate("p") == '{"done": true}'


def test_generate_openai_missing_config_raises(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "openai")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(llm.LLMError):
        llm.generate("p")


def test_generate_claude_backend_explicit(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "claude")
    monkeypatch.delenv("LLM_CHAIN", raising=False)
    called = {}

    def fake_claude(*a, **k):
        called["hit"] = True
        return "ok"

    monkeypatch.setattr(llm, "call_claude", fake_claude)
    assert llm.generate("p") == "ok"
    assert called.get("hit")


def test_generate_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "weird")
    monkeypatch.delenv("LLM_CHAIN", raising=False)
    with pytest.raises(llm.LLMError):
        llm.generate("p")


# --------------------------------------------------------------------------- #
# Cascade / failover
# --------------------------------------------------------------------------- #


def _clear_chain_env(monkeypatch):
    for v in ("LLM_CHAIN", "LLM_BACKEND", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)


def test_parse_chain_provider_model():
    links = llm._parse_chain("github:openai/gpt-4o, ollama:qwen2.5 , bogus:x")
    assert links == [("github", "openai/gpt-4o"), ("ollama", "qwen2.5")]


def test_parse_chain_uses_default_model_when_omitted():
    links = llm._parse_chain("github")
    assert links == [("github", "openai/gpt-4o")]


def test_cascade_falls_over_on_429(monkeypatch):
    _clear_chain_env(monkeypatch)
    monkeypatch.setenv("LLM_CHAIN", "github:m1,openrouter:m2")
    monkeypatch.setenv("GITHUB_TOKEN", "g")
    monkeypatch.setenv("OPENROUTER_API_KEY", "o")

    def post(url, json=None, headers=None, timeout=None):
        model = json["model"]

        class R:
            status_code = 429 if model == "m1" else 200
            text = "rate limited"

            def json(self):
                return _ok_payload('{"served": "m2"}')
        return R()

    fake = types.ModuleType("requests")
    fake.post = post
    fake.Timeout = type("T", (Exception,), {})
    fake.RequestException = type("RE", (Exception,), {})
    monkeypatch.setitem(sys.modules, "requests", fake)

    events = []
    out = llm.generate("p", on_event=events.append)
    assert out == '{"served": "m2"}'
    assert any("429" in e or "лимит" in e for e in events)
    assert any("✓ openrouter:m2" in e for e in events)


def test_cascade_skips_provider_without_key(monkeypatch):
    _clear_chain_env(monkeypatch)
    monkeypatch.setenv("LLM_CHAIN", "openrouter:m1,github:m2")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "g")

    captured = {}

    def post(url, json=None, headers=None, timeout=None):
        captured["model"] = json["model"]

        class R:
            status_code = 200
            text = ""

            def json(self):
                return _ok_payload('{"ok": 1}')
        return R()

    fake = types.ModuleType("requests")
    fake.post = post
    fake.Timeout = type("T", (Exception,), {})
    fake.RequestException = type("RE", (Exception,), {})
    monkeypatch.setitem(sys.modules, "requests", fake)

    out = llm.generate("p")
    assert out == '{"ok": 1}'
    # openrouter skipped (no key) → only github:m2 actually called.
    assert captured["model"] == "m2"


def test_cascade_all_fail_raises(monkeypatch):
    _clear_chain_env(monkeypatch)
    monkeypatch.setenv("LLM_CHAIN", "github:m1")
    monkeypatch.setenv("GITHUB_TOKEN", "g")
    _fake_requests(monkeypatch, status=500, body="boom")
    with pytest.raises(llm.LLMError):
        llm.generate("p")


def test_default_chain_used_when_unset(monkeypatch):
    _clear_chain_env(monkeypatch)
    links = llm._resolve_chain()
    assert links[0][0] == "github"  # smart provider first
    assert links[-1][0] == "ollama"  # unlimited local floor last
