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
    """Raised when the Claude CLI cannot be located or fails to respond."""


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
            f"{model} HTTP {resp.status_code}: {resp.text.strip()[:500]}"
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


def _resolve_backend(
    backend: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> dict:
    """Collect backend config from explicit args first, then env vars."""
    backend = (backend or os.environ.get("LLM_BACKEND") or "claude").strip().lower()
    return {
        "backend": backend,
        "base_url": base_url or os.environ.get("LLM_BASE_URL", ""),
        "model": model or os.environ.get("LLM_MODEL", ""),
        "api_key": (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ),
    }


def generate(
    prompt: str,
    *,
    dry_run: bool = False,
    stub: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    backend: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    """Backend-agnostic entry point used by the pipeline.

    dry-run → stub; otherwise dispatch by LLM_BACKEND: `claude` (CLI, default)
    or `openai` (any OpenAI-compatible endpoint — OpenRouter/Ollama/GitHub
    Models). Config comes from explicit args, then environment variables.
    """
    if dry_run:
        if stub is None:
            raise LLMError("dry_run=True requires a stub to substitute.")
        return _strip_fences(stub)

    cfg = _resolve_backend(backend, base_url, model)
    if cfg["backend"] == "claude":
        return call_claude(prompt, dry_run=False, timeout=timeout)
    if cfg["backend"] == "openai":
        if not cfg["base_url"] or not cfg["model"]:
            raise LLMError(
                "LLM_BACKEND=openai требует LLM_BASE_URL и LLM_MODEL "
                "(см. .env.example)."
            )
        return _call_openai_compatible(
            prompt,
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            model=cfg["model"],
            timeout=timeout,
        )
    raise LLMError(
        f"неизвестный LLM_BACKEND={cfg['backend']!r} (ожидается claude|openai)."
    )


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
