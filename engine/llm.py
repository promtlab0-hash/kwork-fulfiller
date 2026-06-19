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
