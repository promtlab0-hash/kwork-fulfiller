"""Dry-run stubs.

For each implemented profile, produce a deterministic, schema-valid payload (as
the JSON string the model would have returned) so the builders and checks can
run offline. The data is realistic enough that every declared check passes.

Stubs receive (settings, brief) so volume-niches can mirror the brief's item
count — that keeps the `completeness` check honest in --dry-run.
"""

from __future__ import annotations

import json
import re


def parse_brief_items(brief: str) -> list[str]:
    """Best-effort extraction of list positions from a free-form brief.

    Counts lines that look like enumerated/bulleted positions:
      "1. Плед…", "- Полотенца…", "• Свеча…". Falls back to non-trivial lines
    under a "Товары"/"Позиции"/"Список" header. Header/label lines are skipped.
    """
    items: list[str] = []
    in_list = False
    for raw in brief.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if re.match(r"^(товары|позиции|услуги|список|ассортимент)\b.*:?\s*$", low):
            in_list = True
            continue
        m = re.match(r"^(?:\d+[.)]\s+|[-•*]\s+)(.+)$", line)
        if m:
            items.append(m.group(1).strip())
            in_list = True
            continue
        # A line with "key: value" before the list starts is a label, not an item.
        if not in_list and ":" in line:
            continue
        if in_list:
            items.append(line)
    if not items:
        # No markers at all: treat every non-label line as a position.
        items = [l.strip() for l in brief.splitlines()
                 if l.strip() and ":" not in l.strip()]
    return items


def _name_of(item: str) -> str:
    """Trim a position line down to a clean heading (drop the '— detail' tail)."""
    head = re.split(r"\s+[—–-]\s+", item, maxsplit=1)[0]
    return head.strip().rstrip(".,;")[:80] or item[:80]


def _price_list_stub(settings: dict, brief: str) -> dict:
    items = parse_brief_items(brief) or ["Товар 1", "Товар 2", "Товар 3"]
    tone = settings.get("tone", "тёплый, доверительный")
    sections = []
    for idx, item in enumerate(items, 1):
        name = _name_of(item)
        detail = ""
        parts = re.split(r"\s+[—–-]\s+", item, maxsplit=1)
        if len(parts) == 2:
            detail = parts[1].strip()
        para = (
            f"{name} — практичное решение для дома, которое легко впишется в "
            f"повседневный быт. {('Главное преимущество: ' + detail + '. ') if detail else ''}"
            f"Продумано до мелочей: приятные материалы, аккуратная отделка и "
            f"долгий срок службы. Берут, чтобы сделать дом уютнее без лишних хлопот."
        )
        bullets = [
            "Качественные материалы → служит долго и выглядит опрятно",
            "Простой уход → экономит время на стирке и уборке",
            f"Готов к использованию сразу → не нужно ничего докупать (позиция {idx})",
        ]
        if detail:
            bullets.insert(0, f"{detail} → ощутимая польза в быту")
        sections.append({
            "heading": name,
            "level": 2,
            "paragraphs": [para],
            "bullets": bullets,
        })
    title_line = next((l.strip() for l in brief.splitlines()
                       if l.lower().strip().startswith("бизнес")), "")
    title = title_line.split(":", 1)[1].strip() if ":" in title_line else "ниша заказчика"
    return {"title": f"Прайс-лист: {title}", "sections": sections, "_tone": tone}


_STUBS = {
    "price_list": _price_list_stub,
}


def dry_run_stub(niche: dict, brief: str) -> str:
    """Return a JSON string standing in for the model's response."""
    builder = _STUBS.get(niche["id"])
    if builder is None:
        raise ValueError(
            f"No dry-run stub for profile {niche['id']!r} "
            f"(implemented: {', '.join(sorted(_STUBS)) or 'none'})"
        )
    data = builder(niche.get("settings", {}), brief)
    data.pop("_tone", None)
    return json.dumps(data, ensure_ascii=False)
