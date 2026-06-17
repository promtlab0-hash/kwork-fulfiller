"""Опциональная вторая ИИ-прогонка — смысл-ревью результата.

Автопроверки в `validate.py` ловят ФОРМУ (полнота, длина, дубли, артефакты).
Этот модуль — про СМЫСЛ: отдельным вызовом `claude -p` просим модель прочитать
готовый результат глазами заказчика и вернуть короткий список замечаний.
Не блокирует сдачу (информирует оператора); в --dry-run не запускается.
"""

from __future__ import annotations

import json
from typing import Any

from . import llm

_REVIEW_PROMPT = """\
Ты — придирчивый редактор. Ниже — готовый результат заказа («{title}»), который
сейчас отдадут клиенту, и бриф клиента. Проверь СМЫСЛ (не форму):
- соответствует ли результат брифу, ничего ли не упущено и не выдумано;
- нет ли фактических ошибок, нелепостей, противоречий;
- везде ли живой, продающий, естественный язык без воды и канцелярита;
- не повторяются ли мысли между блоками.

Верни СТРОГО валидный JSON без markdown-обёртки:
{{"verdict": "ok" | "revise", "issues": ["короткое замечание", ...]}}
Если всё хорошо — verdict "ok" и пустой список issues. Замечания — по делу, кратко.

## Бриф
{brief}

## Результат (JSON)
{result}
"""


def review_result(result: Any, niche: dict, brief: str, *, timeout: int = 180) -> dict:
    """Run a second-pass meaning review. Returns {"verdict", "issues"}.

    Never raises on model/parse failure — returns a soft error dict so the
    caller can print it without aborting delivery.
    """
    prompt = _REVIEW_PROMPT.format(
        title=niche.get("title", niche.get("id", "результат")),
        brief=brief.strip(),
        result=json.dumps(result, ensure_ascii=False, indent=2)[:120000],
    )
    try:
        raw = llm.call_claude(prompt, dry_run=False, timeout=timeout)
        parsed = llm.parse_json(raw)
    except Exception as exc:  # noqa: BLE001 — review is best-effort
        return {"verdict": "unknown", "issues": [f"ревью недоступно: {exc}"]}
    if not isinstance(parsed, dict):
        return {"verdict": "unknown", "issues": ["ответ ревью не распознан"]}
    parsed.setdefault("verdict", "unknown")
    parsed.setdefault("issues", [])
    if not isinstance(parsed["issues"], list):
        parsed["issues"] = [str(parsed["issues"])]
    return parsed
