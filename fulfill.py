#!/usr/bin/env python3
"""kwork-fulfiller — CLI orchestrator (движок + сменные профили).

Один движок, под каждую услугу — профиль (промпт + правила автопроверки +
структура документа) в profiles/NN_*.json.

Pipeline for one Kwork order:
  load profile (3 parts: create / settings / checks)
    -> read brief
    -> build prompt (template + brief + settings)
    -> call Claude (or dry-run stub)
    -> parse result
    -> builder writes deliverable file(s) into --out
    -> run_checks and print a ✅ОК / ⚠️НА ДОРАБОТКУ report
    -> (--review) опциональная 2-я ИИ-прогонка на смысл
  Exit code is non-zero if any CRITICAL check fails.

Usage:
  python fulfill.py --niche price_list --brief samples/price_list.txt --out ./out
  python fulfill.py --niche price_list --brief - --out ./out
  python fulfill.py                       # interactive menu
  python fulfill.py --niche price_list --brief samples/price_list.txt --dry-run
  python fulfill.py --niche price_list --brief samples/price_list.txt --review
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from engine import llm, outputs, validate
from stubs import dry_run_stub

ROOT = pathlib.Path(__file__).resolve().parent
PROFILES_DIR = ROOT / "profiles"


# --------------------------------------------------------------------------- #
# Profile loading
# --------------------------------------------------------------------------- #


def list_niches() -> list[tuple[str, pathlib.Path]]:
    """Return (id, path) for every profile JSON, ordered by filename prefix."""
    out: list[tuple[str, pathlib.Path]] = []
    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        out.append((data.get("id", path.stem), path))
    return out


def load_niche(niche_id: str) -> dict:
    """Load a niche preset by its `id` (or filename stem)."""
    for nid, path in list_niches():
        if nid == niche_id or path.stem.endswith(niche_id):
            return json.loads(path.read_text(encoding="utf-8"))
    available = ", ".join(nid for nid, _ in list_niches())
    raise SystemExit(f"Unknown profile {niche_id!r}. Available: {available}")


# --------------------------------------------------------------------------- #
# Prompt assembly
# --------------------------------------------------------------------------- #


def _format_template(template_text: str, settings: dict, brief: str) -> str:
    """Fill {placeholders} in the template from settings (missing -> left as-is).

    Adds a couple of derived values so templates can reference them.
    """
    ctx = dict(settings)
    count = settings.get("count", 0)
    cats = settings.get("categories", 1) or 1
    ctx.setdefault("count_per_cat", max(1, int(count) // int(cats)) if count else 1)
    # Render list values inline for readability inside the prompt.
    rendered = {k: (", ".join(map(str, v)) if isinstance(v, list) else v) for k, v in ctx.items()}

    # Substitute ONLY known {settings_key} tokens. We can't use str.format here:
    # templates embed a JSON example whose braces ({ "title": … }, {{...}}) would
    # break str.format and (previously) silently skipped ALL substitution. A
    # targeted regex replaces just the identifiers we know, leaving every other
    # brace — JSON examples, {{placeholders}} — untouched.
    def _sub(match: "re.Match") -> str:
        key = match.group(1)
        return str(rendered[key]) if key in rendered else match.group(0)

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", _sub, template_text)


def build_prompt(niche: dict, brief: str) -> str:
    """Compose the full prompt: template + settings + buyer brief."""
    template_rel = niche["create"]["template"]
    template_path = ROOT / template_rel
    template_text = template_path.read_text(encoding="utf-8")
    settings = niche.get("settings", {})
    filled = _format_template(template_text, settings, brief)

    settings_block = json.dumps(settings, ensure_ascii=False, indent=2)
    return (
        f"{filled}\n\n"
        f"---\n\n"
        f"## Настройки заказа\n```json\n{settings_block}\n```\n\n"
        f"## Бриф заказчика\n{brief.strip()}\n\n"
        f"---\nВерни результат строго в формате, описанном выше. Без пояснений."
    )


# --------------------------------------------------------------------------- #
# Brief reading
# --------------------------------------------------------------------------- #


def read_brief(brief_arg: str) -> str:
    """Read the brief from a file path, '-' (stdin), or treat as literal text."""
    if brief_arg == "-":
        return sys.stdin.read()
    path = pathlib.Path(brief_arg)
    if path.exists():
        return path.read_text(encoding="utf-8")
    # Not a path -> treat the argument itself as the brief text.
    return brief_arg


def parse_set_args(pairs: list[str]) -> dict:
    """Turn ['count=80', 'tone=живой'] into {'count': 80, 'tone': 'живой'}."""
    out: dict = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--set expects k=v, got {pair!r}")
        key, _, value = pair.partition("=")
        key = key.strip()
        value = value.strip()
        if value.isdigit():
            out[key] = int(value)
        else:
            try:
                out[key] = float(value)
            except ValueError:
                out[key] = value
    return out


# --------------------------------------------------------------------------- #
# Result parsing per response_format
# --------------------------------------------------------------------------- #


def parse_result(raw: str, response_format: str):
    """Parse the raw model output according to the niche's response_format."""
    if response_format == "json":
        return llm.parse_json(raw)
    return raw  # plain text/markdown


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def print_report(
    niche: dict,
    files: list[pathlib.Path],
    check_results: list[tuple[str, bool, str, bool]],
) -> bool:
    """Print the deliverables + check report. Return True if all critical pass."""
    print("\n" + "=" * 60)
    print(f"  НИША: {niche.get('title')}  [{niche.get('id')}]")
    print("=" * 60)

    print("\nСозданные файлы:")
    for f in files:
        size = f.stat().st_size if f.exists() else 0
        print(f"  • {f}  ({size} B)")

    print("\nПроверки:")
    all_critical_ok = True
    for name, ok, detail, critical in check_results:
        mark = "✓" if ok else "✗"
        tag = "" if critical else "  (необязательная)"
        print(f"  {mark} {name}: {detail}{tag}")
        if critical and not ok:
            all_critical_ok = False

    print("\n" + ("РЕЗУЛЬТАТ: ✓ всё готово к сдаче" if all_critical_ok
                   else "РЕЗУЛЬТАТ: ✗ есть критичные ошибки — доработать"))
    print("=" * 60 + "\n")
    return all_critical_ok


