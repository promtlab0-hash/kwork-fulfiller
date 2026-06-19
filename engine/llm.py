"""СОЗДАНИЕ — LLM invocation layer.

Reuses the proven `claude -p` subprocess pattern from tg_channel_generate.py.
The CLI itself picks up CLAUDE_CODE_OAUTH_TOKEN from the environment, so GitHub
Actions just needs the secret exported — no special handling here.

`--dry-run` short-circuits the network call and returns a deterministic stub so
the whole pipeline (builders + checks) can run offline.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess

DEFAULT_TIMEOUT = 600


class LLMError(RuntimeError):
    """Raised when a backend cannot be reached or fails to respond.

    `status` carries the HTTP status code for OpenAI-compatible failures (e.g.
    429 rate-limit), letting the cascade tell limits apart from other errors.
    """

    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


def find_claude_bin() -> str:
    """Locate the `claude` executable on PATH or in known install dirs."""
    found = shutil.which("claude")
    if found:
        return found
    candidates = [
        pathlib.Path.home() / ".local" / "bin" / "claude",
        pathlib.Path("/usr/local/bin/claude"),
        pathlib.Path("/usr/bin/claude"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise LLMError(
        "claude CLI not found. Install it (`npm i -g @anthropic-ai/claude-code`) "
        "or run with --dry-run."
    )


def _strip_fences(text: str) -> str:
    """Drop a leading/trailing ```json / ```markdown fence if present."""
    text = re.sub(r"^```(?:json|markdown|python|csv|html)?\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def call_claude(
    prompt: str,
    dry_run: bool = False,
    *,
    stub: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_turns: int = 3,
) -> str:
    """Run a prompt through Claude and return cleaned text.

    In dry-run mode the provided `stub` is returned verbatim (after fence
    stripping), letting the rest of the pipeline execute without a network call.
    """
    if dry_run:
        if stub is None:
            raise LLMError("dry_run=True requires a stub to substitute.")
        return _strip_fences(stub)

    claude_bin = find_claude_bin()
    try:
        proc = subprocess.run(
            [claude_bin, "-p", "--max-turns", str(max_turns), "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "CLAUDE_CODE_NO_TELEMETRY": "1"},
        )
    except subprocess.TimeoutExpired:
        raise LLMError(
            f"claude CLI не ответил за {timeout}s (таймаут). "
            "Повторите позже или уменьшите объём задания."
        )
    if proc.returncode != 0:
        raise LLMError(
            f"claude CLI exit={proc.returncode}: {proc.stderr.strip()[:500]}"
        )
    cleaned = _strip_fences(proc.stdout)
    if not cleaned.strip():
        raise LLMError("claude CLI вернул пустой ответ (возможно, rate limit).")
    return cleaned


def _call_openai_compatible(
    prompt: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: int = DEFAULT_TIMEOUT,
    temperature: float = 0.7,
) -> str:
    """Call any OpenAI-compatible /chat/completions endpoint and return text.

    Works with OpenRouter, a local Ollama (`/v1`), GitHub Models, or anything
    else that speaks the OpenAI schema. Auth is a Bearer token (Ollama ignores
    it but still wants a non-empty value).
    """
    import requests  # local import keeps the claude/dry-run path dependency-free

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.Timeout:
        raise LLMError(f"{model} не ответил за {timeout}s (таймаут).")
    except requests.RequestException as exc:
        raise LLMError(f"сеть/endpoint недоступен ({base_url}): {exc}")

    if resp.status_code != 200:
        raise LLMError(
            f"{model} HTTP {resp.status_code}: {resp.text.strip()[:500]}",
            status=resp.status_code,
        )
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"неожиданный ответ от {model}: {resp.text.strip()[:300]} ({exc})")

    cleaned = _strip_fences(content or "")
    if not cleaned.strip():
        raise LLMError(f"{model} вернул пустой ответ.")
    return cleaned


# Provider presets: how to reach each backend and where its key lives. The key
# is read from the first non-empty env var listed in `key_envs`.
PROVIDERS: dict[str, dict] = {
    "claude": {"kind": "claude"},
    "github": {
        "kind": "openai",
        "base_url": "https://models.github.ai/inference",
        "key_envs": ["LLM_API_KEY", "GITHUB_TOKEN"],
        "default_model": "openai/gpt-4o",
    },
    "openrouter": {
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "key_envs": ["OPENROUTER_API_KEY", "LLM_API_KEY"],
        "default_model": "qwen/qwen-2.5-72b-instruct:free",
    },
    "groq": {
        "kind": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "key_envs": ["GROQ_API_KEY"],
        "default_model": "llama-3.3-70b-versatile",
    },
    "gemini": {
        "kind": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "key_envs": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "default_model": "gemini-2.0-flash",
    },
    "ollama": {
        "kind": "openai",
        "base_url": "http://localhost:11434/v1",
        "key_envs": [],  # local, no key
        "default_model": "qwen2.5",
        "no_key_ok": True,
    },
}

# Smart → simple. Rotates models inside GitHub Models (separate daily quotas),
# then jumps to other providers, ending at a local Ollama floor (if running).
DEFAULT_CHAIN = (
    "github:openai/gpt-4o,"
    "github:meta/Llama-3.3-70B-Instruct,"
    "github:deepseek/DeepSeek-V3-0324,"
    "openrouter:qwen/qwen-2.5-72b-instruct:free,"
    "ollama:qwen2.5"
)


def _provider_key(provider: str) -> str:
    for env_name in PROVIDERS.get(provider, {}).get("key_envs", []):
        val = os.environ.get(env_name)
        if val:
            return val
    return ""


def _parse_chain(chain_str: str | None) -> list[tuple[str, str]]:
    """Turn 'github:gpt-4o, ollama:qwen2.5' into [(provider, model), …]."""
    links: list[tuple[str, str]] = []
    for raw in (chain_str or "").split(","):
        token = raw.strip()
        if not token:
            continue
        provider, _, model = token.partition(":")
        provider = provider.strip().lower()
        if provider not in PROVIDERS:
            continue
        model = model.strip() or PROVIDERS[provider].get("default_model", "")
        links.append((provider, model))
    return links


def _resolve_chain(
    backend: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> list[tuple[str, str]]:
    """Decide the failover chain from explicit args → env → sensible default."""
    # Explicit single backend (flag/env) keeps the old one-shot behaviour.
    single = backend or os.environ.get("LLM_BACKEND")
    if single and not os.environ.get("LLM_CHAIN"):
        if single == "claude":
            return [("claude", "")]
        # openai single backend: rely on LLM_BASE_URL/LLM_MODEL (back-compat).
        return [("__custom__", model or os.environ.get("LLM_MODEL", ""))]
    return _parse_chain(os.environ.get("LLM_CHAIN") or DEFAULT_CHAIN)


def _call_link(provider: str, model: str, prompt: str, timeout: int) -> str:
    """Invoke one chain link. Raises LLMError (with .status) on failure."""
    if provider == "claude":
        return call_claude(prompt, dry_run=False, timeout=timeout)
    if provider == "__custom__":
        # Single openai backend via raw LLM_BASE_URL/LLM_API_KEY (back-compat).
        base = os.environ.get("LLM_BASE_URL", "")
        if not base or not model:
            raise LLMError("LLM_BACKEND=openai требует LLM_BASE_URL и LLM_MODEL.")
        key = (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        )
        return _call_openai_compatible(
            prompt, base_url=base, api_key=key, model=model, timeout=timeout
        )
    spec = PROVIDERS[provider]
    key = _provider_key(provider)
    if not key and not spec.get("no_key_ok"):
        raise LLMError(f"{provider}: нет ключа (пропускаю)")
    return _call_openai_compatible(
        prompt,
        base_url=spec["base_url"],
        api_key=key or "x",  # Ollama ignores it but wants a non-empty value
        model=model,
        timeout=timeout,
    )


def generate(
    prompt: str,
    *,
    dry_run: bool = False,
    stub: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    backend: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    on_event=None,
) -> str:
    """Backend-agnostic entry point with automatic failover.

    dry-run → stub. Otherwise walk the failover chain (LLM_CHAIN, or a sensible
    default): the first link that succeeds wins; on a rate-limit/quota/error the
    next link is tried, so the tool never stops on one provider's limit. A link
    whose provider has no API key is skipped. `on_event(msg)` (optional) reports
    which link is used / skipped for logging.
    """
    if dry_run:
        if stub is None:
            raise LLMError("dry_run=True requires a stub to substitute.")
        return _strip_fences(stub)

    chain = _resolve_chain(backend, base_url, model)
    if not chain:
        raise LLMError("пустая цепочка бэкендов (проверьте LLM_CHAIN).")

    errors: list[str] = []
    for provider, link_model in chain:
        label = provider if provider in ("claude", "__custom__") else f"{provider}:{link_model}"
        try:
            result = _call_link(provider, link_model, prompt, timeout)
            if on_event:
                on_event(f"✓ {label}")
            return result
        except LLMError as exc:
            note = "лимит" if getattr(exc, "status", None) == 429 else "ошибка"
            errors.append(f"{label}: {exc}")
            if on_event:
                on_event(f"✗ {label} ({note}) → следующий")
    raise LLMError("все бэкенды в цепочке недоступны:\n  " + "\n  ".join(errors))


def parse_json(text: str) -> dict | list:
    """Parse JSON from model output, tolerating surrounding prose.

    Trims to the outermost {...} or [...] span before parsing, which rescues
    responses where the model leaks a sentence before/after the JSON.
    """
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the widest balanced object or array span. Try each candidate
    # (leftmost first) and return the first that parses — a single malformed
    # span shouldn't sink a response that also carries a valid one.
    candidates: list[tuple[int, int]] = []
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            candidates.append((start, end))
    if not candidates:
        raise ValueError(f"No JSON object/array found in output: {text[:200]!r}")

    last_err: json.JSONDecodeError | None = None
    for start, end in sorted(candidates, key=lambda c: c[0]):
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            last_err = exc
    raise ValueError(
        f"Found JSON-like spans but none parsed ({last_err}): {text[:200]!r}"
    )
