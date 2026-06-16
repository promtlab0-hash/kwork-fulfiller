"""ПРОВЕРКА — declarative validation of a generated result.

Each check is a dict from the niche JSON, e.g. {"type": "min_count",
"field": "prompts", "value": 30}. run_checks dispatches by `type` and returns
a list of (name, ok, detail) tuples. A check may set "critical": false to make
a failure non-fatal (informational); by default every check is critical.

Supported types:
  nonempty          — result is a non-empty dict/list/str
  valid_json        — result parsed as JSON (i.e. is a dict or list)
  min_count         — len(result[field]) >= value
  min_items         — alias of min_count, default field "items"
  char_range        — total text length within [min, max]
  contains_keywords — every keyword in `keywords` appears (case-insensitive)
  no_placeholders   — no {{...}}, [ЦА]-style, lorem ipsum, TODO markers
  has_sections      — every name in `sections` appears as a key or heading
  py_compiles       — given Python source compiles cleanly
"""

from __future__ import annotations

import ast
import re
from typing import Any

CheckResult = tuple[str, bool, str]

_PLACEHOLDER_PATTERNS = [
    r"\{\{.*?\}\}",          # {{handlebars}}
    r"lorem ipsum",
    r"\bTODO\b",
    r"\bFIXME\b",
    r"\bxxxx+\b",
    r"\[(?:ВСТАВЬ|ВСТАВИТЬ|ЗАПОЛНИ|TODO|ПЛЕЙСХОЛДЕР|PLACEHOLDER)[^\]]*\]",
    r"<[^>]*placeholder[^>]*>",
    r"…\s*…\s*…",            # repeated ellipsis filler
]


def _collect_text(value: Any) -> str:
    """Flatten any nested structure into one searchable string."""
    parts: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for k, sub in v.items():
                parts.append(str(k))
                walk(sub)
        elif isinstance(v, (list, tuple)):
            for sub in v:
                walk(sub)
        elif v is not None:
            parts.append(str(v))

    walk(value)
    return "\n".join(parts)


def _resolve_field(result: Any, field: str | None) -> Any:
    """Fetch result[field], or the result itself when field is None."""
    if field is None:
        return result
    if isinstance(result, dict):
        return result.get(field)
    return None


def _check_nonempty(result: Any, _: dict) -> CheckResult:
    ok = bool(result) and (
        not isinstance(result, (dict, list, str)) or len(result) > 0
    )
    return ("nonempty", ok, "result is non-empty" if ok else "result is empty")


def _check_valid_json(result: Any, _: dict) -> CheckResult:
    ok = isinstance(result, (dict, list))
    return ("valid_json", ok, type(result).__name__)


def _check_min_count(result: Any, check: dict) -> CheckResult:
    field = check.get("field")
    value = int(check.get("value", 1))
    target = _resolve_field(result, field)
    count = len(target) if isinstance(target, (list, dict, str)) else 0
    ok = count >= value
    label = f"min_count[{field or 'result'}]"
    return (label, ok, f"{count} >= {value}" if ok else f"{count} < {value}")


def _check_min_items(result: Any, check: dict) -> CheckResult:
    field = check.get("field", "items")
    return _check_min_count(result, {**check, "field": field})


def _check_char_range(result: Any, check: dict) -> CheckResult:
    field = check.get("field")
    target = _resolve_field(result, field)
    text = _collect_text(target if field else result)
    length = len(text)
    lo = int(check.get("min", 0))
    hi = int(check.get("max", 10**9))
    ok = lo <= length <= hi
    return (
        f"char_range[{field or 'result'}]",
        ok,
        f"{length} chars in [{lo}, {hi}]" if ok else f"{length} chars outside [{lo}, {hi}]",
    )


def _check_contains_keywords(result: Any, check: dict) -> CheckResult:
    keywords = check.get("keywords", [])
    field = check.get("field")
    haystack = _collect_text(_resolve_field(result, field) if field else result).lower()
    missing = [k for k in keywords if k.lower() not in haystack]
    ok = not missing
    detail = "all keywords present" if ok else f"missing: {', '.join(missing)}"
    return ("contains_keywords", ok, detail)


def _check_no_placeholders(result: Any, _: dict) -> CheckResult:
    text = _collect_text(result)
    hits: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            hits.append(m.group(0)[:40])
    ok = not hits
    detail = "no placeholders" if ok else f"found: {', '.join(sorted(set(hits))[:5])}"
    return ("no_placeholders", ok, detail)


def _check_has_sections(result: Any, check: dict) -> CheckResult:
    sections = check.get("sections", [])
    if isinstance(result, dict):
        haystack = _collect_text(list(result.keys()) + [_collect_text(result)])
    else:
        haystack = _collect_text(result)
    haystack_low = haystack.lower()
    missing = [s for s in sections if s.lower() not in haystack_low]
    ok = not missing
    detail = "all sections present" if ok else f"missing: {', '.join(missing)}"
    return ("has_sections", ok, detail)


def _check_py_compiles(result: Any, check: dict) -> CheckResult:
    field = check.get("field", "code")
    source = _resolve_field(result, field)
    if not isinstance(source, str):
        # Fall back: maybe result itself is the source string.
        source = result if isinstance(result, str) else None
    if not isinstance(source, str) or not source.strip():
        return ("py_compiles", False, "no Python source found")
    try:
        ast.parse(source)
        compile(source, "<script.py>", "exec")
    except SyntaxError as e:
        return ("py_compiles", False, f"SyntaxError: {e.msg} (line {e.lineno})")
    return ("py_compiles", True, "source compiles")


_DISPATCH = {
    "nonempty": _check_nonempty,
    "valid_json": _check_valid_json,
    "min_count": _check_min_count,
    "min_items": _check_min_items,
    "char_range": _check_char_range,
    "contains_keywords": _check_contains_keywords,
    "no_placeholders": _check_no_placeholders,
    "has_sections": _check_has_sections,
    "py_compiles": _check_py_compiles,
}


def run_checks(result: Any, checks: list[dict]) -> list[tuple[str, bool, str, bool]]:
    """Run every declared check.

    Returns a list of (name, ok, detail, critical) tuples. `critical` defaults
    to True; a check sets "critical": false to be advisory-only.
    """
    out: list[tuple[str, bool, str, bool]] = []
    for check in checks:
        ctype = check.get("type")
        handler = _DISPATCH.get(ctype)
        critical = bool(check.get("critical", True))
        if handler is None:
            out.append((f"unknown[{ctype}]", False, "no such check type", critical))
            continue
        name, ok, detail = handler(result, check)
        out.append((name, ok, detail, critical))
    return out