# --------------------------------------------------------------------------- #
# Core run
# --------------------------------------------------------------------------- #


def run(niche_id: str, brief_arg: str, out_dir: str, overrides: dict,
        dry_run: bool, do_review: bool = False) -> int:
    niche = load_niche(niche_id)
    niche.setdefault("settings", {}).update(overrides)

    brief = read_brief(brief_arg)
    if not brief.strip():
        print("Пустой бриф — нечего генерировать.", file=sys.stderr)
        return 2

    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(niche, brief)
    response_format = niche["create"].get("response_format", "json")

    stub = dry_run_stub(niche, brief) if dry_run else None
    print(f"[{'dry-run' if dry_run else 'live'}] вызываю Claude для ниши '{niche['id']}'…")
    raw = llm.call_claude(prompt, dry_run=dry_run, stub=stub)

    try:
        result = parse_result(raw, response_format)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Не удалось распарсить ответ модели: {exc}", file=sys.stderr)
        (out_path / f"{niche['id']}_raw.txt").write_text(raw, encoding="utf-8")
        return 3

    builder = outputs.get_builder(niche["create"]["builder"])
    base_name = niche["id"]
    files = builder(result, out_path, niche, base_name)

    check_results = validate.run_checks(result, niche.get("checks", []), brief=brief)
    ok = print_report(niche, files, check_results)

    if do_review and not dry_run:
        from engine import review
        print("Смысл-ревью (2-я ИИ-прогонка)…")
        verdict = review.review_result(result, niche, brief)
        print(f"  Вердикт: {verdict.get('verdict')}")
        for issue in verdict.get("issues", []):
            print(f"   • {issue}")
        print("=" * 60 + "\n")

    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# Interactive menu
# --------------------------------------------------------------------------- #


def interactive() -> int:
    niches = list_niches()
    print("\nВыберите нишу:")
    for i, (nid, path) in enumerate(niches, 1):
        data = json.loads(path.read_text(encoding="utf-8"))
        print(f"  {i}. {nid:14s} — {data.get('title')}")
    choice = input("\nНомер ниши: ").strip()
    try:
        nid = niches[int(choice) - 1][0]
    except (ValueError, IndexError):
        print("Неверный выбор.", file=sys.stderr)
        return 2

    brief_path = input("Путь к файлу брифа (или текст брифа): ").strip()
    out_dir = input("Папка для результата [./out]: ").strip() or "./out"
    dry = input("Dry-run без сети? [y/N]: ").strip().lower() == "y"
    rev = (not dry) and input("Смысл-ревью 2-й прогонкой? [y/N]: ").strip().lower() == "y"
    return run(nid, brief_path, out_dir, {}, dry, rev)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="kwork-fulfiller — генератор+проверка результата заказа")
    parser.add_argument("--niche", "--profile", dest="niche",
                        help="id профиля (см. папку profiles/)")
    parser.add_argument("--brief", help="файл брифа, '-' для stdin, или текст")
    parser.add_argument("--out", default="./out", help="папка для готовых файлов")
    parser.add_argument("--set", dest="sets", action="append", default=[],
                        metavar="k=v", help="переопределить настройку (повторяемо)")
    parser.add_argument("--dry-run", action="store_true",
                        help="без вызова Claude — подставить осмысленную заглушку")
    parser.add_argument("--review", action="store_true",
                        help="вторая ИИ-прогонка на смысл (не в dry-run)")
    args = parser.parse_args(argv)

    if not args.niche:
        return interactive()

    if not args.brief:
        parser.error("--brief обязателен вместе с --niche")

    overrides = parse_set_args(args.sets)
    try:
        return run(args.niche, args.brief, args.out, overrides, args.dry_run, args.review)
    except llm.LLMError as exc:
        print(f"Ошибка LLM: {exc}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
